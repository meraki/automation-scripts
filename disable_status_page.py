#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3.6+

Install the requests & Meraki Python modules:
pip[3] install --upgrade requests
pip[3] install --upgrade meraki

=== DESCRIPTION ===
This script iterates through a dashboard org's templates and updates the
appliances' allowed remote IPs for the web service (on Firewall page) to
"blocked"/"None". The same change is also applied to all networks in the org
not bound to templates, as well as disabling their local status pages.

=== USAGE ===
python[3] disable_status_page.py -k <api_key> -o <org_id> [-m <mode>]
Mode defaults to "simulate" unless "commit" is specified. 

'''


import csv
from datetime import datetime
import getopt
import json
import logging
import requests
import sys
from meraki import meraki

base_url = 'https://api.meraki.com/api/v0/'

logger = logging.getLogger(__name__)
def configure_logging():
    logging.basicConfig(
        filename='{}_log_{:%Y%m%d_%H%M%S}.txt'.format(sys.argv[0].split('.')[0], datetime.now()),
        level=logging.DEBUG,
        format='%(asctime)s: %(levelname)7s: [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# Prints READ_ME help message for user to read
def print_help():
    lines = READ_ME.split('\n')
    for line in lines:
        print('# {0}'.format(line))

# Update a network
# https://api.meraki.com/api_docs#update-a-network
def set_network(api_key, net_id, name=None, timeZone=None, tags=None, disableMyMerakiCom=False, display_result=True):
    put_url = f'{base_url}/networks/{net_id}'
    headers = {'X-Cisco-Meraki-API-Key': api_key,
               'Content-Type': 'application/json'}
    
    if type(tags) == list:
        tags = ' '.join(tags)
    
    payload = {key: value for (key, value) in locals().items()
               if key in ['name', 'timeZone', 'tags', 'disableMyMerakiCom'] and value != None}
    
    result = requests.put(put_url, headers=headers, data=json.dumps(payload))
    if display_result:
        print(f'Response status code of {result.status_code}, with content: {result.text}')
    return result

# List the appliance services and their accessibility rules
# https://api.meraki.com/api_docs#list-the-appliance-services-and-their-accessibility-rules
def get_appliance_services(api_key, net_id, display_result=True):
    get_url = f'{base_url}/networks/{net_id}/firewalledServices'
    headers = {'X-Cisco-Meraki-API-Key': api_key,
               'Content-Type': 'application/json'}
    
    result = requests.get(get_url, headers=headers)
    if display_result:
        print(f'Response status code of {result.status_code}, with content: {result.text}')
    return result

# Return the accessibility settings of the given service ('ICMP', 'web', or 'SNMP')
# https://api.meraki.com/api_docs#return-the-accessibility-settings-of-the-given-service-icmp-web-or-snmp
def get_appliance_service_setting(api_key, net_id, service=None, display_result=True):
    get_url = f'{base_url}/networks/{net_id}/firewalledServices/{service}'
    headers = {'X-Cisco-Meraki-API-Key': api_key,
               'Content-Type': 'application/json'}
    
    if not service or service.lower() not in ('icmp', 'web', 'snmp'):
        raise ValueError(f'parameter service must be either "ICMP", "web", or "SNMP", and cannot be {service} ('
                          'https://api.meraki.com/api_docs#updates-the-accessibility-settings-for-the-given-service-icmp-web-or-snmp)')
    
    result = requests.get(get_url, headers=headers)
    if display_result:
        print(f'Response status code of {result.status_code}, with content: {result.text}')
    return result

# Updates the accessibility settings for the given service ('ICMP', 'web', or 'SNMP')
# https://api.meraki.com/api_docs#updates-the-accessibility-settings-for-the-given-service-icmp-web-or-snmp
def set_appliance_service_setting(api_key, net_id, service=None, access=None, allowedIps=None, display_result=True):
    put_url = f'{base_url}/networks/{net_id}/firewalledServices/{service}'
    headers = {'X-Cisco-Meraki-API-Key': api_key,
               'Content-Type': 'application/json'}
    
    if not service or service.lower() not in ('icmp', 'web', 'snmp'):
        raise ValueError(f'parameter service must be either "ICMP", "web", or "SNMP", and cannot be {service} ('
                          'https://api.meraki.com/api_docs#updates-the-accessibility-settings-for-the-given-service-icmp-web-or-snmp)')
    
    if not access or access.lower() not in ('blocked', 'restricted', 'unrestricted'):
        raise ValueError(f'parameter access must be either "blocked", "restricted", or "unrestricted", and cannot be {access} ('
                          'https://api.meraki.com/api_docs#updates-the-accessibility-settings-for-the-given-service-icmp-web-or-snmp)')
    
    if access.lower() == 'restricted' and (not allowedIps or type(allowedIps) != list):
        raise ValueError(f'parameter allowedIps must be a list of whitelisted IP addresses, and cannot be {allowedIps} ('
                          'https://api.meraki.com/api_docs#updates-the-accessibility-settings-for-the-given-service-icmp-web-or-snmp)')
    
    payload = {key: value for (key, value) in locals().items() if key in ['access', 'allowedIps'] and value != None}
    
    result = requests.put(put_url, headers=headers, data=json.dumps(payload))
    if display_result:
        print(f'Response status code of {result.status_code}, with content: {result.text}')
    return result


def main(argv):
    # Set default values for command line arguments
    api_key = org_id = arg_mode = None
    
    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:m:')
    except getopt.GetoptError:
        print_help()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print_help()
            sys.exit()
        elif opt == '-k':
            api_key = arg
        elif opt == '-o':
            org_id = arg
        elif opt == '-m':
            arg_mode = arg
    
    # Check if all required parameters have been input
    if api_key == None or org_id == None:
        print_help()
        sys.exit(2)
    
    # Assign default mode to "simulate" unless "commit" specified
    if arg_mode != 'commit':
        arg_mode = 'simulate'
    
    # Get lists of templates and networks in org
    templates = meraki.gettemplates(api_key, org_id)
    networks = meraki.getnetworklist(api_key, org_id)
    unbound_networks = [network for network in networks if 'configTemplateId' not in network]
    
    # Iterate through all templates
    logger.info(f'Iterating through {len(templates)} templates:')
    for template in templates:
        
        result = get_appliance_service_setting(api_key, template['id'], 'web')
        # Does template have MX appliance component?
        if result.ok:
            web_status = json.loads(result.text)['access']
            
            # Check current config to see if already disabled
            if web_status == 'blocked':
                logger.info(f'Appliance web service for template {template["name"]} already disabled/blocked')
                csv_row = ['Template', template['name'], template['id'], '?', 'blocked']
                csv_writer.writerow(csv_row)
            else:
                
                # Update configuration
                if arg_mode == 'commit':
                    logger.info(f'Updating template {template["name"]}...')
                    result = set_appliance_service_setting(api_key, template['id'], 'web', 'blocked')
                    if result.ok:
                        logger.info(f'Blocked remote IPs for web service on template {template["name"]}')
                        web_status = json.loads(result.text)['access']
                    else:
                        logger.error(f'Failed to update appliance web service on {template["name"]}')
                        web_status = '?'
                else:
                    logger.info(f'Simulating update of template {template["name"]}...')
                
                # Write result to CSV output file
                csv_row = ['Template', template['name'], template['id'], '?', web_status]
                csv_writer.writerow(csv_row)
        
        else:
            # Template without appliance component
            csv_row = ['Template', template['name'], template['id'], '?', 'N/A']
            csv_writer.writerow(csv_row)
    
    
    # Iterate through all unbound networks (networks not associated with a template)
    logger.info(f'Iterating through {len(unbound_networks)} unbound networks:')
    for network in unbound_networks:
        
        # For appliance networks, check web firewall service
        if network['type'] in ('appliance', 'combined'):
            result = get_appliance_service_setting(api_key, network['id'], 'web')
            web_status = json.loads(result.text)['access']
        else:
            web_status = 'N/A'
        
        # If everything already disabled, make note in CSV & continue
        local_status_disabled = network['disableMyMerakiCom']
        if local_status_disabled and web_status in ('blocked', 'N/A'):
            logger.info(f'Status page for network {network["name"]} already disabled/blocked')
            csv_row = ['Network', network['name'], network['id'], 'disabled', web_status]
            csv_writer.writerow(csv_row)
        else:
            # Update configuration
            if arg_mode == 'commit':
                logger.info(f'Updating network {network["name"]}...')
                result1 = set_network(api_key, network['id'], disableMyMerakiCom=True)
                if result1.ok:
                    logger.info(f'Disabled local status page for network {network["name"]}')
                    local_status_disabled = True
                else:
                    logger.error(f'Failed to update local status page on network {network["name"]}')
                if network['type'] in ('appliance', 'combined'):
                    result2 = set_appliance_service_setting(api_key, network['id'], 'web', 'blocked')
                    if result2.ok:
                        logger.info(f'Blocked remote IPs for web service on appliance {network["name"]}')
                        web_status = json.loads(result2.text)['access']
                    else:
                        logger.error(f'Failed to update appliance web service on {network["name"]}')
                        web_status = '?'
            else:
                logger.info(f'Simulating update of network {network["name"]}...')
            
            # Write result to CSV output file
            lsp_status = 'disabled' if local_status_disabled else 'enabled'
            csv_row = ['Network', network['name'], network['id'], lsp_status, web_status]
            csv_writer.writerow(csv_row)


if __name__ == '__main__':
    inputs = sys.argv[1:]
    if len(inputs) == 0:
        print_help()
        sys.exit(2)
    
    # Configure logging to stdout
    configure_logging()
    # Define a Handler which writes INFO messages or higher to the sys.stderr
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    # Set a format which is simpler for console use
    formatter = logging.Formatter('%(name)-12s: %(levelname)-8s %(message)s')
    # Tell the handler to use this format
    console.setFormatter(formatter)
    # Add the handler to the root logger
    logging.getLogger('').addHandler(console)
    
    # Set the CSV output file and write the header row
    time_now = f'{datetime.now():%Y%m%d_%H%M%S}'
    file_name = f'status_page_results_{time_now}.csv'
    output_file = open(file_name, mode='w', newline='\n')
    field_names = ['Type', 'Name','ID','Status Page','Appliance Web Service']
    csv_writer = csv.writer(output_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    csv_writer.writerow(field_names)
    logger.info(f'Output of results to file: {file_name}')
    
    # Output to logfile/console starting inputs
    key_index = inputs.index('-k')
    inputs.pop(key_index+1)
    inputs.pop(key_index)
    start_time = datetime.now()
    logger.info(f'Started script at {start_time}')
    logger.info(f'Input parameters: {inputs}')
    
    # Call main function
    main(sys.argv[1:])
    
    # Finish output to logfile/console
    end_time = datetime.now()
    logger.info(f'Ended script at {end_time}')
    logger.info(f'Total run time = {end_time - start_time}')
