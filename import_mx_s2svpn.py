#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3

Install both requests & Meraki Dashboard API Python modules:
pip[3] install --upgrade requests
pip[3] install --upgrade meraki

=== DESCRIPTION ===
Imports CSV of MX site-to-site VPN firewall rules into Dashboard network. Note
that if logging is enabled for any rule, then a syslog server needs to be
configured on the Network-wide > General page.

=== USAGE ===
python import_mx_s2svpn.py -k <api_key> -o <org_id> -f <file> [-m <mode>]
The -f parameter is the path to the CSV file with MX S2S VPN firewall rules.
The optional -m parameter is either "simulate" (default) to only print changes,
or "commit" to also apply those changes to Dashboard.
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

logger = logging.getLogger(__name__)

def configure_logging():
    logging.basicConfig(
        filename='{}_log_{:%Y%m%d_%H%M%S}.txt'.format(sys.argv[0].split('.')[0], datetime.now()),
        level=logging.DEBUG,
        format='%(asctime)s: %(levelname)7s: [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


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

    # Read CSV input file, and skip header row
    input_file = open(arg_file)
    csv_reader = csv.reader(input_file, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
    next(csv_reader, None)
    logger.info('Reading file {0}'.format(arg_file))

    # Loop through each firewall rule from CSV file and build PUT data
    fw_rules = []
    for row in csv_reader:
        rule = dict({'policy': row[0], 'protocol': row[1], 'srcCidr': row[2], 'srcPort': row[3], 'destCidr': row[4], 'destPort': row[5], 'comment': row[6], 'syslogEnabled': (row[7] == True or row[7] == 'True' or row[7] == 'true')})
        fw_rules.append(rule)
    old_rules = list(fw_rules)
    logger.info('Processed all {0} rules of file {1}'.format(len(fw_rules), arg_file))

    # Check if last (default) rule exists, and if so, remove and check for default logging
    default_rule_exists = False
    default_logging = False
    last_rule = {'comment': 'Default rule', 'policy': 'allow', 'protocol': 'Any', 'srcPort': 'Any', 'srcCidr': 'Any', 'destPort': 'Any', 'destCidr': 'Any'}
    if all(item in fw_rules[-1].items() for item in last_rule.items()):
        default_rule_exists = True
        default_logging = (fw_rules.pop()['syslogEnabled'] == True)

    # Update MX site-to-site VPN firewall rules
    if arg_mode == 'commit':
        meraki.updatemxvpnfwrules(api_key, org_id, fw_rules, default_logging)
        logger.info('Attempting update of site-to-site VPN firewall rules to organization {0}'.format(org_id))

        # Confirm whether changes were successfully made
        new_rules = meraki.getmxvpnfwrules(api_key, org_id)
        if default_rule_exists and new_rules[:-1] == old_rules[:-1]:
            logger.info('Update successful!')
        elif not(default_rule_exists) and new_rules[:-1] == old_rules:
            logger.info('Update successful!')
        else:
            logger.error('Uh oh, something went wrong...')
    else:
        logger.info('Simulating update of site-to-site VPN firewall rules to organization {0}'.format(org_id))


if __name__ == '__main__':
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

    # Output to logfile/console starting inputs
    start_time = datetime.now()
    logger.info('Started script at {0}'.format(start_time))
    inputs = sys.argv[1:]
    try:
        key_index = inputs.index('-k')
    except ValueError:
        print_help()
        sys.exit(2)
    inputs.pop(key_index+1)
    inputs.pop(key_index)
    logger.info('Input parameters: {0}'.format(inputs))

    main(sys.argv[1:])

    # Finish output to logfile/console
    end_time = datetime.now()
    logger.info('Ended script at {0}'.format(end_time))
    logger.info(f'Total run time = {end_time - start_time}')
