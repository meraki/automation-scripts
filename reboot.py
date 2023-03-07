#!/usr/bin/env python3

import meraki
import sys


dashboard = meraki.DashboardAPI(suppress_logging=True)


def reboot(file):
    with open(file, 'r') as device:
        for i in device:
            serial = i.strip()
            response = dashboard.devices.rebootDevice(serial)
            print(f'Device {serial} was rebooted {response}')
    sys.exit()


if __name__ == '__main__':
    try:
        sys.argv[1]
    except IndexError:
        print("Please provide a file with serial numbers")
        sys.exit()
    else:
        file = ' '.join(sys.argv[1:])
        reboot(file)

read_me = '''
A Python 3 script to reboot Meraki Devices.
Required Python modules:
    meraki

Usage:
bssid.py file.txt

"file" should be a txt with the list of serail numbers that need to be rebooted
one on each line

serial1
serial2
serial3

API Key
requires you to have your API key in env vars as 'MERAKI_DASHBOARD_API_KEY'
'''
