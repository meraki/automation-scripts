#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3

Fill out OLD_MODEL, NEW_MODEL, and optionally SKIPPED_NAMES below (lines 29-31)
OLD_MODEL = model number of switch to be swapped out
NEW_MODEL = model number of switch to be swapped in
SKIPPED_NAMES = exact names of any new model switches to be left untouched

Install both requests & Meraki Dashboard API Python modules:
pip[3] install --upgrade requests
pip[3] install --upgrade meraki

=== DESCRIPTION ===
This script iterates through the org's networks that are tagged with the label
"migrate". For each of these networks' OLD_MODEL switch, a corresponding
NEW_MODEL with the same name is expected in the network. The switch port
configuration per port per OLD_MODEL is then copied over to the corresponding
port on the NEW_MODEL. Remove the network tag/label "migrate" afterwards.

=== USAGE ===
python[3] clone_port_configs.py -k <api_key> -o <org_id> [-m <mode>]
The optional -m parameter is either "simulate" (default) to only print changes,
or "commit" to also apply those changes to Dashboard.
'''

OLD_MODEL = 'MS225-48FP'
NEW_MODEL = 'MS250-48FP'
SKIPPED_NAMES = ['EXACT name of switch']

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

    # Get list of current networks in org
    networks = meraki.getnetworklist(api_key, org_id)

    # Iterate through all networks
    for network in networks:

        # Skip if network does not have the tag "migrate"
        if network['tags'] is None or 'migrate' not in network['tags']:
            continue

        # Iterate through a "migrate" network's switches
        devices = meraki.getnetworkdevices(api_key, network['id'])

        # Use two dictionaries to keep track of names (keys) and serials (values)
        old_switches = {}
        new_switches = {}
        for device in devices:
            if device['model'] == OLD_MODEL:
                old_switches[device['name']] = device['serial']
            elif device['model'] == NEW_MODEL:
                new_switches[device['name']] = device['serial']

        # Check to make sure there actually are new switches in this network
        if len(new_switches) == 0:
            logger.error('{0} has no {1} switches, so skipping'.format(network['name'], NEW_MODEL))
            continue
        else:
            logger.info('Cloning configs for network {0}'.format(network['name']))
            
            # For networks where new switches have been added with matching names
            for name in new_switches.keys():
                if name in SKIPPED_NAMES:
                    continue
                
                # Lookup serial numbers
                old_switch = old_switches[name]
                new_switch = new_switches[name]
                logger.info('Cloning configs from {0} {1} to {2} {3}'.format(OLD_MODEL, old_switch, NEW_MODEL, new_switch))
                
                # Port 1 through 54 (48 LAN, 4 uplinks, 2 stacking, +1 for range ending index)
                for port in range(1, 48+4+2+1):
                    config = meraki.getswitchportdetail(api_key, old_switch, port)
                    
                    # Clone corresponding new switch
                    if arg_mode == 'commit':
                        # Tags needed to be input as a list
                        if config['tags'] is not None:
                            tags = config['tags'].split()
                        else:
                            tags = []

                        # Access type port
                        if config['type'] == 'access':
                            meraki.updateswitchport(api_key, new_switch, port,
                                name=config['name'], tags=tags, enabled=config['enabled'],
                                porttype=config['type'], vlan=config['vlan'], voicevlan=config['voiceVlan'],
                                poe=config['poeEnabled'], isolation=config['isolationEnabled'], rstp=config['rstpEnabled'],
                                stpguard=config['stpGuard'], accesspolicynum=config['accessPolicyNumber'])
                        # Trunk type port
                        elif config['type'] == 'trunk':
                            meraki.updateswitchport(api_key, new_switch, port,
                                name=config['name'], tags=tags, enabled=config['enabled'],
                                porttype=config['type'], vlan=config['vlan'], allowedvlans=config['allowedVlans'],
                                poe=config['poeEnabled'], isolation=config['isolationEnabled'], rstp=config['rstpEnabled'],
                                stpguard=config['stpGuard'])
                        logger.info('Switch port {0} config cloned'.format(port))
                    else:
                        logger.info('Switch port {0} config clone simulated'.format(port))


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
