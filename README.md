# pangraft

The scripts contained in this repo are for demonstrating the use of Palo Alto Networks Cloud Management API for automated onboarding of third-party SD-WAN branch networks.  They utilize the lightweight Cloud Management API SDK located at https://github.com/PaloAltoNetworks/panapi.

This is intended to serve as a proof-of-concept rather than a supported tool for branch network orchestration.

--- 
## Dependencies
- panapi
- geopy
- geographiclib

---
## Authentication

The OAuth2.0 session handler that is included in the `panapi` SDK can be instantiated with the `client_id`, `client_secret`, `scope`, and `token_url` attribute values.  However, this script assumes that you've written your credentials to the `$HOME/.panapi/config.yml` file as follows:

```yaml
# my lab tenant
client_id: my-service-acct@1018675309.iam.panserviceaccount.com
client_secret: 2d9f31ca-dead-beef-a196-857c42d77b99
token_url: https://auth.apps.paloaltonetworks.com/am/oauth2/access_token
scope: tsg_id:1018675309
```

---
## Preparation

1. Download the `pangraft` repository.
```bash
$ git clone https://github.com/PaloAltoNetworks/pangraft.git
```

2. Create a python virtual environment within the pangraft directory and activate it.
```bash
$ cd pangraft
$ python3 -m venv .venv
$ source .venv/bin/activate
```

3. Upgrade pip.  
**_NOTE:_** This is important as earlier versions of pip will not properly install the `PyJWT` package dependencies.
```bash
$ pip install --upgrade pip
```

4. Install `panapi` and the rest of the required packages.
```bash
$ pip install panapi
$ pip install -r requirements.txt
```

5. Edit the `networks.json` file and provide the relevant details for your branch networks.
```json
[
    {
        "name": "London",
        "latitude": 51.507351,
        "longitude": -0.127758,
        "bandwidth": 100,
        "subnets": ["10.2.2.0/24"],
        "redundancy": false,
        "bgp": true,
        "platform": "silverpeak"
    },
    {
        "name": "Tokyo",
        "latitude": 35.689487,
        "longitude": 139.691711,
        "bandwidth": 100,
        "subnets": ["10.6.2.0/24"],
        "redundancy": true,
        "bgp": false,
        "platform": "velocloud"
    },
    {
        "name": "Sao Paulo",
        "latitude": -23.550520,
        "longitude": -46.633308,
        "bandwidth": 50,
        "subnets": ["10.3.2.0/24"],
        "redundancy": true,
        "bgp": true,
        "platform": "viptela"
    }
]
```
### Platform Values
The `platform` attribute is used to select the predefined IKE and IPSec crypto profiles for a given platform.  Valid values are as follows:

| Value | Platform | 
|-------|----------|
| cloudgenix | Prisma SD-WAN |
| paloalto | PAN-OS SD-WAN |
| velocloud | VMWare VeloCloud |
| silverpeak | Aruba Networks / Silver Peak |
| viptela | Cisco Viptela | 
| ciscoasa | Cisco ASA | 
| ciscoisr | Cisco ISR | 
| riverbed | Riverbed | 
| other | Other |

---
## Usage

```bash
$ python3 pangraft.py -h
usage: pangraft.py [-h] [-b BGP_ASN] [-p PEER_NET] filename domainname

Onboard a list of remote networks to Prisma SASE

positional arguments:
  filename              JSON file containing network details
  domainname            DNS domain name

optional arguments:
  -h, --help            show this help message and exit
  -b BGP_ASN, --bgp_asn BGP_ASN
                        The BGP autonomous system number (ASN)
  -p PEER_NET, --peer_net PEER_NET
                        IP netblock used for BGP peering loopback addresses
```

---
## Output

The script will output the following configuration details which may be used in the branch SD-WAN configuration.

- Remote network name
  - IKE pre-shared key (PSK)
  - IKE Local ID (primary tunnel)
  - IKE Local ID (secondary tunnel)
  - BGP peer autonomous system (AS)
  - Tunnel termination IP address