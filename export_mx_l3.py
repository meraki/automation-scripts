#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3

Install both requests & Meraki Dashboard API Python modules:
pip[3] install --upgrade requests
pip[3] install --upgrade meraki

=== DESCRIPTION ===
Exports CSV of MX L3 firewall rules from Dashboard appliance/combined network.

=== USAGE ===
python export_mx_l3.py -k <api_key> -n <net_id>
'''


import csv
from datetime import datetime
import getopt
import logging
import sys
from meraki import meraki

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
    if api_key == None or net_id == None:
        print_help()
        sys.exit(2)

    # Set the CSV output file and write the header row
    timenow = '{:%Y%m%d_%H%M%S}'.format(datetime.now())
    filename = 'mx_l3fw_rules_{0}.csv'.format(timenow)
    output_file = open(filename, mode='w', newline='\n')
    field_names = ['policy','protocol','srcCidr','srcPort','destCidr','destPort','comment','logging']
    csv_writer = csv.writer(output_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    csv_writer.writerow(field_names)

    # Read Dashboard configuration of MX L3 firewall rules
    fw_rules = meraki.getmxl3fwrules(api_key, net_id)

    # Loop through each firewall rule and write to CSV
    for rule in fw_rules:
        csv_row = [rule['policy'], rule['protocol'], rule['srcCidr'], rule['srcPort'],  rule['destCidr'], rule['destPort'], rule['comment'], rule['syslogEnabled']]
        csv_writer.writerow(csv_row)

    output_file.close()
    print('Export completed to file {0}'.format(filename))


if __name__ == '__main__':
    inputs = sys.argv[1:]
    try:
        key_index = inputs.index('-k')
    except ValueError:
        print_help()
        sys.exit(2)
    
    main(sys.argv[1:])
