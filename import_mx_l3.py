#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3 with Meraki dashboard API Python library @
https://github.com/meraki/dashboard-api-python/
pip[3] install --upgrade meraki

=== DESCRIPTION ===
Imports MX L3 outbound firewall rules from CSV file.
Note that if there is a final "default rule" with logging enabled, then a
syslog server needs to be configured on the Network-wide > General page.

=== USAGE ===
python[3] import_mx_l3.py [-k <api_key>] -n <net_id> -f <file> [-m <mode>]
The -f parameter is the path to the CSV file with the new MX L3 firewall rules.
The optional -m parameter is either "simulate" (default) to only print changes,
or "commit" to also apply those changes to the dashboard network.

API key can also be exported as an environment variable named
MERAKI_DASHBOARD_API_KEY
'''


import csv
from datetime import datetime
import getopt
import os
import sys

import meraki


# Prints READ_ME help message for user to read
def print_help():
    lines = READ_ME.split('\n')
    for line in lines:
        print('# {0}'.format(line))


def main(argv):
    # Set default values for command line arguments
    api_key = net_id = arg_file = arg_mode = None

    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:n:f:m:')
    except getopt.GetoptError:
        print_help()
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            print_help()
            sys.exit()
        elif opt == '-k':
            api_key = arg
        elif opt == '-n':
            net_id = arg
        elif opt == '-f':
            arg_file = arg
        elif opt == '-m':
            arg_mode = arg

    # Check if all required parameters have been input
    if (api_key == None and os.getenv('MERAKI_DASHBOARD_API_KEY') == None) or net_id == None or arg_file == None:
        print_help()
        sys.exit(2)

    # Assign default mode to "simulate" unless "commit" specified
    if arg_mode != 'commit':
        arg_mode = 'simulate'

    # Read CSV input file, and skip header row
    input_file = open(arg_file)
    csv_reader = csv.reader(input_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    next(csv_reader, None)
    print(f'Reading file {arg_file}')
    
    # Loop through each firewall rule from CSV file and build PUT data
    fw_rules = []
    for row in csv_reader:
        rule = dict({'policy': row[0], 'protocol': row[1], 'srcCidr': row[2], 'srcPort': row[3], 'destCidr': row[4], 'destPort': row[5], 'comment': row[6], 'syslogEnabled': (row[7] == True or row[7] == 'True' or row[7] == 'true')})
        
        # Append implied "/32" for IP addresses for just one host
        if '/' not in rule['srcCidr'] and rule['srcCidr'].lower() != 'any':
            rule['srcCidr'] += '/32'
        if '/' not in rule['destCidr'] and rule['destCidr'].lower() != 'any':
            rule['destCidr'] += '/32'

        print(rule)
        
        fw_rules.append(rule)
    old_rules = list(fw_rules)
    print(f'Processed all {len(fw_rules)} rules of file {arg_file}')

    # Check if last (default) rule exists, and if so, remove and check for default logging
    default_rule_exists = False
    default_logging = False
    last_rule = {'comment': 'Default rule', 'policy': 'allow', 'protocol': 'Any', 'srcPort': 'Any', 'srcCidr': 'Any', 'destPort': 'Any', 'destCidr': 'Any'}
    if all(item in fw_rules[-1].items() for item in last_rule.items()):
        default_rule_exists = True
        default_logging = (fw_rules.pop()['syslogEnabled'] == True)
    
    # Dashboard API library class
    m = meraki.DashboardAPI(api_key=api_key, log_file_prefix=__file__[:-3], simulate=(arg_mode == 'simulate'))

    # Update MX L3 firewall rules
    print(f'Attempting update/simulation of firewall rules to network {net_id}')
    m.mx_l3_firewall.updateNetworkL3FirewallRules(net_id, rules=fw_rules, syslogDefaultRule=default_logging)
    
    # Confirm whether changes were successfully made
    if arg_mode == 'commit':
        new_rules = m.mx_l3_firewall.getNetworkL3FirewallRules(net_id)
        if default_rule_exists and new_rules[:-1] == old_rules[:-1]:
            print('Update successful!')
        elif not(default_rule_exists) and new_rules[:-1] == old_rules:
            print('Update successful!')
        else:
            print('Uh oh, something went wrong...')


if __name__ == '__main__':
    main(sys.argv[1:])
