#!/usr/bin/python3

"""
=== PREREQUISITES ===
Run in Python 3.6+
Install MQTT package: pip[3] install paho-mqtt

=== DESCRIPTION ===
Monitor connectivity of specific clients using MR's MQTT data stream.

=== USAGE ===
Run with an input file of clients' MAC addresses to monitor, one per line.
python[3] mr_mqtt_monitoring.py -f client_addresses.txt
"""


import argparse
from datetime import datetime
import json
from subprocess import Popen

import paho.mqtt.client as mqtt


MOBILE_CLIENTS_STATE = {}
OVERALL_STATE = 'AWAY'
LAST_PRINT_TIME = None


def parse_arguments(parser):
    parser.add_argument('-f', '--file', help='Input file of MAC addresses, one per line')
    parser.exit
    args = parser.parse_args()
    return args.file


# The callback for when the client receives a CONNACK response from the server
def on_connect(client, user_data, flags, rc):
    global LAST_PRINT_TIME
    LAST_PRINT_TIME = datetime.utcnow()
    print(LAST_PRINT_TIME)

    print(f'Connected with result code {rc}')

    # Subscribing in on_connect() means that if we lose the connection and
    # reconnect then subscriptions will be renewed.
    client.subscribe(f'/meraki/mr')


# The callback for when a PUBLISH message is received from the server
def on_message(client, user_data, msg):
    global MOBILE_CLIENTS_STATE, OVERALL_STATE, LAST_PRINT_TIME

    # Process incoming MQTT data
    mqtt_data = json.loads(msg.payload)
    client = mqtt_data['clientMac']
    if client in MOBILE_CLIENTS_STATE:
        client_timestamp = mqtt_data['timestamp']
        MOBILE_CLIENTS_STATE[client]['last_seen'] = client_timestamp

    # Update state of each monitored client
    current_time = datetime.utcnow()
    for data in MOBILE_CLIENTS_STATE.values():
        if 'last_seen' in data and data['last_seen']:
            delta = current_time - datetime.fromisoformat(data['last_seen'])

            # If device is not seen for 5 seconds, mark as disconnected
            if delta.seconds < 5:
                data['connected'] = True
            else:
                data['connected'] = False
        else:
            data['connected'] = False

    # Update overall state
    home_clients = {k for k, v in MOBILE_CLIENTS_STATE.items() if v['connected']}
    if len(home_clients) == 0:
        if OVERALL_STATE == 'HOME':
            Popen(f'python3 turn_off_lights.py', shell=True)
        OVERALL_STATE = 'AWAY'
    else:
        OVERALL_STATE = 'HOME'

    # Display state to end user to see visually, at most once per second
    # if client in MOBILE_CLIENTS_STATE:
    #     print(MOBILE_CLIENTS_STATE)
    delta = current_time - LAST_PRINT_TIME
    # print(delta.microseconds)
    if delta.seconds >= 1 or delta.microseconds >= 9 * 10 ** 5:
        LAST_PRINT_TIME = current_time
        print(MOBILE_CLIENTS_STATE)


def main():
    # Process input parameters
    parser = argparse.ArgumentParser()
    input_file = parse_arguments(parser)
    if not input_file:
        parser.exit(2, parser.print_help())

    # Add to global variable for tracking state
    with open(input_file) as fp:
        mac_addresses = fp.readlines()
    mobile_clients = [mac.strip().upper() for mac in mac_addresses]
    for client in mobile_clients:
        MOBILE_CLIENTS_STATE[client] = {}

    # Start MQTT client
    client = mqtt.Client()
    user_data = {}
    client.user_data_set(user_data)
    client.on_connect = on_connect
    client.on_message = on_message
    client.connect('localhost', 1883)

    # Blocking call that processes network traffic, dispatches callbacks and
    # handles reconnecting.
    # Other loop*() functions are available that give a threaded interface and a
    # manual interface.
    client.loop_forever()


if __name__ == '__main__':
    main()
