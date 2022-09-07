#!/bin/bash
# A sample onboard script

# Provision the remote networks
python3 phase1.py

# Push the configs
python3 push.py

# Pause for a bit then retrieve the service IPs
sleep 15
python3 phase2.py


