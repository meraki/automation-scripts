READ_ME = """
=== PREREQUISITES ===
Use with Meraki Python SDK @ github.com/meraki/dashboard-api-python/ & install required libraries with
pip[3] install -r requirements.txt 

=== DESCRIPTION ===
This script iterates through a dashboard organization and backs up the configuration for the org, networks & templates, 
and devices, for the config settings that have API endpoint support.

=== USAGE ===
python[3] backup_configs.py -o <old_org> [-k <api_key>] [-t <tag>] [-y]
API key can, and is recommended to, be set as an environment variable named MERAKI_DASHBOARD_API_KEY. 
If the optional tag is provided, then filter only for those networks with the tag, along with those networks' devices.
Optional flag -y to automatically continue to run without waiting for user confirmation.
"""


import asyncio
import csv
from datetime import datetime
import getopt
import json
import math
import os
import sys

import meraki
import meraki.aio
import requests
import yaml


# User configurable constants
BACKUP_FORMAT = 'json'  # possible options of ('json', 'yaml', 'both') to specify output format
GET_OPERATION_MAPPINGS_FILE = 'backup_GET_operations.csv'  # path to input file, listing GET operations of API calls
DEFAULT_CONFIGS_DIRECTORY = 'defaults'  # path to folder where default configurations (for a new network) are stored

# Global variables; DO NOT MODIFY
ORG_ID = None
TOTAL_CALLS = 0
COMPLETED_OPERATIONS = set()
DEFAULT_CONFIGS = []
DEVICES = NETWORKS = TEMPLATES = []


# Helper function that returns type of device based on model number
def device_type(model):
    family = model[:2]
    if family == 'MR':
        return 'wireless'
    elif family == 'MS':
        return 'switch'
    elif family == 'MV':
        return 'camera'
    elif family == 'MG':
        return 'cellularGateway'
    elif family in ('MX', 'vM', 'Z3', 'Z1'):
        return 'appliance'
    else:
        return None


# Helper function to format the file name generated from the operation ID
def generate_file_name(operation):
    new_name = ''
    suffix = operation.replace('getOrganization', '').replace('getDevice', '').replace('getNetwork', '')
    for letter in suffix:
        if letter.isupper():
            new_name += '_' + letter.lower()
        else:
            new_name += letter
    return new_name[1:] if new_name and new_name[0] == '_' else new_name


# Helper function to format the scope, which is the middle part of the actual API function call
def generate_scope(tags):
    # first = tags[0]
    # scope = ''
    # for letter in first:
    #     if letter.isupper():
    #         scope += '_' + letter.lower()
    #     else:
    #         scope += letter
    return tags[0]

# Save data to JSON and/or YAML output files
def save_data(file, data, path=''):
    if path and path[-1] != '/':  # add trailing slash if missing
        path += '/'
    if data:  # check if there is actually data
        if type(data) != dict or (type(data) == dict and any(data.values())):  # non-empty values in objects

            # Check if config same as a default file, or null rfProfileId for getDeviceWirelessRadioSettings
            proceed_saving = False
            if type(data) == dict and set(data.keys()) == {'rfProfileId', 'serial'}:
                if data['rfProfileId']:
                    proceed_saving = True
            elif data not in DEFAULT_CONFIGS:
                proceed_saving = True

            if proceed_saving:
                if BACKUP_FORMAT in ('both', 'json'):
                    with open(f'{path}{file}.json', 'w') as fp:
                        json.dump(data, fp, indent=4)
                if BACKUP_FORMAT in ('both', 'yaml'):
                    with open(f'{path}{file}.yaml', 'w') as fp:
                        yaml.dump(data, fp, explicit_start=True, default_flow_style=False, sort_keys=False)


# Asynchronous function to make REST API call
async def async_call(dashboard, call):
    global TOTAL_CALLS
    TOTAL_CALLS += 1

    operation = call['operation']
    function_call = call['function_call']
    file_name = call['file_name']
    file_path = call['file_path']

    serial = net_id = profile_id = identifier = None
    if 'serial' in call:
        serial = call['serial']
        identifier = serial
    if 'net_id' in call:
        net_id = call['net_id']
        identifier = net_id
    if 'profile_id' in call:
        profile_id = call['profile_id']
        identifier = profile_id

    try:
        response = await eval(function_call)
    except meraki.AsyncAPIError as e:
        print(f'Error with {identifier}: {e}')
        return None
    else:
        return {
            'operation': operation,
            'response': response,
            'file_name': file_name,
            'file_path': file_path,
            'net_id': net_id,
            'serial': serial,
            'profile_id': profile_id,
        }


# Make multiple API calls asynchronously
async def make_calls(dashboard, calls):
    global COMPLETED_OPERATIONS, DEVICES, NETWORKS, TEMPLATES

    tasks = [async_call(dashboard, call) for call in calls]
    for task in asyncio.as_completed(tasks):
        results = await task
        if results:
            operation = results['operation']
            response = results['response']
            file_name = results['file_name']
            file_path = results['file_path']

            save_data(file_name, response, file_path)

            # Update global variables
            COMPLETED_OPERATIONS.add(operation)
            if operation == 'getOrganizationNetworks':
                NETWORKS = response
            elif operation == 'getOrganizationConfigTemplates':
                TEMPLATES = response
            elif operation == 'getOrganizationDevices':
                DEVICES = response


# Backup configuration for organization
async def backup_org(dashboard, endpoints):
    calls = []

    for ep in endpoints:
        logic = ep['Logic']
        operation = ep['operationId']
        file_name = generate_file_name(operation)
        tags = eval(ep['tags'])
        scope = generate_scope(tags)
        function_call = f'dashboard.{scope}.{operation}(ORG_ID)'

        if operation.startswith('getOrganization') and logic not in ('skipped', 'script'):
            # Iterate through all pages for paginated endpoints
            params = [p['name'] for p in eval(ep['parameters'])]
            if 'perPage' in params:
                function_call = function_call[:-1] + ", total_pages='all')"

            calls.append(
                {
                    'operation': operation,
                    'function_call': function_call,
                    'file_name': file_name,
                    'file_path': '',
                }
            )

    await make_calls(dashboard, calls)


# Backup configuration for devices
async def backup_devices(dashboard, endpoints, devices):
    os.mkdir('devices')
    calls = []

    for device in devices:
        serial = device['serial']
        model = device['model']
        family = device_type(model)
        file_path = f'devices/{model} - {serial}'
        os.mkdir(file_path)

        for ep in endpoints:
            logic = ep['Logic']
            operation = ep['operationId']
            file_name = generate_file_name(operation)
            tags = eval(ep['tags'])
            scope = generate_scope(tags)
            function_call = f'dashboard.{scope}.{operation}(serial)'

            if operation.startswith('getDevice') and logic not in ('skipped', 'script') and \
                    ((scope == 'devices' and family in ('wireless', 'switch', 'appliance')) or (scope == family)):
                calls.append(
                    {
                        'operation': operation,
                        'function_call': function_call,
                        'file_name': file_name,
                        'file_path': file_path,
                        'serial': serial,
                    }
                )

    await make_calls(dashboard, calls)


# Backup configuration for networks and templates
async def backup_networks(dashboard, endpoints, networks, devices):
    os.mkdir('networks')
    calls = []

    for network in networks:
        net_name = network['name']
        net_id = network['id']
        products = network['productTypes']
        template = True if 'tags' not in network else False
        bound = True if 'configTemplateId' in network else False
        file_path = f'networks/{net_name} - {net_id}'
        os.mkdir(file_path)

        for ep in endpoints:
            logic = ep['Logic']
            operation = ep['operationId']
            file_name = generate_file_name(operation)
            tags = eval(ep['tags'])
            scope = generate_scope(tags)
            function_call = f'dashboard.{scope}.{operation}(net_id)'

            # API calls that apply to networks, or the majority of settings that also work for templates
            if operation.startswith('getNetwork') and logic not in ('skipped', 'script', 'ssids'):

                # Check whether endpoint applies to the network based on its component products
                proceed = False
                if scope == 'networks':
                    if logic not in ('', 'non-template', 'non-bound'):
                        if set(logic.split(',')).intersection(products):
                            proceed = True
                    else:
                        proceed = True
                elif scope in products:
                    proceed = True

                # Check for template/bound logic
                if proceed:
                    if (not template and not bound) or (bound and logic != 'non-bound') or \
                            (template and logic != 'non-template'):
                        calls.append(
                            {
                                'operation': operation,
                                'function_call': function_call,
                                'file_name': file_name,
                                'file_path': file_path,
                                'net_id': net_id,
                            }
                        )

            # For getNetworkWirelessRfProfiles, which has an optional parameter includeTemplateProfiles
            elif operation == 'getNetworkWirelessRfProfiles' and 'wireless' in products:
                if bound:
                    function_call = function_call[:-1] + ', includeTemplateProfiles=True)'
                calls.append(
                    {
                        'operation': operation,
                        'function_call': function_call,
                        'file_name': file_name,
                        'file_path': file_path,
                        'net_id': net_id,
                    }
                )

    await make_calls(dashboard, calls)


# Backup configuration for appliances VLANs & VLAN ports, or single LAN network
async def backup_appliance_vlans(dashboard, networks):
    calls = []

    appliance_networks = [n for n in networks if 'appliance' in n['productTypes']]
    for network in appliance_networks:
        net_name = network['name']
        net_id = network['id']

        file_path = f'networks/{net_name} - {net_id}'

        # VLANs enabled, as presence of the vlans_settings file indicates non-default configuration
        if os.path.exists(f'{file_path}/appliance_vlans_settings.json'):
            operations = ['getNetworkApplianceVlans', 'getNetworkAppliancePorts']
        else:
            operations = ['getNetworkApplianceSingleLan']

        # Make possibly multiple API calls
        scope = 'appliance'
        for operation in operations:
            file_name = generate_file_name(operation)
            function_call = f'dashboard.{scope}.{operation}(net_id)'

            calls.append(
                {
                    'operation': operation,
                    'function_call': function_call,
                    'file_name': file_name,
                    'file_path': file_path,
                    'net_id': net_id,
                }
            )

    await make_calls(dashboard, calls)


# Backup configuration for configuration templates' switch profiles
async def backup_ms_profiles(dashboard, templates):
    calls = []

    switch_templates = [t for t in templates if 'switch' in t['productTypes']]
    for template in switch_templates:
        template_name = template['name']
        net_id = template['id']

        file_path = f'networks/{template_name} - {net_id}'

        operation = 'getOrganizationConfigTemplateSwitchProfiles'
        file_name = f'{generate_file_name(operation)}'
        tags = ['switch', 'configure', 'configTemplates', 'profiles']
        scope = generate_scope(tags)
        function_call = f'dashboard.{scope}.{operation}(ORG_ID, net_id)'

        calls.append(
            {
                'operation': operation,
                'function_call': function_call,
                'file_name': file_name,
                'file_path': file_path,
                'net_id': net_id,
            }
        )

    await make_calls(dashboard, calls)


# Backup configuration for configuration templates' switch profiles' ports
async def backup_ms_profile_ports(dashboard, templates):
    calls = []

    switch_templates = [t for t in templates if 'switch' in t['productTypes']]
    for template in switch_templates:
        template_name = template['name']
        net_id = template['id']

        file_path = f'networks/{template_name} - {net_id}'

        if os.path.exists(f'{file_path}/config_template_switch_profiles.json'):
            with open(f'{file_path}/config_template_switch_profiles.json') as fp:
                config = json.load(fp)

            for profile in config:
                profile_id = profile['switchProfileId']
                operation = 'getOrganizationConfigTemplateSwitchProfilePorts'
                file_name = f'{generate_file_name(operation)}_{profile_id}'
                tags = ['switch', 'configure', 'configTemplates', 'profiles', 'ports']
                scope = generate_scope(tags)
                function_call = f'dashboard.{scope}.{operation}(ORG_ID, net_id, profile_id)'

                calls.append(
                    {
                        'operation': operation,
                        'function_call': function_call,
                        'file_name': file_name,
                        'file_path': file_path,
                        'net_id': net_id,
                        'profile_id': profile_id,
                    }
                )

    await make_calls(dashboard, calls)


# Backup configuration for SSID-specific settings
async def backup_mr_ssids(dashboard, endpoints, networks):
    calls = []

    wireless_networks = [n for n in networks if 'wireless' in n['productTypes']]
    for network in wireless_networks:
        template = True if 'tags' not in network else False
        bound = True if 'configTemplateId' in network else False

        # Filter for those SSIDs that are configured (without the string "Unconfigured" in the name)
        net_name = network['name']
        net_id = network['id']

        file_path = f'networks/{net_name} - {net_id}'

        with open(f'{file_path}/wireless_ssids.json') as fp:
            config = json.load(fp)
        config_ssids = ['Unconfigured' not in ssid['name'] for ssid in config]
        for num in range(0, 15):
            if config_ssids[num]:
                for ep in endpoints:
                    logic = ep['Logic']
                    operation = ep['operationId']
                    file_name = f'{generate_file_name(operation)}_ssid_{num}'
                    tags = eval(ep['tags'])
                    scope = generate_scope(tags)
                    function_call = f'dashboard.{scope}.{operation}(net_id, {num})'

                    if logic == 'ssids' and tags:
                        process_call = True
                        # process_call = False
                        # if operation == 'getNetworkWirelessSsidTrafficShapingRules':
                        #     if not template and not bound:
                        #         process_call = True
                        # else:
                        #     process_call = True

                        if process_call:
                            calls.append(
                                {
                                    'operation': operation,
                                    'function_call': function_call,
                                    'file_name': file_name,
                                    'file_path': file_path,
                                    'net_id': net_id,
                                }
                            )

    await make_calls(dashboard, calls)


# Backup configuration for Bluetooth device settings for networks using unique BLE advertising
async def backup_ble_settings(dashboard, networks, devices):
    calls = []

    wireless_networks = [n for n in networks if 'wireless' in n['productTypes']]
    for network in wireless_networks:
        # Filter for those networks using unique BLE advertising
        net_name = network['name']
        net_id = network['id']

        file_path = f'networks/{net_name} - {net_id}'

        if os.path.exists(f'{file_path}/wireless_bluetooth_settings.json'):
            with open(f'{file_path}/wireless_bluetooth_settings.json') as fp:
                config = json.load(fp)
            if config['advertisingEnabled'] and config['majorMinorAssignmentMode'] == 'Unique':
                for d in devices:
                    if d['networkId'] == net_id and device_type(d['model']) == 'wireless':
                        serial = d['serial']
                        operation = 'getDeviceWirelessBluetoothSettings'
                        file_name = f'{generate_file_name(operation)}_{serial}'
                        tags = ['wireless', 'configure', 'bluetooth', 'settings']
                        scope = generate_scope(tags)
                        function_call = f'dashboard.{scope}.{operation}(serial)'

                        calls.append(
                            {
                                'operation': operation,
                                'function_call': function_call,
                                'file_name': file_name,
                                'file_path': file_path,
                                'serial': serial,
                            }
                        )

    await make_calls(dashboard, calls)


async def main_async(api_key, operations, endpoints, tag):
    global DEVICES, NETWORKS, TEMPLATES
    async with meraki.aio.AsyncDashboardAPI(api_key, maximum_concurrent_requests=3, maximum_retries=4,
                                               print_console=True, suppress_logging=False) as dashboard:
        # Backup org
        await backup_org(dashboard, endpoints)

        # Filter on networks/devices, if optional tag provided by user
        if tag:
            TEMPLATES = []
            NETWORKS = [n for n in NETWORKS if tag in n['tags']]
            DEVICES = [d for d in DEVICES if d['networkId'] in [n['id'] for n in NETWORKS]]

        # Backup devices
        await backup_devices(dashboard, endpoints, DEVICES)

        # Backup networks and configuration templates
        await backup_networks(dashboard, endpoints, NETWORKS + TEMPLATES, DEVICES)

        # Backup either VLANs or single-LAN addressing for appliances
        await backup_appliance_vlans(dashboard, NETWORKS + TEMPLATES)

        # Backup switch profiles for configuration templates
        await backup_ms_profiles(dashboard, TEMPLATES)

        # Backup switch profiles' ports for configuration templates
        await backup_ms_profile_ports(dashboard, TEMPLATES)

        # Backup SSID-specific settings for configured SSIDs
        await backup_mr_ssids(dashboard, endpoints, NETWORKS + TEMPLATES)

        # Backup Bluetooth device settings for networks using unique BLE advertising
        await backup_ble_settings(dashboard, NETWORKS, DEVICES)

    # Check any operations that were not used
    for ep in endpoints:
        if ep['Logic'] == 'skipped':
            operation = ep['operationId']
            COMPLETED_OPERATIONS.add(operation)
    unfinished = [op for op in operations if op['operationId'] not in COMPLETED_OPERATIONS]
    if unfinished:
        print(f'\n{len(unfinished)} API endpoints that were not called during this backup process:')
        for op in unfinished:
            print(op['operationId'])


def run_backup(api_key, org_id, filter_tag):
    global GET_OPERATION_MAPPINGS_FILE, DEFAULT_CONFIGS_DIRECTORY, DEFAULT_CONFIGS, ORG_ID, TOTAL_CALLS

    # Calculate total time
    start = datetime.now()

    # Get operations from current dashboard OpenAPI specification
    spec = requests.get('https://api.meraki.com/api/v1/openapiSpec').json()
    current_operations = []

    # Filter for just GET methods with corresponding POST/PUT configuration methods
    for uri in spec['paths']:
        methods = spec['paths'][uri]
        # for method in methods:
        #     current_operations.append(spec['paths'][uri][method])
        if 'get' in methods and ('post' in methods or 'put' in methods):
            current_operations.append(spec['paths'][uri]['get'])

    # Export current GET operations to spreadsheet; for comparison later to check for new operations that were not used
    output_file = open('current_GET_operations.csv', mode='w', newline='\n')
    field_names = ['operationId', 'tags', 'description', 'parameters']
    csv_writer = csv.DictWriter(output_file, field_names, quoting=csv.QUOTE_ALL, extrasaction='ignore')
    csv_writer.writeheader()
    for op in current_operations:
        csv_writer.writerow(op)
    output_file.close()

    # Read input mappings of backup GET operations, the actual list of API calls that will be made
    input_mappings = []
    with open(GET_OPERATION_MAPPINGS_FILE, encoding='utf-8-sig') as fp:
        csv_reader = csv.DictReader(fp)
        for row in csv_reader:
            input_mappings.append(row)

    # Read input folder of default configs
    os.chdir(DEFAULT_CONFIGS_DIRECTORY)
    files = os.listdir()
    for file in files:
        if '.json' in file:
            with open(file) as fp:
                data = json.load(fp)
            DEFAULT_CONFIGS.append(data)
    os.chdir('..')

    # Create folder structure
    # os.chdir('/tmp')
    time_now = datetime.now()
    backup_path = f'backup_{org_id}__{time_now:%Y-%m-%d_%H-%M-%S}'
    os.mkdir(backup_path)
    os.chdir(backup_path)

    # Run backup!
    ORG_ID = org_id
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main_async(api_key, current_operations, input_mappings, filter_tag))

    # Calculate total time
    end = datetime.now()
    time_ran = end - start
    return backup_path, time_ran, TOTAL_CALLS


# Calculate approximate time for script to run
def estimate_backup(api_key, org_id, filter_tag):
    try:
        # Estimate of API calls for org
        m = meraki.DashboardAPI(api_key, suppress_logging=True)
        networks = m.organizations.getOrganizationNetworks(org_id, total_pages='all')
        templates = m.organizations.getOrganizationConfigTemplates(org_id)
        devices = m.organizations.getOrganizationDevices(org_id, total_pages='all')
        if filter_tag:
            networks = [n for n in networks if filter_tag in n['tags']]
            templates = []
            devices = [d for d in devices if d['networkId'] in [n['id'] for n in networks]]
        org_calls = 19

        # Estimate of API calls for devices
        total_devices = len(devices)
        mr_devices = len([d for d in devices if d['model'][:2] == 'MR'])
        ms_devices = len([d for d in devices if d['model'][:2] == 'MS'])
        mv_devices = len([d for d in devices if d['model'][:2] == 'MV'])
        mg_devices = len([d for d in devices if d['model'][:2] == 'MG'])
        mx_devices = total_devices - mr_devices - ms_devices - mv_devices - mg_devices
        device_calls = (mr_devices + ms_devices + mx_devices) + mr_devices + 2 * ms_devices + 3 * mv_devices + 2 * mg_devices

        # Estimate of API calls for networks
        mr_networks = len([n for n in networks if 'wireless' in n['productTypes']]) + \
                      len([t for t in templates if 'wireless' in t['productTypes']])
        ms_networks = len([n for n in networks if 'switch' in n['productTypes']]) + \
                      len([t for t in templates if 'switch' in t['productTypes']])
        mx_networks = len([n for n in networks if 'appliance' in n['productTypes']]) + \
                      len([t for t in templates if 'appliance' in t['productTypes']])
        mg_networks = len([n for n in networks if 'cellularGateway' in n['productTypes']]) + \
                      len([t for t in templates if 'cellularGateway' in t['productTypes']])
        mv_networks = len([n for n in networks if 'camera' in n['productTypes']])
        network_calls = 19 * mr_networks + 22 * ms_networks + 32 * mx_networks + 6 * mg_networks + 4 * mv_networks

        total_calls = org_calls + device_calls + network_calls
        minutes = math.ceil(total_calls / 4 / 60)
        return total_calls, minutes
    except meraki.APIError:
        sys.exit('Please check that you have both the correct API key and org ID set.')


# Prints READ_ME help message for user to read
def print_help():
    lines = READ_ME.split('\n')
    for line in lines:
        print(f'# {line}')


# Parse command line arguments
def main(inputs):
    if len(inputs) == 0:
        print_help()
        sys.exit(2)
    else:
        api_key = org_id = filter_tag = auto_run = confirm = None

        try:
            opts, args = getopt.getopt(inputs, 'ho:k:t:y')
        except getopt.GetoptError:
            print_help()
            sys.exit(2)
        for opt, arg in opts:
            if opt == '-h':
                print_help()
                sys.exit(2)
            elif opt == '-o':
                org_id = arg
            elif opt == '-k':
                api_key = arg
            elif opt == '-t':
                filter_tag = arg
            elif opt == '-y':
                auto_run = True

        if org_id is None:
            print_help()
            sys.exit(2)
        else:
            calls, minutes = estimate_backup(api_key, org_id, filter_tag)
            minutes = f'{minutes} minutes' if minutes != 1 else '1 minute'
            message = f'Based on your org, it is estimated that around {calls:,} API calls will be made, '
            message += f'so should not take longer than about {minutes} to finish running.\n'
            message += 'Do you want to continue [Y/n]? '
            if not auto_run:
                confirm = input(message)
            if auto_run or confirm.upper() in ('Y', 'YES'):
                print()
                backup_path, time_ran, calls_made = run_backup(api_key, org_id, filter_tag)
                time_ran_min = time_ran.seconds // 60
                time_ran_min = f'{time_ran_min} minutes' if time_ran_min != 1 else '1 minute'
                time_ran_sec = time_ran.seconds % 60
                time_ran_sec = f'{time_ran_sec} seconds' if time_ran_sec != 1 else '1 second'
                message = f'\nThis backup process ended up making {calls_made:,} API calls, taking a total time of '
                message += f'{time_ran_min} {time_ran_sec}. The output can be found in the folder: {backup_path}'
                print(message)


if __name__ == '__main__':
    main(sys.argv[1:])
