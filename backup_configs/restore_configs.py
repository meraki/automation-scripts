#!/usr/bin/python3

"""
=== PREREQUISITES ===
Use with Meraki Python SDK @ github.com/meraki/dashboard-api-python/ & install required libraries with
pip[3] install -r requirements.txt

=== DESCRIPTION ===
This script creates new networks/templates and restores their configuration from a backup set of JSON files.
Settings that require a device to be present are not included, to safely not affect any running networks/devices.
See the input restore_operations.csv spreadsheet for full list of API endpoints that are requested.

=== USAGE ===
python[3] restore_configs.py -o <org_id> -d <backup_directory> [-k <api_key>]
API key can, and is recommended to, be set as an environment variable named MERAKI_DASHBOARD_API_KEY.
"""


import argparse
import csv
from datetime import datetime
import json
import os

import meraki

# INCLUDE THIS FILE LOCALLY
OPERATION_MAPPINGS_FILE = 'restore_operations.csv'  # path to input file, listing GET operations of API calls


def parse_arguments(parser):
    parser.add_argument('-o', '--org', help='Dashboard organization ID')
    parser.add_argument('-d', '--dir', help='Directory of backup configs')
    parser.add_argument('-k', '--key', help='Dashboard API key')
    parser.exit
    args = parser.parse_args()
    return args.org, args.dir, args.key


# Helper function to retrieve GET operation ID from saved config file
def return_get(file):
    name = file.replace('.json', '')
    if '_ssid_' in name:
        name = name[:name.rfind('_ssid_')]
    operation = 'getNetwork' + name[0].upper()
    index = 1
    while index <= len(name) - 1:
        if name[index] == '_':
            operation += name[index + 1].upper()
            index += 2
        else:
            operation += name[index]
            index += 1
    return operation


# Create networks & configuration templates from backup
def create_networks(dashboard, org_id):
    # Read from backup
    time_now = datetime.isoformat(datetime.utcnow())[5:16].replace(':', '-')
    backup = []
    if 'networks.json' in os.listdir():
        with open('networks.json') as fp:
            backup.extend(json.load(fp))
    if 'config_templates.json' in os.listdir():
        with open('config_templates.json') as fp:
            backup.extend(json.load(fp))

    # Check for networks' configs
    network_folders_names = [name.split(' - ')[0] for name in os.listdir('networks') if ' - ' in name]
    backup_set = [n for n in backup if n['name'] in network_folders_names]

    # Iterate through list of backup set, creating new networks
    for net in backup_set:
        net['old_name'] = net['name']
        net['name'] += f' @{time_now}'

        # Create new copy of network
        if 'tags' in net:
            net['tags'].append('BACKUP')
            try:
                n = dashboard.organizations.createOrganizationNetwork(**net)
                net['new_id'] = n['id']
                print(f'Networks > created "{net["name"]}" with ID {net["new_id"]}')

            except meraki.APIError as e:
                print(f'Networks > error attempting to create "{net["name"]}": {e}')

        # Create new copy of template
        else:
            net['organizationId'] = org_id
            try:
                n = dashboard.organizations.createOrganizationConfigTemplate(**net)
                net['new_id'] = n['id']
                print(f'Templates > created "{net["name"]}" with ID {net["new_id"]}')

            except meraki.APIError as e:
                print(f'Templates > error attempting to create "{net["name"]}": {e}')

    return backup_set


# Transform data as needed before making API call
def transform(net, data, operation, params=None, path_id=None):
    payload = f'networkId="{net["new_id"]}"'
    if 'networkId' in data:
        data.pop('networkId')
    extra_op = None

    # Transform data as needed for specific endpoints
    # updateNetworkApplianceSingleLan - logic so VLAN1 deletion later is skipped (moot point)
    if operation == 'updateNetworkApplianceSingleLan':
        net['single_lan'] = True

    # createNetworkApplianceVlan - account for default VLAN1 that exists already for newly-created networks
    elif operation == 'createNetworkApplianceVlan' and data['id'] == 1:
        operation = 'updateNetworkApplianceVlan'
        net['vlan1_updated'] = True

    # createNetworkApplianceVlan - DHCP parameters need to be set via PUT, and not initial POST
    elif operation == 'createNetworkApplianceVlan':
        if set(data.keys()).intersection(['fixedIpAssignments', 'reservedIpRanges', 'dnsNameservers', 'dhcpHandling',
                                          'dhcpLeaseTime', 'dhcpBootOptionsEnabled', 'dhcpBootNextServer',
                                          'dhcpBootFilename', 'dhcpOptions']):
            extra_op = 'updateNetworkApplianceVlan'

    # updateNetworkAppliancePort - account for different key between value and response (actually skipped for now)
    elif operation == 'updateNetworkAppliancePort':
        data['portId'] = data.pop('number')

    # updateNetworkApplianceContentFiltering - account for different in PUT format payload from GET
    elif operation == 'updateNetworkApplianceContentFiltering':
        blocked_categories = []
        for category in data['blockedUrlCategories']:
            blocked_categories.append(category['id'])
        data['blockedUrlCategories'] = blocked_categories

    # updateNetworkApplianceFirewallL3FirewallRules - remove default allow rule at end of array
    elif operation == 'updateNetworkApplianceFirewallL3FirewallRules':
        data['rules'] = data['rules'][:-1]

    # updateNetworkApplianceFirewallCellularFirewallRules - remove default allow rule at end of array
    elif operation == 'updateNetworkApplianceFirewallCellularFirewallRules':
        data['rules'] = data['rules'][:-1]

    # updateNetworkSwitchAccessControlLists - remove default ACL rule at end of array
    elif operation == 'updateNetworkSwitchAccessControlLists':
        data['rules'] = data['rules'][:-1]

    # createNetworkSwitchQosRule - vlan required as second argument after network
    elif operation == 'createNetworkSwitchQosRule':
        payload += f', vlan={data.pop("vlan")}'

    # updateNetworkSwitchQosRulesOrder - use IDs generated from createNetworkSwitchQosRule POSTs
    elif operation == 'updateNetworkSwitchQosRulesOrder':
        data['ruleIds'] = net['switch_qos_rules_order']

    # updateNetworkWirelessSsid - only update SSID slots that are configured
    elif operation == 'updateNetworkWirelessSsid':
        if 'Unconfigured' in data['name']:
            if 'configured_ssids' not in net:
                net['configured_ssids'] = [data['number']]
            else:
                net['configured_ssids'].append(data['number'])
            return net, operation, None, extra_op
        # not include encryptionMode if authMode != psk
        if data['authMode'] != 'psk' and 'encryptionMode' in data:
            data.pop('encryptionMode')
        # radiusFailoverPolicy returning null in GET
        if 'radiusFailoverPolicy' in data and data['radiusFailoverPolicy'] is None:
            data['radiusFailoverPolicy'] = 'Deny access'
        # radiusLoadBalancingPolicy returning null in GET
        if 'radiusLoadBalancingPolicy' in data and data['radiusLoadBalancingPolicy'] is None:
            data['radiusLoadBalancingPolicy'] = 'Strict priority order'
        # radiusServers secret not returned in GET
        if 'radiusServers' in data:
            for server in data['radiusServers']:
                server['secret'] = 'ciscomeraki'

    # updateNetworkWirelessSsidFirewallL3FirewallRules - remove two rules at end of array & convert local LAN rule
    elif operation == 'updateNetworkWirelessSsidFirewallL3FirewallRules':
        data['allowLanAccess'] = True if data['rules'][-2]['policy'] == 'allow' else False
        data['rules'] = data['rules'][:-2]

    # updateNetworkWirelessSsidSplashSettings - remove splash page file entities
    elif operation == 'updateNetworkWirelessSsidSplashSettings':
        if data['splashMethod'] == "None":
            return net, operation, None, extra_op
        data.pop('splashLogo')
        data.pop('splashImage')
        data.pop('splashPrepaidFront')

    # Change ID keys' names as needed
    if 'create' not in operation and path_id:
        data[path_id] = data.pop('id')

    # Construct payload for function call
    for k, v in data.items():
        if not params or (params and k in params):
            if type(v) == str:
                payload += f', {k}="{v}"'
            else:
                payload += f', {k}={v}'

    return net, operation, payload, extra_op


# Process Dashboard API call
def make_api_call(dashboard, net, data, scope, operation, params=None, path_id=None):
    net, operation, payload, extra_op = transform(net, data, operation, params, path_id)
    function_call = f'dashboard.{scope}.{operation}({payload})'

    try:
        if payload:
            response = eval(function_call)
        if extra_op:
            net, operation, payload, extra_op = transform(net, data, extra_op, params, path_id)
            function_call = f'dashboard.{scope}.{operation}({payload})'
            response = eval(function_call)

        # createNetworkSwitchQosRule - need IDs from created entities for updateNetworkSwitchQosRulesOrder
        if operation == 'createNetworkSwitchQosRule':
            if 'switch_qos_rules_order' not in net:
                net['switch_qos_rules_order'] = [response['id']]
            else:
                net['switch_qos_rules_order'].append(response['id'])

    except meraki.APIError as e:
        print(f'{net["name"]} > error attempting operation {operation} with function call {function_call}: {e}')


# Restore individual setting
def restore(endpoint, dashboard, net, data):
    if endpoint['restoreOperation']:
        logic = endpoint['Logic'].split(',') if endpoint['Logic'] else None
        operation = endpoint['restoreOperation']
        tags = eval(endpoint['tags'])
        scope = tags[0]
        params = eval(endpoint['parameters']) if endpoint['parameters'] else None
        path_id = endpoint['pathId']

        # Skip processing for certain endpoints
        if logic == ['skipped']:
            pass

        # Skip endpoints that only apply to certain network types
        elif logic and logic != ['skipped'] and not set(logic).intersection(net['productTypes']):
            pass

        # Data is an object
        elif type(data) == dict:
            make_api_call(dashboard, net, data, scope, operation, params, path_id)

        # Data is an array
        elif type(data) == list:
            for element in data:
                make_api_call(dashboard, net, element, scope, operation, params, path_id)


# Restore settings to network from backup
def restore_settings(operations, dashboard, net):
    for endpoint in operations:
        for file in os.listdir(f'networks/{net["old_name"]} - {net["id"]}'):
            if return_get(file) == endpoint['operationId']:
                with open(f'networks/{net["old_name"]} - {net["id"]}/{file}') as fp:
                    data = json.load(fp)

                    if '_ssid_' in file:  # for any getNetworkWirelessSsid* endpoints
                        data['number'] = file[file.rfind('_ssid_') + 6:file.rfind('.json')]

                    restore(endpoint, dashboard, net, data)

    # Remove VLAN1 (created by default for a new network) if not in backup
    if 'single_lan' not in net and 'vlan1_updated' not in net and 'appliance' in net['productTypes']:
        make_api_call(dashboard, net, {'vlanId': 1}, 'appliance', 'deleteNetworkApplianceVlan')


def main():
    # Process input parameters
    parser = argparse.ArgumentParser()
    org_id, backup_dir, api_key = parse_arguments(parser)
    if not (org_id and backup_dir):
        parser.exit(2, parser.print_help())

    # Read input mappings of restore operations
    input_mappings = []
    with open(OPERATION_MAPPINGS_FILE, encoding='utf-8-sig') as fp:
        csv_reader = csv.DictReader(fp)
        for row in csv_reader:
            input_mappings.append(row)

    # Create new networks & configuration templates
    dashboard = meraki.DashboardAPI(api_key)
    os.chdir(backup_dir)
    backup_set = create_networks(dashboard, org_id)

    # Configure settings for each network
    for net in backup_set:
        restore_settings(input_mappings, dashboard, net)


if __name__ == '__main__':
    main()
