#!/usr/bin/env python3

import meraki
import sys
import json
import argparse


dashboard = meraki.DashboardAPI(suppress_logging=True)


def parse_options():
    parser = argparse.ArgumentParser(
        prog='Meraki Location Updater',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description='''
            A Python 3 script to set the location of all devices in a Network

            Usage:
            setlocation.py -n "Network Name" -l "Address of the site"
            **Please note the quotes around the Network Name and Address

            API Key
            requires you to have your API key in env vars as
            'MERAKI_DASHBOARD_API_KEY'
  ''')
    parser.add_argument('-n', '--name',
                        metavar='name',
                        help="Network to be updated",
                        required=True)
    parser.add_argument('-l', '--location',
                        metavar='location',
                        help="Address of the Site",
                        required=True)
    parser.add_argument('-v', '--version',
                        action='version',
                        version='%(prog)s 2.0')
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)
    args = parser.parse_args()
    net_name = str(args.name)
    new_location = str(args.location)
    return net_name, new_location


def get_orgs():
    orgs = dashboard.organizations.getOrganizations()
    org_list = {}
    for dic in orgs:
        org_list[dic['id']] = dic['name']
    return org_list


def find_org(org_list):
    if len(org_list) == 1:
        org_id = org_list[0]['id']
    else:
        org_id = input(
            f'Please type the number of the Organization that has the network '
            f'you would like to update{json.dumps(org_list, indent = 4)}' "\n")
    return org_id


def get_networks(org_id):
    net_list = dashboard.organizations.getOrganizationNetworks(
        org_id, total_pages='all')
    return net_list


def find_networks(net_list, net_name):
    found_network = False
    for dic in net_list:
        if dic['name'] == net_name:
            found_network = True
            net_id = dic['id']
    if not found_network:
        print(f'We did not find {net_name} in your organization(s)')
        sys.exit()
    return net_id


def get_serials(net_id):
    serials_list = []
    devices = dashboard.networks.getNetworkDevices(net_id)
    for dic in devices:
        serials_list.append(dic['serial'])
    return serials_list


def update_address(serials_list, new_location, net_name):
    for serial in serials_list:
        dashboard.devices.updateDevice(
            serial,
            address=new_location,
            moveMapMarker='true')
    print(f'All devices in {net_name} have been updated to {new_location}')


def main():
    net_name, new_location = parse_options()
    org_list = get_orgs()
    org_id = find_org(org_list)
    net_list = get_networks(org_id)
    net_id = find_networks(net_list, net_name)
    serials_list = get_serials(net_id)
    update_address(serials_list, new_location, net_name)


if __name__ == '__main__':
    main()
