#!/usr/bin/env python3

#
# A proof-of-concept API automation script used to graft new branches onto a Prisma SASE tenant
#

import json
import secrets
import argparse
import logging
from time import sleep
import panapi
from panapi.config import network, management
from pangraft import *


def main():
    #
    # Grab the arguments
    #
    parser = argparse.ArgumentParser(description='Onboard a list of remote networks to Prisma SASE')
    parser.add_argument('filename', help='JSON file containing network details')
    parser.add_argument('domainname', help='DNS domain name')
    parser.add_argument('-b', '--bgp_asn', help='The BGP autonomous system number (ASN)')
    parser.add_argument('-p', '--peer_net', help='Netblock used for BGP peering loopback addresses', default='172.16.0.0/12')
    args = parser.parse_args()
    input_file = args.filename
    domainname = args.domainname
    bgp_asn = args.bgp_asn
    peer_net = args.peer_net
    #
    # Initialize the output logger
    #
    logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
        )
    #
    # Process the json file
    #
    logging.info('Reading input file: {}'.format(input_file))
    with open(input_file, 'r') as f:
        remote_networks = json.load(f)
    #
    # Build the session handler
    #
    logging.info('Initializing API session handler')
    session = panapi.PanApiSession()
    session.authenticate()
    #
    # If BGP is needed get the BGP ASN
    #
    if bgp_asn:
        settings = network.SharedInfrastructureSetting().list(session)
        tenant_bgp_asn = settings['infra_bgp_as']
    else:
        tenant_bgp_asn = None
    #
    # Get the list of edge locations
    #
    logging.info('Retrieving edge location data')
    locations = get_locations(session)
    #
    # Iterate through the list of locations
    #
    remote_network_json = {}
    for site in remote_networks:
        site_name = site['name']
        logging.info('----- {} -----'.format(site_name))
        #
        # Get the per-site distances to each edge location and select the nearest
        #
        distances = get_distances(site['latitude'], site['longitude'], locations)
        nearest_region = min(distances, key=distances.get)
        for region in locations:
            if region['region'] == nearest_region:
                nearest_aggregate = region.get('aggregate_region')
                break
        logging.info('Selecting nearest compute location: {}'.format(nearest_aggregate))
        #
        # Allocate the bandwidth and retrieve the SPN name
        #
        logging.info('Allocating bandwidth (Mbps): {}'.format(site['bandwidth']))
        allocation = allocate_bw(nearest_aggregate, site['bandwidth'], session)
        spn = allocation['spn_name_list'][-1]
        #
        # Create the IKE gateway
        #
        key = secrets.token_urlsafe(32)
        suffix = secrets.token_hex(2)
        ufqdn = suffix + '@' + domainname
        gw_name = site_name.replace(' ', '_') + '-ike-' + suffix
        logging.info('Creating primary IKE gateway: {}'.format(gw_name))
        gw = create_ike_gateway(
            gw_name, 
            key,
            ufqdn,
            site['platform'],
            session
        )
        #
        # Create the IPSec tunnel
        #
        tunnel_name = site_name.replace(' ', '_') + '-ipsec-' + suffix
        logging.info('Creating primary IPSec tunnel: {}'.format(tunnel_name))
        tunnel = create_ipsec_tunnel(
            tunnel_name, 
            gw['name'],
            site['platform'],
            session
        )
        #
        # Create redundancy if defined
        #
        ufqdn2 = None
        if site['redundancy']:
            #
            # Create the secondary IKE gateway
            #
            key = secrets.token_urlsafe(32)
            suffix2 = secrets.token_hex(2)
            ufqdn2 = suffix2 + '@' + domainname
            gw2_name = site_name.replace(' ', '_') + '-ike-' + suffix2
            logging.info('Creating secondary IKE gateway: {}'.format(gw2_name))
            gw2 = create_ike_gateway(
                gw2_name, 
                key,
                ufqdn2,
                site['platform'],
                session
            )
            #
            # Create the secondary IPSec tunnel
            #
            tunnel2_name = site_name.replace(' ', '_') + '-ipsec-' + suffix2
            logging.info('Creating secondary IPSec tunnel: {}'.format(tunnel2_name))
            tunnel2 = create_ipsec_tunnel(
                tunnel2_name, 
                gw2['name'],
                site['platform'],
                session
            )
        else:
            tunnel2 = {'name': None}
        #
        # Create the Remote Network
        #
        remote_network_name = site_name
        logging.info('Creating Remote Network: {}'.format(remote_network_name))
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
            bgp_asn,
            peer_net,
            key,
            session
        )
        #
        # Update the results
        #
        remote_network_json[remote_network_name] = {
            "pre_shared_key": key,
            "primary_local_id": ufqdn
        }
        if 'ufqdn2' in locals():
            remote_network_json[remote_network_name]['secondary_local_id'] = ufqdn2
        if 'tenant_bgp_asn' in locals():
            remote_network_json[remote_network_name]['peer_asn'] = tenant_bgp_asn
    #
    # Push the configuration and wait for the job to complete
    #
    logging.info('Pushing the configuration')
    job = management.ConfigVersion(folders=['Remote Networks']).push(session)
    job_complete = False
    while job_complete is False:
        job.read(session)
        if session.response.status_code == 200:
            status = session.response.json()['data'][0]['status_str']
            logging.info('Polling job [{}]: {}'.format(job.id, status))
            if status == 'FIN':
                job_complete = True
            elif status == 'PEND' or status == 'ACT':
                job_complete = False
            else:
                job_complete = True
        else:
            logging.error('API call failure!')
            break
        sleep(5)
    #
    # Retrieve the service IPs for all remote networks
    #
    logging.info('Retrieving edge service IP addresses')
    settings = network.SharedInfrastructureSetting().list(session)
    api_key = settings['api_key']
    sleep(15)
    addresses = get_service_ips(api_key)
    #
    # Update the results with the service IPs for the remote networks we've provisioned
    #
    for s in remote_networks:
        remote_network_json[s['name']]['peer_ip'] = addresses.get(s['name'])
    #
    # Output the results
    # 
    logging.info('Summarizing local configuration parameters')
    print(json.dumps(remote_network_json, indent=4))
    

#
# Let's do this!
#
if __name__ == '__main__':
    main()
