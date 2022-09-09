#!/usr/bin/env python3

import random
import struct
import ipaddress
import sys
import requests
from geopy import distance
from panapi.config import network, management



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


def create_ike_gateway(name, key, ufqdn, platform, session):
    ike_platforms = {
        'cloudgenix': 'CloudGenix-IKE-Crypto-Default',
        'paloalto': 'PaloAlto-Networks-IKE-Crypto',
        'velocloud': 'Velocloud-IKE-default',
        'silverpeak': 'SilverPeak-IKE-Crypto-Default',
        'viptela': 'Viptela-IKE-default',
        'riverbed': 'Riverbed-IKE-Crypto-Default',
        'ciscoasa': 'CiscoASA-IKE-Crypto-Default',
        'ciscoisr': 'CiscoISR-IKE-Crypto-Default',
        'other': 'Others-IKE-Crypto-Default'
    }
    ike_profile = ike_platforms.get(platform)
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
                "ike_crypto_profile": ike_profile
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


def create_ipsec_tunnel(name, gateway, platform, session):
    ipsec_platforms = {
        'cloudgenix': 'CloudGenix-IPSec-Crypto-Default',
        'paloalto': 'PaloAlto-Networks-IPSec-Crypto',
        'velocloud': 'Velocloud-IPSec-default',
        'silverpeak': 'SilverPeak-IPSec-Crypto-Default',
        'viptela': 'Viptela-IPSec-default',
        'riverbed': 'Riverbed-IPSec-Crypto-Default',
        'ciscoasa': 'CiscoASA-IPSec-Crypto-Default',
        'ciscoisr': 'CiscoISR-IPSec-Crypto-Default',
        'other': 'Others-IPSec-Crypto-Default'
    }
    ipsec_profile = ipsec_platforms.get(platform)
    payload = {
        "name": name,
        "folder": "Remote Networks",
        "auto_key": {
            "ike_gateway": [
                {
                    "name": gateway
                }
            ],
            "ipsec_crypto_profile": ipsec_profile
        }
    }
    ipsec_tunnel = network.IPSecTunnel(**payload)
    ipsec_tunnel.create(session)
    if session.response.status_code == 201:
        return session.response.json()
    else:
        sys.exit(session.response.json())


def create_remote_network(name, region, spn, tunnel, tunnel2, subnets, bgp_asn, peer_net, key, session):
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
        local_ip_address = random_ip(peer_net)
        peer_ip_address = random_ip(peer_net)
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


def get_service_ips(key):
    url = 'https://api.prod.datapath.prismaaccess.com/getPrismaAccessIP/v2'
    headers = {'header-api-key': key}
    payload = {
        'serviceType': 'remote_network',
        'addrType': 'service_ip',
        'location': 'all'
    }
    r = requests.post(url=url, headers=headers, json=payload)
    result = r.json()['result']
    addresses = {}
    for a in result:
        for b in a['address_details']:
            node = b['node_name'][0]
            ip_addr = b['address']
            addresses[node] = ip_addr
    return addresses