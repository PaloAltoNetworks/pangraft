#!/usr/bin/env python3

import ipaddress
from operator import ne
import sys
import json
import secrets
import random
import struct
from geopy import distance
import panapi
from panapi.config import network, management

# Edit the following variables
FQDN = 'prismaaccess.com'
BGP_ASN = '65432'
IKE_PROFILE = "Velocloud-IKE-default"
IPSEC_PROFILE = "Velocloud-IPSec-default"
PEERNET = '172.16.0.0/12'
NETWORK_FILE = "networks.json"


def random_ip(network):
    network = ipaddress.IPv4Network(network)
    network_int, = struct.unpack("!I", network.network_address.packed)
    rand_bits = network.max_prefixlen - network.prefixlen
    rand_host_int = random.randint(0, 2**rand_bits - 1)
    ip_address = ipaddress.IPv4Address(network_int + rand_host_int)
    return ip_address.exploded


def get_locations(session):
    locations = network.Location()
    locations = locations.list(session)
    return locations


def get_distances(latitude, longitude, locations):
    distances = {}
    for l in locations:
        d = distance.distance((latitude, longitude), (l['latitude'], l['longitude'])).km
        distances[l['value']] = d
    return distances


def allocate_bw(region, bw, session):
    # Check if region already has bandwidth allocation
    r = network.BandwidthAllocation(name=region)
    r.read(session)
    if session.response.status_code == 404:
        r.allocated_bandwidth = bw
        r.create(session)
    elif session.response.status_code == 200:
        allocation = session.response.json()['data'][0]
        orig_bw = allocation['allocated_bandwidth']
        r.allocated_bandwidth = orig_bw + bw
        r.spn_name_list = allocation['spn_name_list']
        r.update(session)
    return session.response.json()


def create_ike_gateway(name, key, ufqdn, session):
    payload = {
        "name": name,
        "folder": "Remote Networks",
        "authentication": {
            "pre_shared_key": {
                "key": key
            }
        },
        "peer_address": {
            "dynamic": {}
        },
        "peer_id": {
            "type": "ufqdn",
            "id": ufqdn
        },
        "protocol": {
            "ikev2": {
                "dpd": {
                    "enable": True
                },
                "ike_crypto_profile": IKE_PROFILE
            },
            "version": "ikev2"
        }
    }
    ike_gateway = network.IKEGateway(**payload)
    ike_gateway.create(session)
    if session.response.status_code == 201:
        return session.response.json()
    else:
        sys.exit(session.response.json())


def create_ipsec_tunnel(name, gateway, session):
    payload = {
        "name": name,
        "folder": "Remote Networks",
        "auto_key": {
            "ike_gateway": [
                {
                    "name": gateway
                }
            ],
            "ipsec_crypto_profile": IPSEC_PROFILE
        }
    }
    ipsec_tunnel = network.IPSecTunnel(**payload)
    ipsec_tunnel.create(session)
    if session.response.status_code == 201:
        return session.response.json()
    else:
        sys.exit(session.response.json())


def create_remote_network(name, region, spn, tunnel, tunnel2, subnets, bgp_asn, key, session):
    payload = {
        "name": name,
        "folder": "Remote Networks",
        "license_type": "FWAAS-AGGREGATE",
        "region": region,
        "spn_name": spn,
        "ipsec_tunnel": tunnel,
        "subnets": subnets
    }
    if tunnel2:
        payload['secondary_ipsec_tunnel'] = tunnel2
    if bgp_asn:
        local_ip_address = random_ip(PEERNET)
        peer_ip_address = random_ip(PEERNET)
        payload['protocol'] = {
            "bgp": {
                "enable": True,
                "peer_as": bgp_asn,
                "peer_ip_address": peer_ip_address,
                "local_ip_address": local_ip_address,
                "secret": key,
                "originate_default_route": True,
                "do_not_export_routes": True
            }
        }
    remote_network = network.RemoteNetwork(**payload)
    remote_network.create(session)
    if session.response.status_code == 201:
        return session.response.json()
    else:
        sys.exit(session.response.json())


def valid_network(network):
    try:
        x = ipaddress.ip_network(network)
    except ValueError as err:
        sys.exit(err)
    return True
        

def main():
    # Process the json file
    with open(NETWORK_FILE, 'r') as f:
        remote_networks = json.load(f)
    # Build the session handler
    session = panapi.PanApiSession()
    session.authenticate()
    # If BGP is needed get the BGP ASN
    for b in remote_networks:
        if b['bgp'] is True:
            settings = network.SharedInfrastructureSetting().list(session)
            tenant_bgp_asn = settings['infra_bgp_as']
            break
        else:
            tenant_bgp_asn = None
    # Get the list of locations
    locations = get_locations(session)
    # Iterate through site list
    for site in remote_networks:
        site_name = site['name'].replace(' ', '_')
        # Get the per-site distances to each edge location
        distances = get_distances(site['latitude'], site['longitude'], locations)
        nearest_region = min(distances, key=distances.get)
        for region in locations:
            if region['region'] == nearest_region:
                nearest_aggregate = region.get('aggregate_region')
                break
        # Allocate the bandwidth and retrieve the SPN name
        allocation = allocate_bw(nearest_aggregate, site['bandwidth'], session)
        spn = allocation['spn_name_list'][-1]
        # Create the IKE gateway
        key = secrets.token_urlsafe(32)
        suffix = secrets.token_hex(2)
        ufqdn = suffix + '@' + FQDN
        gw_name = site_name + '-ike-' + suffix
        gw = create_ike_gateway(
            gw_name, 
            key,
            ufqdn,
            session
        )
        # Create the IPSec tunnel
        tunnel_name = site_name + '-ipsec-' + suffix
        tunnel = create_ipsec_tunnel(
            tunnel_name, 
            gw['name'], 
            session
        )
        # Create redundancy if defined
        ufqdn2 = None
        if site['redundancy']:
            # Create the IKE gateway
            key = secrets.token_urlsafe(32)
            suffix2 = secrets.token_hex(2)
            ufqdn2 = suffix2 + '@' + FQDN
            gw2_name = site_name + '-ike-' + suffix2
            gw2 = create_ike_gateway(
                gw2_name, 
                key,
                ufqdn2,
                session
            )
            # Create the IPSec tunnel
            tunnel2_name = site_name + '-ipsec-' + suffix2
            tunnel2 = create_ipsec_tunnel(
                tunnel2_name, 
                gw2['name'], 
                session
            )
        else:
            tunnel2 = {'name': None}
        # Create the Remote Network
        remote_network_name = site_name
        if site['subnets']:
            subnets = []
            for s in site['subnets']:
                if valid_network(s):
                    subnets.append(s)
        remote_network = create_remote_network(
            remote_network_name,
            nearest_region,
            spn,
            tunnel['name'],
            tunnel2['name'],
            subnets,
            BGP_ASN,
            key,
            session
        )
        # Wrap it up
        remote_network_json = {
            "name": remote_network_name,
            "pre_shared_key": key,
            "ufqdn": ufqdn
        }
        if 'ufqdn2' in locals():
            remote_network_json['ufqdn2'] = ufqdn2
        if 'tenant_bgp_asn' in locals():
            remote_network_json['peer_asn'] = BGP_ASN
        print(json.dumps(remote_network_json, indent=4))



if __name__ == '__main__':
    main()