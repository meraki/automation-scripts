#!/usr/bin/env python3

import meraki
from pathlib import Path
import json

read_me = '''
A Python 3 script to pull of the enabled BSSID from an Organization

Required Python modules:
    meraki

Usage:
bssid.py

If you have only one Organization, it will search for all AP in the
organization and create a csv named for the network

If you have multiple Organizations, it will ask you which org to run against

API Key
requires you to have your API key in env vars as 'MERAKI_DASHBOARD_API_KEY'

'''

net_list = {}
p = Path.home()
loc = p / 'Documents' / 'BSSID'

dashboard = meraki.DashboardAPI(suppress_logging=True)


def Folder1():
    if not Path.is_dir(loc):
        Path.mkdir(loc)


def Folder2(loc2):
    if not Path.is_dir(loc2):
        Path.mkdir(loc2)


def getOrgs():
    orgs = dashboard.organizations.getOrganizations()
    if len(orgs) == 1:
        for dic in orgs:
            orgID = dic['id']
            orgName = dic['name']
            loc2 = loc / orgName
            Folder2(loc2)
            getNetworks(orgID, orgName)
    else:
        org_list = {}
        for dic in orgs:
            org_list[dic['id']] = dic['name']
        orgID = input(f'Please type in the number of the Organization name '
            f'that you would like to query {json.dumps(org_list, indent=4)}' "\n")
        orgName = org_list.get(orgID)
        loc2 = loc / orgName
        Folder2(loc2)
        getNetworks(orgID, orgName)


def getNetworks(orgID, orgName):
    networks = dashboard.organizations.getOrganizationNetworks(
        orgID, total_pages='all')
    for dic in networks:
        if 'wireless' in dic['productTypes']:
            net_list[dic['id']] = dic['name']
    for k, v in net_list.items():
        net_id = k
        net_name = v
        getAP(net_id, net_name, orgName)


def getAP(net_id, net_name, orgName):
    devices = dashboard.networks.getNetworkDevices(net_id)
    ap_list = {}
    for dic in devices:
        model = dic['model'][:2]
        if model == 'MR' or model == 'CW':
            if dic.get('name') is None:
                ap_list[dic['mac']] = dic['serial']
            else:
                ap_list[dic['name']] = dic['serial']
    getBss(net_name, orgName, ap_list)


def getBss(net_name, orgName, ap_list):
    bss = f'{loc}/{orgName}/{net_name}.csv'
    with open(bss, mode='w') as f:
        f.write(f"AP Name , SSID Name , Frequency , BSSID" + "\n")
        for k, v in ap_list.items():
            response = dashboard.wireless.getDeviceWirelessStatus(v)
            for data in response['basicServiceSets']:
                good = data['enabled']
                if good is True:
                    f.write(f"{k} , {data['ssidName']} , {data['band']}\
                         , {data['bssid']}" + "\n")
    print(f'Your file {net_name}.csv has been creeated in {loc} / {orgName}')


if __name__ == '__main__':
    Folder1()
    getOrgs()
