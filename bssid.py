#!/usr/bin/env python3

import meraki
from pathlib import Path
import json

read_me = '''
A Python 3 script to pull of the enabled BSSID from an Organization.

Required Python modules:
    meraki

Usage:
bssid.py

If you have only one Organization, it will find all BSSID in each Network
and create a csv for each in Documents/BSSID/Organization

If you have multiple Organizations, it will ask you which org to run against

API Key
requires you to have your API key in env vars as 'MERAKI_DASHBOARD_API_KEY'

'''

p = Path.home()
loc = p / 'Documents' / 'BSSID'

dashboard = meraki.DashboardAPI(suppress_logging=True)


def base_folder():
    if not Path.is_dir(loc):
        Path.mkdir(loc)


def get_orgs():
    orgs = dashboard.organizations.getOrganizations()
    org_dict = {}
    for i in orgs:
        org_dict[i['id']] = i['name']
    return org_dict


def find_org(org_dict):
    if len(org_dict) == 1:
        org_id = org_dict[0]['id']
        org_name = org_dict[0]['name']
    else:
        org_id = input(
            f"Please type the number of the Organization you want to find "
            f"the bssid in{json.dumps(org_dict, indent=4)}" "\n")
        org_name = org_dict.get(org_id)
    return org_id, org_name


def org_folder(org_name):
    loc2 = Path.joinpath(loc, org_name)
    if not Path.is_dir(loc2):
        Path.mkdir(loc2)


def get_networks(org_id):
    net_list = dashboard.organizations.getOrganizationNetworks(
        org_id, total_pages='all')
    return net_list


def find_networks(net_list):
    net_ids = {}
    for i in net_list:
        if 'wireless' in i['productTypes']:
            net_ids[i['id']] = i['name']
            net_name = i['name']
    return net_ids, net_name


def find_ap(net_ids):
    ap_dict = {}
    for k, v in net_ids.items():
        name = v
        lst = []
        devices = dashboard.networks.getNetworkDevices(k)
        for i in devices:
            model = i['model'][:2]
            if model == 'MR' or model == 'CW':
                dic = {}
                if i.get('name') is None:
                    dic.update(name=i['mac'], serial=i['serial'])
                else:
                    dic.update(name=i['name'], serial=i['serial'])
                lst.append(dic)
        ap_dict[name] = lst
    return ap_dict


def get_bssid(ap_dict, net_ids):
    bssid_dict = {}
    for k, v in net_ids.items():
        name = v
        lst = []
        for data in ap_dict[name]:
            ap = data['serial']
            response = dashboard.wireless.getDeviceWirelessStatus(ap)
            for value in response['basicServiceSets']:
                info_dict = {}
                good = value['enabled']
                if good is True:
                    info_dict['name'] = data['name']
                    info_dict['ssidName'] = value['ssidName']
                    info_dict['band'] = value['band']
                    info_dict['bssid'] = value['bssid']
                    lst.append(info_dict)
        bssid_dict[name] = lst
    return bssid_dict


def file_writer(bssid_dict, net_ids, org_name):
    for k, v in net_ids.items():
        network = v
        file = f'{loc}/{org_name}/{network}.csv'
        with open(file, mode='w') as f:
            f.write(f"AP Name , SSID Name , Frequency , BSSID" + "\n")
            for data in bssid_dict[network]:
                f.write(f"{data['name']}, {data['ssidName']}, "
                    f"{data['band']}, {data['bssid']}" + "\n")
    print(f'Your file {network}.csv has been created in {loc} / {org_name}')


def main():
    base_folder()
    org_dict = get_orgs()
    org_id, org_name = find_org(org_dict)
    org_folder(org_name)
    net_list = get_networks(org_id)
    net_ids, net_name = find_networks(net_list)
    ap_dict = find_ap(net_ids)
    bssid_dict = get_bssid(ap_dict, net_ids)
    print(f'writing BSSID to file')
    file_writer(bssid_dict, net_ids, org_name)


if __name__ == '__main__':
    main()
