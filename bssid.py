#!/usr/bin/env python3

import meraki
from pathlib import Path
import json

read_me = '''
A Python 3 script to pull of the enabled BSSID from an Organization.

Required Python modules:
    meraki 1.48.0 or higher

Usage:
bssid.py

If you have only one Organization, it will find all BSSID
and create a csv for each network in Documents/BSSID/Organization

If you have multiple Organizations, it will ask you which org to run against

API Key
requires you to have your API key in env vars as 'MERAKI_DASHBOARD_API_KEY'

'''

p = Path.home()
loc = p / 'Documents' / 'BSSID'

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


def org_folder(org_name):
    '''
    check if the organizaiton folder exists, create if not
    '''
    loc2 = Path.joinpath(loc, org_name)
    if not Path.is_dir(loc2):
        Path.mkdir(loc2)


def get_networks(org_id):
    net_list = dashboard.organizations.getOrganizationNetworks(
        org_id, total_pages='all')
    print(net_list)
    return net_list


def find_networks(net_list):
    net_ids = {}
    for i in net_list:
        if 'wireless' in i['productTypes']:
            net_ids[i['id']] = i['name']
    return net_ids


def get_bssid(org_id, net_ids):
    '''
    dump the BSSID list for the organization
    '''
    bssid_dict = dashboard.wireless.getOrganizationWirelessSsidsStatusesByDevice\
         (org_id, total_pages='all')
    return bssid_dict


def file_writer(bssid_dict, net_ids, org_name):
    print(f'writing BSSID to file')
    for k, v in net_ids.items():
        net_name = v
        file = f'{loc}/{org_name}/{net_name}.csv'
        with open(file, mode='w') as f:
            f.write(f"AP Name , SSID Name , Frequency , BSSID, AP Serial" + "\n")
            for ap in bssid_dict['items']:
                network = ap['network']['name']
                if net_name == network:
                    for bss in ap['basicServiceSets']:
                        f.write(f"{ap['name']}, "
                            f"{bss['ssid']['name']}, "
                            f"{bss['radio']['band']} GHz, "
                            f"{bss['bssid']}, "
                            f"{ap['serial']}" + "\n")
        print(f'Your file {net_name}.csv has been created in {loc}/{org_name}')


def main():
    base_folder()
    org_dict = get_orgs()
    org_id, org_name = find_org(org_dict)
    org_folder(org_name)
    net_list = get_networks(org_id)
    net_ids = find_networks(net_list)
    bssid_dict = get_bssid(org_id, net_ids)
    file_writer(bssid_dict, net_ids, org_name)


if __name__ == '__main__':
    main()
