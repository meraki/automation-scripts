#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3

Install Requests, PyYAML and Meraki Dashboard API Python modules:
pip[3] install --upgrade requests
pip[3] install --upgrade meraki
pip[3] install --upgrade pyyaml

=== DESCRIPTION ===
Imports YAML of MX site-to-site VPN firewall rules into Dashboard network. Note
that if logging is enabled for any rule, then a syslog server needs to be
configured on the Network-wide > General page.

=== USAGE ===
python import_mx_s2svpn.py -k <api_key> -o <org_id> -f <file> [-m <mode>]
The -f parameter is the path to the YAML file with MX S2S VPN firewall rules.
The optional -m parameter is either "simulate" (default) to only print changes,
or "commit" to also apply those changes to Dashboard.
'''

from datetime import datetime
import getopt
import sys
import os
import meraki
import yaml

# Prints READ_ME help message for user to read
def print_help():
    lines = READ_ME.split('\n')
    for line in lines:
        print('# {0}'.format(line))


def main(argv):
    # Set default values for command line arguments
    api_key = org_id = arg_file = arg_mode = None

    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:f:m:')
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
        elif opt == '-f':
            arg_file = arg
        elif opt == '-m':
            arg_mode = arg

    # Check if all required parameters have been input
    if api_key == None or org_id == None or arg_file == None:
        print_help()
        sys.exit(2)

    # Assign default mode to "simulate" unless "commit" specified
    if arg_mode != 'commit':
        arg_mode = 'simulate'
                
    dashboard = meraki.DashboardAPI(
        api_key=api_key,
        base_url='https://api-mp.meraki.com/api/v1/',
        output_log=True,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='',
        print_console=False
    )

    # Read input file
    with open(arg_file) as file:
        loaded_rules = yaml.full_load(file)
            
    #Remove default allow rule, if it exists in loaded rules
    default_allow_rule = {'comment': 'Default rule', 'destCidr': 'Any', 'destPort': 'Any',
        'policy': 'allow', 'protocol': 'Any', 'srcCidr': 'Any', 'srcPort': 'Any'}
        
    last_line = loaded_rules['rules'][len(loaded_rules['rules'])-1]
    
    matched_default = True
    for key in default_allow_rule:
        if key in last_line:
            if last_line[key] != default_allow_rule[key]:
                matched_default = False
                
    if matched_default:
        processed_rules = loaded_rules['rules'][:-1]
    else:
        processed_rules = loaded_rules['rules']
        
    if arg_mode == 'commit':
        print("\nCOMMIT MODE ENABLED\n")
        result = dashboard.appliance.updateOrganizationApplianceVpnVpnFirewallRules(org_id, rules=processed_rules)
        print("Configuration updated. Result:\n\n%s" % result)
    else:
        print("\nSIMULATION MODE ENABLED\n")
        print('Use "-m commit" to apply the following VPN FW rules:\n')
        print(processed_rules)
    
if __name__ == '__main__':
    inputs = sys.argv[1:]
    try:
        key_index = inputs.index('-k')
    except ValueError:
        print_help()
        sys.exit(2)

    main(sys.argv[1:])
