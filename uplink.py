#!/usr/bin/python3

'''
=== PREREQUISITES ===
Run in Python 3

Install requests library, via macOS terminal:
pip3 install requests

login.py has these two lines, with the API key from your Dashboard profile (upper-right email login > API access), and organization ID to call (https://dashboard.meraki.com/api/v0/organizations); separated into different file for security.
api_key = '[API_KEY]'
org_id = '[ORG_ID]'

Usage:
python3 uplink.py

=== DESCRIPTION ===
Iterates through all devices, and exports to two CSV files: one for appliance (MX, Z1, Z3, vMX100) networks to collect WAN uplink information, and the other for all other devices (MR, MS, MC, MV) with local uplink info.

Possible statuses:
Active: active and working WAN port
Ready: standby but working WAN port, not the preferred WAN port
Failed: was working at some point but not anymore
Not connected: nothing was ever connected, no cable plugged in
For load balancing, both WAN links would show active.

For any questions, please contact Shiyue (Shay) Cheng, shiychen@cisco.com
'''

import csv
import datetime
import json
import requests
import sys

def get_network_name(network_id, networks):
    return [element for element in networks if network_id == element['id']][0]['name']


if __name__ == '__main__':
    # Import API key and org ID from login.py
    try:
        import login
        (API_KEY, ORG_ID) = (login.api_key, login.org_id)
    except ImportError:
        API_KEY = input('Enter your Dashboard API key: ')
        ORG_ID = input('Enter your organization ID: ')


    # Find all appliance networks (MX, Z1, Z3, vMX100)
    session = requests.session()
    headers = {'X-Cisco-Meraki-API-Key': API_KEY, 'Content-Type': 'application/json'}
    try:
        name = json.loads(session.get('https://dashboard.meraki.com/api/v0/organizations/' + ORG_ID, headers=headers).text)['name']
    except:
        sys.exit('Incorrect API key or org ID, as no valid data returned')
    networks = json.loads(session.get('https://dashboard.meraki.com/api/v0/organizations/' + ORG_ID + '/networks', headers=headers).text)
    inventory = json.loads(session.get('https://dashboard.meraki.com/api/v0/organizations/' + ORG_ID + '/inventory', headers=headers).text)
    appliances = [device for device in inventory if device['model'][:2] in ('MX', 'Z1', 'Z3', 'vM') and device['networkId'] is not None]
    devices = [device for device in inventory if device not in appliances and device['networkId'] is not None]


    # Output CSV of appliances' info
    today = datetime.date.today()
    csv_file1 = open(name + ' appliances -' + str(today) + '.csv', 'w', encoding='utf-8')
    fieldnames = ['Network', 'Device', 'Serial', 'MAC', 'Model', 'WAN1 Status', 'WAN1 IP', 'WAN1 Gateway', 'WAN1 Public IP', 'WAN1 DNS', 'WAN1 Static', 'WAN2 Status', 'WAN2 IP', 'WAN2 Gateway', 'WAN2 Public IP', 'WAN2 DNS', 'WAN2 Static', 'Cellular Status', 'Cellular IP', 'Cellular Provider', 'Cellular Public IP', 'Cellular Model', 'Cellular Connection', 'Performance']
    writer = csv.DictWriter(csv_file1, fieldnames=fieldnames, restval='')
    writer.writeheader()

    # Iterate through appliances
    for appliance in appliances:
        network_name = get_network_name(appliance['networkId'], networks)
        device_name = json.loads(session.get('https://dashboard.meraki.com/api/v0/networks/' + appliance['networkId'] + '/devices/' + appliance['serial'], headers=headers).text)['name']
        try:
            perfscore = json.loads(session.get('https://dashboard.meraki.com/api/v0/networks/' + appliance['networkId'] + '/devices/' + appliance['serial'] + '/performance', headers=headers).text)['perfScore']
        except:
            perfscore = None
        try:
            print('Found appliance ' + device_name)
        except:
            print('Found appliance ' + appliance['serial'])
        uplinks_info = dict.fromkeys(['WAN1', 'WAN2', 'Cellular'])
        uplinks_info['WAN1'] = dict.fromkeys(['interface', 'status', 'ip', 'gateway', 'publicIp', 'dns', 'usingStaticIp'])
        uplinks_info['WAN2'] = dict.fromkeys(['interface', 'status', 'ip', 'gateway', 'publicIp', 'dns', 'usingStaticIp'])
        uplinks_info['Cellular'] = dict.fromkeys(['interface', 'status', 'ip', 'provider', 'publicIp', 'model', 'connectionType'])
        uplinks = json.loads(session.get('https://dashboard.meraki.com/api/v0/networks/' + appliance['networkId'] + '/devices/' + appliance['serial'] + '/uplink', headers=headers).text)
        for uplink in uplinks:
            if uplink['interface'] == 'WAN 1':
                for key in uplink.keys():
                    uplinks_info['WAN1'][key] = uplink[key]
            elif uplink['interface'] == 'WAN 2':
                for key in uplink.keys():
                    uplinks_info['WAN2'][key] = uplink[key]
            elif uplink['interface'] == 'Cellular':
                for key in uplink.keys():
                    uplinks_info['Cellular'][key] = uplink[key]
        if perfscore != None:
            writer.writerow({'Network': network_name, 'Device': device_name, 'Serial': appliance['serial'], 'MAC': appliance['mac'], 'Model': appliance['model'], 'WAN1 Status': uplinks_info['WAN1']['status'], 'WAN1 IP': uplinks_info['WAN1']['ip'], 'WAN1 Gateway': uplinks_info['WAN1']['gateway'], 'WAN1 Public IP': uplinks_info['WAN1']['publicIp'], 'WAN1 DNS': uplinks_info['WAN1']['dns'], 'WAN1 Static': uplinks_info['WAN1']['usingStaticIp'], 'WAN2 Status': uplinks_info['WAN2']['status'], 'WAN2 IP': uplinks_info['WAN2']['ip'], 'WAN2 Gateway': uplinks_info['WAN2']['gateway'], 'WAN2 Public IP': uplinks_info['WAN2']['publicIp'], 'WAN2 DNS': uplinks_info['WAN2']['dns'], 'WAN2 Static': uplinks_info['WAN2']['usingStaticIp'], 'Cellular Status': uplinks_info['Cellular']['status'], 'Cellular IP': uplinks_info['Cellular']['ip'], 'Cellular Provider': uplinks_info['Cellular']['provider'], 'Cellular Public IP': uplinks_info['Cellular']['publicIp'], 'Cellular Model': uplinks_info['Cellular']['model'], 'Cellular Connection': uplinks_info['Cellular']['connectionType'], 'Performance': perfscore})
        else:
            writer.writerow({'Network': network_name, 'Device': device_name, 'Serial': appliance['serial'], 'MAC': appliance['mac'], 'Model': appliance['model'], 'WAN1 Status': uplinks_info['WAN1']['status'], 'WAN1 IP': uplinks_info['WAN1']['ip'], 'WAN1 Gateway': uplinks_info['WAN1']['gateway'], 'WAN1 Public IP': uplinks_info['WAN1']['publicIp'], 'WAN1 DNS': uplinks_info['WAN1']['dns'], 'WAN1 Static': uplinks_info['WAN1']['usingStaticIp'], 'WAN2 Status': uplinks_info['WAN2']['status'], 'WAN2 IP': uplinks_info['WAN2']['ip'], 'WAN2 Gateway': uplinks_info['WAN2']['gateway'], 'WAN2 Public IP': uplinks_info['WAN2']['publicIp'], 'WAN2 DNS': uplinks_info['WAN2']['dns'], 'WAN2 Static': uplinks_info['WAN2']['usingStaticIp'], 'Cellular Status': uplinks_info['Cellular']['status'], 'Cellular IP': uplinks_info['Cellular']['ip'], 'Cellular Provider': uplinks_info['Cellular']['provider'], 'Cellular Public IP': uplinks_info['Cellular']['publicIp'], 'Cellular Model': uplinks_info['Cellular']['model'], 'Cellular Connection': uplinks_info['Cellular']['connectionType']})
    csv_file1.close()


    # Output CSV of all other devices' info
    csv_file2 = open(name + ' other devices -' + str(today) + '.csv', 'w', encoding='utf-8')
    fieldnames = ['Network', 'Device', 'Serial', 'MAC', 'Model', 'Status', 'IP', 'Gateway', 'Public IP', 'DNS', 'VLAN', 'Static']
    writer = csv.DictWriter(csv_file2, fieldnames=fieldnames, restval='')
    writer.writeheader()

    # Iterate through all other devices
    for device in devices:
        network_name = get_network_name(device['networkId'], networks)
        device_name = json.loads(session.get('https://dashboard.meraki.com/api/v0/networks/' + device['networkId'] + '/devices/' + device['serial'], headers=headers).text)['name']
        try:
            print('Found device ' + device_name)
        except:
            print('Found device ' + device['serial'])
        uplink_info = dict.fromkeys(['interface', 'status', 'ip', 'gateway', 'publicIp', 'dns', 'vlan', 'usingStaticIp'])
        uplink = json.loads(session.get('https://dashboard.meraki.com/api/v0/networks/' + device['networkId'] + '/devices/' + device['serial'] + '/uplink', headers=headers).text)
        
        # Blank uplink for devices that are down or meshed APs
        if uplink == []:
            continue
        # All other devices have single uplink
        else:
            uplink = uplink[0]
        for key in uplink.keys():
            uplink_info[key] = uplink[key]
        writer.writerow({'Network': network_name, 'Device': device_name, 'Serial': device['serial'], 'MAC': device['mac'], 'Model': device['model'], 'Status': uplink_info['status'], 'IP': uplink_info['ip'], 'Gateway': uplink_info['gateway'], 'Public IP': uplink_info['publicIp'], 'DNS': uplink_info['dns'], 'VLAN': uplink_info['vlan'], 'Static': uplink_info['usingStaticIp']})
    csv_file2.close()
