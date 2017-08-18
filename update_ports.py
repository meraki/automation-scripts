#!/usr/bin/python2

'''
=== PREREQUISITES ===
Run in Python 2

Install requests library, via macOS terminal:
sudo pip install requests

=== DESCRIPTION ===
This script finds all MS switchports that match the input search parameter, searching either by clients from a file listing MAC addresses (one per line), a specific tag in Dashboard currently applied to ports, or the specific access policy currently configured. It then changes the configuration of the port by applying the new access policy specified. Its counterpart script find_ports.py can be first used to check, as it does not change any configs.

=== USAGE ===
python update_ports.py -k <api_key> -o <org_id> -s <search_parameter> [-t <time>] -p <policy>
The -s parameter will be either a local file of MAC addresses (one per line), a currently configured port tag in Dashboard, or the currently configured access policy (number of policy slot) on the Switch > Access policy page. Option -t, if using input list of MACs, to only search for clients that were last seen within t minutes, default is 15. -p specifies the slot # of the new access policy to configure on matching ports.

'''

import getopt
import json
import requests
import sys
from datetime import datetime

# Prints a line of text that is meant for the user to read
def printusertext(p_message):
    print('# %s' % p_message)

# Prints help text
def printhelp():
    printusertext('This script finds all MS switchports that match the input search parameter,')
    printusertext('searching either by clients from a file listing MAC addresses (one per line),')
    printusertext('a specific tag in Dashboard currently applied to ports, or the specific')
    printusertext('access policy currently configured. It then changes the configuration of the')
    printusertext('port by applying the new access policy specified. Its counterpart script')
    printusertext('find_ports.py can be first used to check, as it does not change any configs.')
    printusertext('')
    printusertext('Usage:')
    printusertext('python update_ports.py -k <api_key> -o <org_id> -s <search_parameter> [-t <time>] -p <policy>')
    printusertext('The -s parameter will be either a local file of MAC addresses (one per line),')
    printusertext('a currently configured port tag in Dashboard, or the currently configured')
    printusertext('access policy (number of policy slot) on the Switch > Access policy page.')
    printusertext('Option -t, if using input list of MACs, to only search for clients')
    printusertext('that were last seen within t minutes, default is 15.')
    printusertext('-p specifies the slot # of the new access policy to configure on matching ports.')


def list_networks(api_key, org_id):
    url = 'https://dashboard.meraki.com/api/v0/organizations/{}/networks'.format(org_id)
    try:
        response = requests.get(url=url, headers={'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'})
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print('Error calling list_networks: {}'.format(e))

def get_inventory(api_key, org_id):
    url = 'https://dashboard.meraki.com/api/v0/organizations/{}/inventory'.format(org_id)
    try:
        response = requests.get(url=url, headers={'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'})
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print('Error calling get_inventory: {}'.format(e))

def list_switch_ports(api_key, serial):
    url = 'https://dashboard.meraki.com/api/v0/devices/{}/switchPorts'.format(serial)
    try:
        response = requests.get(url=url, headers={'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'})
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print('Error calling list_switch_ports with serial number {}: {}'.format(serial, e))

def get_port_details(api_key, serial, number):
    url = 'https://dashboard.meraki.com/api/v0/devices/{}/switchPorts/{}'.format(serial, number)
    try:
        response = requests.get(url=url, headers={'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'})
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print('Error calling get_port_details with serial {} and port {}: {}'.format(serial, number, e))

def update_switch_port(api_key, serial, number, data):
    url = 'https://dashboard.meraki.com/api/v0/devices/{}/switchPorts/{}'.format(serial, number)
    try:
        response = requests.put(url=url, data=data, headers={'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'})
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print('Error calling update_switch_port with serial {}, port {}, and data {}: {}'.format(serial, number, data, e))

def list_clients(api_key, serial, timestamp=86400): # timestamp in seconds
    url = 'https://dashboard.meraki.com/api/v0/devices/{}/clients?timespan={}'.format(serial, timestamp)
    try:
        response = requests.get(url=url, headers={'X-Cisco-Meraki-API-Key': api_key, 'Content-Type': 'application/json'})
        return json.loads(response.text)
    except requests.exceptions.RequestException as e:
        print ('Error calling list_clients with serial {}: {}'.format(serial, e))


def main(argv):
    # Set default values for command line arguments
    API_KEY = ORG_ID = ARG_SEARCH = ARG_TIME = ARG_POLICY = 'null'

    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:s:t:p:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            API_KEY = arg
        elif opt == '-o':
            ORG_ID = arg
        elif opt == '-s':
            ARG_SEARCH = arg
        elif opt == '-t':
            ARG_TIME = arg
        elif opt == '-p':
            ARG_POLICY = arg

    # Check if all parameters are required parameters have been given
    if API_KEY == 'null' or ORG_ID == 'null' or ARG_SEARCH == 'null' or ARG_POLICY == 'null':
        printhelp()
        sys.exit(2)

    # Assign search parameter
    search_file = search_policy = search_tag = None
    try:
        # Check if search parameter is file
        search_file = open(ARG_SEARCH)
    except IOError:
        try:
            # Check if search parameter is number
            search_policy = int(ARG_SEARCH)
        except ValueError:
            search_tag = ARG_SEARCH

    # Assign default time option if not specified
    try:
        search_time = int(ARG_TIME)
        search_time *= 60
    except ValueError:
        search_time = 60*15

    # Check that new policy is a number
    try:
        new_policy = int(ARG_POLICY)
    except ValueError:
        printhelp()
        sys.exit(2)

    # Find all MS networks
    session = requests.session()
    inventory = get_inventory(API_KEY, ORG_ID)
    switches = [device for device in inventory if device['model'][:2] in ('MS') and device['networkId'] is not None]
    switch_networks = []
    for switch in switches:
        if switch['networkId'] not in switch_networks:
            switch_networks.append(switch['networkId'])
    print('Found a total of %d switches configured across %d networks in this organization.' % (len(switches), len(switch_networks)))

    # Find all ports with search parameter
    if search_file is not None:
        # Searching on file with list of MAC addresses
        macs = search_file.read().split('\n')
        macs = [mac.upper() for mac in macs]
        print('Searching on list of %d MACs in file %s, with first and last addresses being %s and %s, respectively.' % (len(macs), ARG_SEARCH, macs[0], macs[-1]))
        tally_ports = 0

        # Find all clients per switch that match list
        for switch in switches:
            # Find clients that were connected in last 15 minutes
            clients = list_clients(API_KEY, switch['serial'], search_time)
            
            # Helper variable that is a list of all MAC addresses, in upper-case to compare with master input list
            clients_macs = [client['mac'].upper() for client in clients]

            # Helper variable that is a dict of MAC address keys to client information values
            matching_dict = {}
            for (mac, client) in zip(clients_macs, clients):
                matching_dict[mac] = client

            # Find matches between clients on switch to master input list
            matches = set(clients_macs).intersection(macs)

            # Find ports of matched clients
            if len(matches) > 0:
                matched_ports = {}
                for match in matches:
                    port = matching_dict[match]['switchport']
                    if port not in matched_ports:
                        matched_ports[port] = 1
                    else:
                        matched_ports[port] += 1
                print('Found %d matched MAC addresses on switch %s' % (len(matches), switch['serial']))
                tally_ports += len(matched_ports.keys())
                for port in matched_ports.keys():
                    switchport = get_port_details(API_KEY, switch['serial'], port)
                    if switchport['accessPolicyNumber'] == new_policy:
                        continue
                    else:
                        switchport['accessPolicyNumber'] = new_policy
                        update_switch_port(API_KEY, switch['serial'], switchport['number'], json.dumps(switchport))
                print('Configured %d matched ports on switch %s' % (len(matched_ports), switch['serial']))
        print('Configured %d total ports matching search criteria.' % (tally_ports))
    elif search_policy is not None:
        # Searching on access policy
        print('Searching on switch ports configured with access policy %d.' % (search_policy))
        tally_ports = 0
        for switch in switches:
            ports = list_switch_ports(API_KEY, switch['serial'])
            matched_ports = [port for port in ports if port['accessPolicyNumber'] != None and search_policy == port['accessPolicyNumber']]
            if len(matched_ports) > 0:
                # Change access policy for all matched ports
                for port in matched_ports:
                    if port['accessPolicyNumber'] == new_policy:
                        continue
                    else:
                        port['accessPolicyNumber'] = new_policy
                        update_switch_port(API_KEY, switch['serial'], port['number'], json.dumps(port))
                print('Configured %d matched ports on switch %s' % (len(matched_ports), switch['serial']))
                tally_ports += len(matched_ports)
        print('Configured %d total ports matching search criteria.' % (tally_ports))
    else:
        # Searching on port tag
        print('Searching on switch ports configured with tag %s.' % (search_tag))
        tally_ports = 0
        for switch in switches:
            ports = list_switch_ports(API_KEY, switch['serial'])
            matched_ports = [port for port in ports if port['tags'] != None and search_tag in port['tags']]
            if len(matched_ports) > 0:
                # Change access policy for all matched ports
                for port in matched_ports:
                    if port['accessPolicyNumber'] == new_policy:
                        continue
                    else:
                        port['accessPolicyNumber'] = new_policy
                        update_switch_port(API_KEY, switch['serial'], port['number'], json.dumps(port))
                print('Configured %d matched ports on switch %s' % (len(matched_ports), switch['serial']))
                tally_ports += len(matched_ports)
        print('Configured %d total ports matching search criteria.' % (tally_ports))

if __name__ == '__main__':
    startTime = datetime.now()
    print('Starting script at: %s' % startTime)
    print('Arguments entered: %s' % sys.argv[1:])
    main(sys.argv[1:])
    print('Ending script at: %s' % datetime.now())
    print('Total run time: %s' % (datetime.now() - startTime))
