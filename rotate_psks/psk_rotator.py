import meraki
import smtplib, ssl
import os
import time
from xkcdpass import xkcd_password as xp

'''
Cisco Meraki PSK Rotator
John M. Kuchta .:|:.:|:.  https://github.com/TKIPisalegacycipher
Goals
* Generate random PSK
* Update one specific SSID's PSK 
* Email one specific address a notification of the change

If you plan to use Gmail's SMTP server, please consult https://support.google.com/a/answer/176600 before use.
There are a few caveats to using it, and you might have errors unless you follow the directions in that doc,
and update this code to use the settings that are right for your organization.

USAGE
Update the SMTP configuration to match your SMTP server
Update the Meraki dashboard configuration section to match your desired outcome
Update the password generator configuration to meet your complexity needs
Test in a test organization with test networks to confirm desired functionality
The rest is history!
'''

# SMTP configuration
# Please note: Gmail SMTP servers can be tricky to use.
# Please read https://support.google.com/a/answer/176600 before using Gmail.
smtp = dict()
smtp['port'] = 465
smtp['fqdn'] = 'smtp.gmail.com' # Please consult https://support.google.com/a/answer/176600 before using Gmail SMTP.
smtp['username'] = os.environ['PYTHON_SMTP_USERNAME']
smtp['password'] = os.environ['PYTHON_SMTP_PASSWORD']

# Meraki dashboard configuration
ORGANIZATION_ID = 'YOUR ORGANIZATION ID HERE'
SSID_NUMBER = 10 # choose the single SSID number that you want to update across the entire org.
ACTIONS_PER_BATCH = 100 # leave at 100 for max efficiency
RECIPIENT_EMAIL = 'YOUR_RECIPIENT@EMAIL.HERE'

# Password generator configuration
# Generated password will take the form of several human-readable words. Max and min length apply to each word.
MINIMUM_LENGTH = 4
MAXIMUM_LENGTH = 7
NUMBER_OF_WORDS = 3


# Email methods
def create_smtp_server(fqdn=smtp['fqdn'], port=smtp['port'], username=smtp['username'], password=smtp['password']):
    # Returns logged-in SMTP server object
    # Create SSL context
    ssl_context = ssl.create_default_context()
    # Log in to SMTP server
    with smtplib.SMTP_SSL(fqdn, port, context=ssl_context) as smtp_server:
        smtp_server.login(username, password)

    return smtp_server


def send_email(server, recipient, message, sender=smtp['username']):
    # Sends an email to the specified recipients
    send = server.sendmail(sender, recipient, message)
    return send


# Action and action batch methods
def check_batch_queue(dashboard, organizationId):
    pending_action_batches = dashboard.organizations.getOrganizationActionBatches(organizationId=organizationId,
                                                                                  status='pending')
    active_action_batches = [batch for batch in pending_action_batches if batch['confirmed']]
    batch_queue_is_full = True if len(active_action_batches) > 4 else False
    return pending_action_batches, active_action_batches, batch_queue_is_full


def add_to_batch_queue(dashboard, organizationId, new_batches, wait_time=5, confirmed=True):
    # Adds batches to the queue and returns the responses when they have been submitted.
    pending_action_batches, active_action_batches, batch_queue_is_full = check_batch_queue(dashboard, organizationId)
    remaining_new_batches = len(new_batches)
    batch_responses = list()

    while remaining_new_batches:
        while batch_queue_is_full and confirmed:
            print(f'There are already {len(active_action_batches)} active action batches. Waiting {wait_time} '
                  f'seconds before trying again.')
            time.sleep(wait_time)

            pending_action_batches, active_action_batches, batch_queue_is_full = check_batch_queue(dashboard, organizationId)

        print(f'Creating the next action batch. {remaining_new_batches} action batches remain.')
        batch_response = dashboard.organizations.createOrganizationActionBatch(**new_batches.pop(0))
        batch_responses.append(batch_response)
        pending_action_batches, active_action_batches, batch_queue_is_full = check_batch_queue(dashboard, organizationId)
        remaining_new_batches = len(new_batches)

    return batch_responses


def group_actions(actions_list, actions_per_batch):
    # Groups actions into lists of appropriate size
    # Returns a list generator
    total_actions = len(actions_list)
    for i in range(0, total_actions, actions_per_batch):
        yield actions_list[i:i + actions_per_batch]


def create_batches(organizationId, actions_list, actions_per_batch=ACTIONS_PER_BATCH,
                   synchronous=False, confirmed=True):
    # Groups actions, then create and optionally run batches
    # Validate the actions_per_batch and synchronous arguments
    if actions_per_batch > 100:
        print('One asynchronous action batch may contain up to a maximum of 100 actions. Using maximum instead.')
        actions_per_batch = 100
    elif actions_per_batch > 20 and synchronous:
        print('One synchronous action batch may contain up to a maximum of 20 actions. Using maximum instead.')
        actions_per_batch = 20

    # Group the actions into lists of appropriate size
    grouped_actions_list = list(group_actions(actions_list, actions_per_batch))
    created_batches = list()

    # Add each new batch to the new_batches list
    for action_list in grouped_actions_list:
        batch = {
            "organizationId": organizationId,
            "actions": action_list,
            "synchronous": synchronous,
            "confirmed": confirmed
        }
        created_batches.append(batch)

    return created_batches


# SSID & PSK methods
def create_action_for_each_network(networks_list, create_action, **kwargs):
    # Returns a list of one action per network in an organization
    actions = list()
    for network in networks_list:
        action = create_action(networkId=network['id'], **kwargs)
        actions.append(action)

    return actions


def initialize():
    # Initialize settings
    # Initialize Dashboard connection
    dashboard = meraki.DashboardAPI(
        caller="PSKRotator/1.0 Kuchta Meraki"
    )

    # Get the networks list
    networks_list = dashboard.organizations.getOrganizationNetworks(
        organizationId=ORGANIZATION_ID
    )

    # PASSPHRASE/PSK GENERATION
    # Password generator configuration
    password_word_list = xp.generate_wordlist(min_length=MINIMUM_LENGTH, max_length=MAXIMUM_LENGTH)

    # Generate today's PSK
    new_psk = xp.generate_xkcdpassword(password_word_list, numwords=NUMBER_OF_WORDS)

    return dashboard, networks_list, new_psk


def change_psks(dashboard, organizationId, networks_list, ssid_number, new_psk):
    # Specify the bulk action
    change_psk_action = dashboard.batch.wireless.updateNetworkWirelessSsid

    # Format the action kwargs
    change_psk_kwargs = {
        'number': ssid_number,
        'psk': new_psk
    }

    print('Creating actions_for_networks...')
    actions_for_networks = create_action_for_each_network(networks_list, change_psk_action, **change_psk_kwargs)

    print(f'The total number of actions in your batches is {len(actions_for_networks)}. Creating the batches...')
    new_batches = create_batches(organizationId, actions_for_networks)

    print(f'The number of new action batches is {len(new_batches)}. Adding batches to queue...')
    added_batch_responses = add_to_batch_queue(dashboard, organizationId, new_batches)

    return added_batch_responses


# main
if __name__ == "__main__":
    dashboard, networks_list, new_psk = initialize()
    responses = change_psks(dashboard, ORGANIZATION_ID, networks_list, SSID_NUMBER, new_psk)
    smtp_server = create_smtp_server()
    smtp_server.connect(smtp['fqdn'], smtp['port'])
    smtp_server.ehlo()
    smtp_server.login(smtp['username'], smtp['password'])
    email = send_email(smtp_server, RECIPIENT_EMAIL, f'The new Meraki SSID PSK is "{new_psk}".\nThank you for '
                                                           f'choosing Meraki!')

    print(f'The new Meraki SSID PSK is "{new_psk}".\nThank you for choosing Meraki!')

