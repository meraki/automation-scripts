#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3 with Meraki dashboard API Python library @
https://github.com/meraki/dashboard-api-python/
pip[3] install --upgrade meraki

=== DESCRIPTION ===
Exports CSV of MX L3 outbound firewall rules.

=== USAGE ===
python[3] export_mx_l3.py [-k <api_key>] -n <net_id>

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
    api_key = net_id = None

    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:n:')
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

    # Check if all required parameters have been input
    if (api_key == None and os.getenv('MERAKI_DASHBOARD_API_KEY') == None) or net_id == None:
        print_help()
        sys.exit(2)

    # Set the CSV output file and write the header row
    time_now = f'{datetime.now():%Y-%m-%d_%H-%M-%S}'
    file_name = f'mx_l3fw_rules__{time_now}.csv'
    output_file = open(file_name, mode='w', newline='\n')
    field_names = ['policy','protocol','srcCidr','srcPort','destCidr','destPort','comment','logging']
    csv_writer = csv.writer(output_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    csv_writer.writerow(field_names)

    # Dashboard API library class
    m = meraki.DashboardAPI(api_key=api_key, log_file_prefix=__file__[:-3])

    # Read configuration of MX L3 firewall rules
    fw_rules = m.mx_l3_firewall.getNetworkL3FirewallRules(net_id)

    # Loop through each firewall rule and write to CSV
    for rule in fw_rules:
        csv_row = [rule['policy'], rule['protocol'], rule['srcCidr'], rule['srcPort'],  rule['destCidr'], rule['destPort'], rule['comment'], rule['syslogEnabled']]
        csv_writer.writerow(csv_row)

    output_file.close()
    print(f'Export completed to file {file_name}')


if __name__ == '__main__':
    main(sys.argv[1:])
