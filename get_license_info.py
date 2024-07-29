#!/usr/bin/env python3

import meraki
from pathlib import Path
import json

read_me = '''
A Python 3 script to find the license status of an Organization.

Required Python modules:
    meraki 1.48.0 or higher

Usage:
get_license_info.py

If you have only one Organization, it will get the license status.

If you have multiple Organizations, it will ask you which org to run against

API Key
requires you to have your API key in env vars as 'MERAKI_DASHBOARD_API_KEY'

'''

p = Path.home()
loc = p / 'Documents' / 'Meraki License'

dashboard = meraki.DashboardAPI(suppress_logging=True)


def base_folder():
    '''
    Check if the root folder exists and create it if not
    '''
    if not Path.is_dir(loc):
        Path.mkdir(loc)


def get_orgs():
    '''
    get a list of organizations the user has access to and return that dict
    '''
    orgs = dashboard.organizations.getOrganizations()
    org_dict = {}
    for i in orgs:
        org_dict[i['id']] = i['name']
    return org_dict


def find_org(org_dict):
    '''
    If only one organizaiton exists, use that org_id
    '''
    if len(org_dict) == 1:
        org_id = org_dict[0]['id']
        org_name = org_dict[0]['name']
    else:
        '''
        If there are multiple organizations, ask the use which one to use
        then store that information to be used
        '''
        org_id = input(
            f"Please type the number of the Organization you want to find "
            f"the bssid in{json.dumps(org_dict, indent=4)}" "\n")
        org_name = org_dict.get(org_id)
    return org_id, org_name


def get_license(org_id):
    lic_info = dashboard.organizations.getOrganizationLicensesOverview(org_id)
    return lic_info


def file_writer(lic_info, org_name):
    print(f'writing License Information to file')
    file = f'{loc}/{org_name}.csv'
    status = lic_info['status']
    expiration = lic_info['expirationDate'].replace(',', '')
    with open(file, mode='w') as f:
        f.write(f"Status, Expiration Date" + "\n")
        f.write(f"{status}, {expiration}" + "\n" + "\n")
        f.write(f"Licensed Devices" + "\n")
        for k, v in lic_info['licensedDeviceCounts'].items():
            f.write(f"{k}, {v}" + "\n")
        print(f'Your file {org_name}.csv has been created in {loc}')


def main():
    base_folder()
    org_dict = get_orgs()
    org_id, org_name = find_org(org_dict)
    lic_info = get_license(org_id)
    file_writer(lic_info, org_name)


if __name__ == '__main__':
    main()
