#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3

Install Requests, PyYAML and Meraki Dashboard API Python modules:
pip[3] install --upgrade requests
pip[3] install --upgrade meraki
pip[3] install --upgrade pyyaml

=== DESCRIPTION ===
Exports YAML of MX site-to-site VPN rules from Dashboard network.

=== USAGE ===
python export_mx_s2svpn.py -k <api_key> -o <org_id>
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
    api_key = org_id = None

    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:')
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

    # Check if all required parameters have been input
    if api_key == None or org_id == None:
        print_help()
        sys.exit(2)
        
    dashboard = meraki.DashboardAPI(
        api_key=api_key,
        base_url='https://api-mp.meraki.com/api/v1/',
        output_log=True,
        log_file_prefix=os.path.basename(__file__)[:-3],
        log_path='',
        print_console=False
    )

    # Set the output file
    timenow = '{:%Y%m%d_%H%M%S}'.format(datetime.now())
    filename = 'mx_s2svpnfw_rules_{0}.yaml'.format(timenow)

    # Read Dashboard configuration of MX L3 firewall rules
    fw_rules = dashboard.appliance.getOrganizationApplianceVpnVpnFirewallRules(org_id)
    
    print(fw_rules)
    
    with open(filename, 'w') as file:
        documents = yaml.dump(fw_rules, file)

    print('Export completed to file {0}'.format(filename))


if __name__ == '__main__':
    inputs = sys.argv[1:]
    try:
        key_index = inputs.index('-k')
    except ValueError:
        print_help()
        sys.exit(2)
    
    main(sys.argv[1:])
