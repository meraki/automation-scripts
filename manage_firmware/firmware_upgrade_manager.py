import meraki
import datetime
import time

'''
Cisco Meraki Firmware Upgrade Manager
John M. Kuchta .:|:.:|:.  https://github.com/TKIPisalegacycipher
This script will pull network IDs from an org and then create asynchronous action batches. Each batch will contain, for 
each network, an action that will delay the upgrade datetime stamp by X days (configurable). Each batch can contain up 
to 100 actions, therefore, each batch can modify up to 100 networks. 

As always, you should read the docs before diving in. If you know how these features work, then it will be easier to 
understand and leverage this tool.

Firmware upgrades endpoint: https://developer.cisco.com/meraki/api-v1/#!get-network-firmware-upgrades
Action batches: https://developer.cisco.com/meraki/api-v1/#!action-batches-overview

NB: Once you start the script, there are no confirmation prompts or previews, so test in a lab if necessary. 

NB: When the final batch has been submitted, depending on the batch size, it may take a few minutes to finish. Feeling 
creative? Then try extending this script (using existing code, for the most part) to confirm when the batches are 
complete. Feeling super creative? Wrap this behind a Flask frontend and have yourself a merry little GUI.
'''

# init Meraki Python SDK session
dashboard = meraki.DashboardAPI(suppress_logging=True, single_request_timeout=120)


# Configurable options
# Organization ID. Replace this with your actual organization ID.
organization_id = 'YOUR ORG ID HERE'  # Use your own organization ID.
time_delta_in_days = 30  # Max is 1 month per the firmware upgrades endpoint docs
actions_per_batch = 100  # Max number of actions to submit in a batch. 100 is the maximum. Bigger batches take longer.
wait_factor = 0.33  # Wait factor for action batches when the action batch queue is full.

# Firmware IDs; not needed for rescheduling, only for upgrading. If you plan to use this for upgrading, then you should
# first GET the availableVersions IDs and use those here instead, since they have probably changed from the time this
# was published.
mx_new_firmware_id = 2128  # Did you update this to your actual FW ID by GETing your availableFirmwareVersions?
mx_old_firmware_id = 2009  # Did you update this to your actual FW ID by GETing your availableFirmwareVersions?


def time_formatter(date_time_stamp):
	# Basic time formatter to return strings that the API requires
	formatted_date_time_stamp = date_time_stamp.replace(microsecond=0).isoformat() + 'Z'
	return formatted_date_time_stamp


# Time stamps
utc_now = datetime.datetime.utcnow()
utc_future = utc_now + datetime.timedelta(days=time_delta_in_days)
utc_now_formatted = time_formatter(utc_now)
utc_future_formatted = time_formatter(utc_future)


action_reschedule_existing = {
	"products": {
		"appliance":
			{
				"nextUpgrade": {
					"time": utc_future_formatted
				}
			}
	}
}

# Use this action to schedule a new upgrade. If you do not provide a time param (as shown above), it will execute
# immediately. IMPORTANT: See API docs for more info before using this.
action_schedule_new_upgrade = {
	"products": {
		"appliance":
			{
				"nextUpgrade": {
					"time": utc_future_formatted,
					"toVersion": {
						"id": mx_new_firmware_id
					}
				}
			}
	}
}


# GET the network list
networks_list = dashboard.organizations.getOrganizationNetworks(
	organizationId=organization_id
)


def format_single_action(resource, operation, body):
	# Combine a single set of batch components into an action
	action = {
		"resource": resource,
		"operation": operation,
		"body": body
	}

	return action


def create_single_upgrade_action(network_id):
	# Create a single upgrade action
	# AB component parts, rename action
	action_resource = f'/networks/{network_id}/firmwareUpgrades'
	action_operation = 'update'
	# Choose whether to reschedule an existing or start a new upgrade
	action_body = action_schedule_new_upgrade

	upgrade_action = format_single_action(action_resource, action_operation, action_body)

	return upgrade_action


def run_an_action_batch(org_id, actions_list, synchronous=False):
	# Create and run an action batch
	batch_response = dashboard.organizations.createOrganizationActionBatch(
		organizationId=org_id,
		actions=actions_list,
		confirmed=True,
		synchronous=synchronous
	)

	return batch_response


def create_action_list(net_list):
	# Creates a list of actions and returns it
	# Iterate through the list of network IDs and create an action for each, then collect it
	list_of_actions = list()

	for network in net_list:
		# Create the action
		single_action = create_single_upgrade_action(network['id'])
		list_of_actions.append(single_action)

	return list_of_actions


def batch_actions_splitter(batch_actions):
	# Split the list of actions into smaller lists of maximum 100 actions each
	# For each ID in range length of network_ids
	for i in range(0, len(batch_actions), actions_per_batch):
		# Create an index range for network_ids of 100 items:
		yield batch_actions[i:i + actions_per_batch]


def action_batch_runner(batch_actions_lists, org_id):
	# Create an action batch for each list of actions
	# Store the responses
	responses = list()
	number_of_batches = len(batch_actions_lists)
	number_of_batches_submitted = 0
	wait_seconds = int(30)

	# Make a batch for each list
	for batch_action_list in batch_actions_lists:
		action_batch_queue_checker(org_id)
		batch_response = run_an_action_batch(org_id, batch_action_list)
		responses.append(batch_response)
		number_of_batches_submitted += 1

		# Inform user of progress.
		print(f'Submitted batch {number_of_batches_submitted} of {number_of_batches}.')

	return responses


def action_batch_queue_checker(org_id):
	all_action_batches = dashboard.organizations.getOrganizationActionBatches(organizationId=org_id)
	running_action_batches = [batch for batch in all_action_batches if batch['status']['completed'] is False and batch['status']['failed'] is False]
	total_running_actions = 0

	for batch in running_action_batches:
		batch_actions = len(batch['actions'])
		total_running_actions += batch_actions

	wait_seconds = total_running_actions * wait_factor

	while len(running_action_batches) > 4:
		print(f'There are already five action batches in progress with a total of {total_running_actions} running actions. Waiting {wait_seconds} seconds.')
		time.sleep(wait_seconds)
		print('Checking again.')

		all_action_batches = dashboard.organizations.getOrganizationActionBatches(organizationId=org_id)
		running_action_batches = [batch for batch in all_action_batches if batch['status']['completed'] is False and batch['status']['failed'] is False]
		total_running_actions = 0

		for batch in running_action_batches:
			batch_actions = len(batch['actions'])
			total_running_actions += batch_actions

		wait_seconds = total_running_actions * wait_factor


# Create a list of upgrade actions
upgrade_actions_list = create_action_list(networks_list)

# Split the list into multiple lists of max 100 items each
upgrade_actions_lists = list(batch_actions_splitter(upgrade_actions_list))

# Run the action batches to clone the networks
upgraded_networks_responses = action_batch_runner(upgrade_actions_lists, organization_id)
