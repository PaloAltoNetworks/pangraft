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
## Usage

First, you will need to download and install the `panapi` SDK.  It is recommended you create a virtual environment for this.

Create a workspace directory.
```bash
$ mkdir workspace
$ cd workspace
```

Download the `panapi` and `pangraft` repositories.
```bash
$ git clone https://github.com/PaloAltoNetworks/panapi.git
$ git clone https://github.com/PaloAltoNetworks/pangraft.git
```

Create a python virtual environment within the pangraft directory and activate it.
```bash
$ cd pangraft
$ python3 -m venv .venv
$ source .venv/bin/activate
```

Upgrade pip.  This is important as earlier versions of pip will not properly install the `cryptography` package.
```bash
$ pip install --upgrade pip
```

Install `panapi` and the rest of the required packages.
```bash
$ pip install ../panapi
$ pip install -r requirements.txt
```

Edit the `networks.json` file and provide the relevant details for your branch networks.
```json
[
    {
        "name": "London",
        "latitude": 51.507351,
        "longitude": -0.127758,
        "bandwidth": 100,
        "subnets": ["10.2.2.0/24"],
        "redundancy": false,
        "bgp": true
    },
    {
        "name": "Tokyo",
        "latitude": 35.689487,
        "longitude": 139.691711,
        "bandwidth": 100,
        "subnets": ["10.6.2.0/24"],
        "redundancy": true,
        "bgp": false
    },
    {
        "name": "Sao Paulo",
        "latitude": -23.550520,
        "longitude": -46.633308,
        "bandwidth": 50,
        "subnets": ["10.3.2.0/24"],
        "redundancy": true,
        "bgp": true
    }
]
```

Edit the following variables in `phase1.py` to suit your needs.
```bash
FQDN = 'prismaaccess.com'
BGP_ASN = '65432'
IKE_PROFILE = "Velocloud-IKE-default"
IPSEC_PROFILE = "Velocloud-IPSec-default"
PEERNET = '172.16.0.0/12'
```

Run the onboarding script.
```bash
$ bash onboard.sh
```

The phase1 and phase2 scripts will output the following configuration details which may be used in the branch SD-WAN configuration.

- Remote network name
- IKE pre-shared key (PSK)
- Local ID (primary tunnel)
- Local ID (secondary tunnel)
- BGP peer autonomous system (AS)
- Tunnel terimination IP address