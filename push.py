#!/usr/bin/env python3

import json
import requests
import panapi
from panapi.config import management
from time import sleep



def main():
    # Build the session handler
    session = panapi.PanApiSession()
    session.authenticate()
    # Push the config
    cfg = management.ConfigVersion(folders=['Remote Networks'])
    job = cfg.push(session)
    job_complete = False
    while job_complete is False:
        job.read(session)
        if session.response.status_code == 200:
            status = session.response.json()['data'][0]['status_str']
            print('Polling job {}: [{}]'.format(job.id, status))
            if status == 'FIN':
                job_complete = True
            elif status == 'PEND' or status == 'ACT':
                job_complete = False
            else:
                job_complete = True
        else:
            print(' API call failure!')
            break
        sleep(5)


if __name__ == '__main__':
    main()