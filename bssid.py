#!/usr/bin/env python3

read_me = '''
A Python 3 script to pull of the enabled BSSID from a specified network.

Required Python modules:
    meraki

Usage:
bssid.py Network Name

If you have only one Organization, it will search for the Network name.

If you have multiple Organizations, it will ask you which org to run against

API Key
requires you to have your API key in env vars as 'MERAKI_DASHBOARD_API_KEY'

'''

import meraki
import sys
from pathlib import Path
import json

ap_list = {}
bssid_list = []
p = Path.home()
loc = p / 'Documents' / 'BSSID'

dashboard = meraki.DashboardAPI(suppress_logging=True)


def getLocation():
    if not Path.is_dir(loc):
        Path.mkdir(loc)


def getOrgs(net_name):
    orgs = dashboard.organizations.getOrganizations()
    if len(orgs) == 1:
        for dic in orgs:
            orgID = dic['id']
            getNetworks(orgID, net_name)
    else:
        org_list = {}
        for dic in orgs:
            org_list[dic['name']] = dic['id']
        orgID = input(
            f'Please type in the number of the Organization name that you would like to query{json.dumps(org_list, indent = 4)}' "\n")
        getNetworks(orgID, net_name)


def getNetworks(orgID, net_name):
    networks = dashboard.organizations.getOrganizationNetworks(
        orgID, total_pages='all')
    for dic in networks:
        if dic['name'] == net_name:
            network_id = dic['id']
            getAP(network_id)
        else:
            print(f'We did not find {net_name} in your organization(s)')
            sys.exit()


def getAP(network_id):
    devices = dashboard.networks.getNetworkDevices(network_id)
    for dic in devices:
        model = dic['model'][:2]
        if model == 'MR' or model == 'CW':
            ap_list[dic['name']] = dic['serial']
    print(ap_list)
    getBss(net_name)


def getBss(net_name):
    bss = f'{loc}/{net_name}.csv'
    with open(bss, mode='w') as f:
        f.write(f"AP Name , SSID Name , Frequency , BSSID" + "\n")
        for k, v in ap_list.items():
            response = dashboard.wireless.getDeviceWirelessStatus(v)
            for data in response['basicServiceSets']:
                good = data['enabled']
                if good is True:
                    f.write(f"{k} , {data['ssidName']} , {data['band']}\
                         , {data['bssid']}" + "\n")
    print(f'Your file {net_name}.csv has been creeated in {loc}')
    sys.exit()


if __name__ == '__main__':
    try:
        sys.argv[1]
    except IndexError:
        print("Please provide a Network Name")
        sys.exit()
    else:
        net_name = ' '.join(sys.argv[1:])
        getLocation()
        getOrgs(net_name)
        getBss(net_name)
