#!/usr/bin/env python3

import json
import requests
import panapi
from panapi.config import network

NETWORK_FILE = "networks.json"

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


def main():
    # Process the json file
    with open(NETWORK_FILE, 'r') as f:
        remote_networks = json.load(f)
    # Build the session handler
    session = panapi.PanApiSession()
    session.authenticate()
    # Get the shared infrastructure settings
    settings = network.SharedInfrastructureSetting().list(session)
    api_key = settings['api_key']
    # Get the service IP address list
    addresses = get_service_ips(api_key)
    # Print the results
    print(json.dumps(addresses, indent=4))


if __name__ == '__main__':
    main()