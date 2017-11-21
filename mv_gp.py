#!/usr/bin/python3

READ_ME = '''
=== PREREQUISITES ===
Run in Python 3

Install both requests & Meraki Dashboard API Python modules:
pip[3] install requests [--upgrade]
pip[3] install meraki [--upgrade]

=== DESCRIPTION ===
This script finds all MV cameras with a specified tag, and then iterates
through all networks to apply an exisitng group policy (enforced by the MX)
to the applicable cameras as client devices.

=== USAGE ===
python mv_gp.py -k <api_key> -o <org_id> -t <tag> -p <policy> [-m <mode>]
The -t parameter specifies the required tag that needs to be present on the MV
camera, and -p the name of the MX group policy to be applied.
The optional -m parameter is either "simulate" (default) to only print changes,
or "commit" to also apply those changes to Dashboard.
'''


import getopt
import logging
import sys
from datetime import datetime
from meraki import meraki

# Prints READ_ME help message for user to read
def print_help():
    lines = READ_ME.split('\n')
    for line in lines:
        print('# {0}'.format(line))

logger = logging.getLogger(__name__)

def configure_logging():
    logging.basicConfig(
        filename='mv_gp_log_{:%Y%m%d_%H%M%S}.txt'.format(datetime.now()),
        level=logging.DEBUG,
        format='%(asctime)s: %(levelname)7s: [%(name)s]: %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def main(argv):
    # Set default values for command line arguments
    api_key = org_id = arg_tag = arg_policy = arg_mode = None

    # Get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:t:p:m:')
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
        elif opt == '-t':
            arg_tag = arg
        elif opt == '-p':
            arg_policy = arg
        elif opt == '-m':
            arg_mode = arg

    # Check if all required parameters have been input
    if api_key == None or org_id == None or arg_tag == None or arg_policy == None:
        print_help()
        sys.exit(2)

    # Assign default mode to "simulate" unless "commit" specified
    if arg_mode != 'commit':
        arg_mode = 'simulate'

    # Get org's inventory
    inventory = meraki.getorginventory(api_key, org_id)

    # Filter for only MV devices
    cameras = [device for device in inventory if device['model'][:2] in ('MV') and device['networkId'] is not None]

    # Gather the networks (IDs) where cameras have been added
    camera_network_ids = set([camera['networkId'] for camera in cameras])
    logger.info('Found a total of {0} cameras added to {1} networks in this Dashboard organization'.format(len(cameras), len(camera_network_ids)))

    # Iterate through camera networks and find cameras with specified tag
    camera_macs = []
    for net_id in camera_network_ids:
        devices = meraki.getnetworkdevices(api_key, net_id)
        for device in devices:
            if device['model'][:2] == 'MV' and 'tags' in device and arg_tag in device['tags']:
                camera_macs.append(device['mac'])
    logger.info('Found {0} cameras with the tag "{1}"'.format(len(camera_macs), arg_tag))

    # Get list of all networks in org
    networks = meraki.getnetworklist(api_key, org_id)

    # Iterate through all networks, looking for cameras as clients, and apply group policy
    for network in networks:
        # Get the Meraki devices in this network
        devices = meraki.getnetworkdevices(api_key, network['id'])
        
        # Filter for just the first two characters of each device model
        device_models = [device['model'][:2] for device in devices]

        # Is there an MX here? If so, get its index in the list of devices
        if 'MX' in device_models:
            # We found the MX device in the network
            mx_device = devices[device_models.index('MX')]
        else:
            # No MX in this network, doesn't make sense to apply a group policy to wired clients (cameras), so move on
            continue

        # Get list of MX clients
        clients = meraki.getclients(api_key, mx_device['serial'], timestamp=2592000)

        # Filter for MAC addresses of these clients
        client_macs = [client['mac'] for client in clients]

        # Cameras in this network = intersection of clients in this network and cameras in the org
        network_cameras = set(client_macs).intersection(camera_macs)

        # Assign group policy to these cameras in the network
        if network_cameras:
            # Gather group policies of network
            gps = meraki.getgrouppolicies(api_key, network['id'])

            # Get human-readable names of all group policies
            gp_names = [gp['name'] for gp in gps]

            # Look for the group policy
            gp_camera = gps[gp_names.index(arg_policy)]

            # Assign that group policy (by ID) to the camera by MAC address
            for mac in network_cameras:
                if arg_mode == 'commit':
                    meraki.updateclientpolicy(api_key, network['id'], mac, policy='group', policyid=gp_camera['groupPolicyId'])
                    logger.info('Assigning group policy "{0}" on network "{1}" for MV camera {2}'.format(arg_policy, network['name'], mac))
                else:
                    logger.info('Simulating group policy "{0}" on network "{1}" for MV camera {2}'.format(arg_policy, network['name'], mac))


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
    key_index = inputs.index('-k')
    inputs.pop(key_index+1)
    inputs.pop(key_index)
    logger.info('Input parameters: {0}'.format(inputs))

    main(sys.argv[1:])

    # Finish output to logfile/console
    end_time = datetime.now()
    logger.info('Ended script at {0}'.format(end_time))
    logger.info(f'Total run time = {end_time - start_time}')
