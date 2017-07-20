# This exports all networks and their base attributes from an organization to a file
#  and then imports them to another organization.
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python copynetworks.py -k <API key> [-s <source org name>] [-d <destination org name>] [-f <file path>]
#
# Parameters '-s', '-d' and '-f' are optional, but at least two of them must be given.
#
# ** If '-s' and '-d' are given, data will be copied from src org to dst org
# ** If '-s' and '-f' are given, data will be dumped from src org to file
# ** If '-d' and '-f' are given, data will be imported from file to dst org
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-04-06

import sys, getopt, requests, json

def printusertext(p_message):
	#prints a line of text that is meant for the user to read
	#do not process these lines when chaining scripts
	print('@ %s' % p_message)

def printhelp():
	#prints help text

	printusertext('This is a script that copies networks and their base attributes from a source organization')
	printusertext('to another, called the destination organization. Both source, destination org and file ')
	printusertext('parameters are optional, but at least two of them must be given.')
	printusertext('')
	printusertext('Usage:')
	printusertext('python copynetworks.py -k <API key> [-s <source org name>] [-d <dest org name>] [-f <file path>]')
	printusertext('')
	printusertext(" ** If '-s' and '-d' are given, data will be copied from src org to dst org")
	printusertext(" ** If '-s' and '-f' are given, data will be dumped from src org to file")
	printusertext(" ** If '-d' and '-f' are given, data will be imported from file to dst org")
	printusertext('')
	printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')
	
def getorgid(p_apikey, p_orgname):
	#looks up org id for a specific org name
	#on failure returns 'null'
	
	r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	if r.status_code != requests.codes.ok:
		return 'null'
	
	rjson = r.json()
	
	
	for record in rjson:
		if record['name'] == p_orgname:
			return record['id']
	return('null')
	
def getshardurl(p_apikey, p_orgid):
	#Looks up shard URL for a specific org. Use this URL instead of 'dashboard.meraki.com'
	# when making API calls with API accounts that can access multiple orgs.
	#On failure returns 'null'
	
	r = requests.get('https://dashboard.meraki.com/api/v0/organizations/%s/snmp' % p_orgid, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	if r.status_code != requests.codes.ok:
		return 'null'
		
	rjson = r.json()

	return(rjson['hostname'])
	
def getnwlist(p_apikey, p_shardurl, p_orgid):
	#returns a list of all networks in an organization
	#on failure returns a single record with 'null' name and id
	
	r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue.append({'name': 'null', 'id': 'null'})
		return(returnvalue)
	
	return(r.json())
	
def getnwid(p_apikey, p_shardurl, p_orgid, p_nwname):
	#looks up network id for a network name
	#on failure returns 'null'

	r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	if r.status_code != requests.codes.ok:
		return 'null'
	
	rjson = r.json()
	
	for record in rjson:
		if record['name'] == p_nwname:
			return record['id']
	return('null') 	

def createnw (p_apikey, p_shardurl, p_dstorg, p_nwdata):
	#creates network if one does not already exist with the same name
	
	#check if network exists
	getnwresult = getnwid(p_apikey, p_shardurl, p_dstorg, p_nwdata['name'])
	if getnwresult != 'null':
		printusertext('WARNING: Skipping network "%s" (Already exists)' % p_nwdata['name'])
		return('null')
	
	if p_nwdata['type'] == 'combined':
		#find actual device types
		nwtype = 'wireless switch appliance'
	else:
		nwtype = p_nwdata['type']
	if nwtype != 'systems manager':
		r = requests.post('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_dstorg), data=json.dumps({'timeZone': p_nwdata['timeZone'], 'tags': p_nwdata['tags'], 'name': p_nwdata['name'], 'organizationId': p_dstorg, 'type': nwtype}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	else:
		printusertext('WARNING: Skipping network "%s" (Cannot create SM networks)' % p_nwdata['name'])
		
	return('ok')
	
		
def main(argv):
	#get command line arguments
	arg_apikey = 'null'
	arg_srcorg = 'null'
	arg_dstorg = 'null'
	arg_filepath = 'null'
		
	try:
		opts, args = getopt.getopt(argv, 'hk:s:d:f:')
	except getopt.GetoptError:
		printhelp()
		sys.exit(2)
	
	for opt, arg in opts:
		if opt == '-h':
			printhelp()
			sys.exit()
		elif opt == '-k':
			arg_apikey = arg
		elif opt == '-s':
			arg_srcorg = arg
		elif opt == '-d':
			arg_dstorg = arg
		elif opt == '-f':
			arg_filepath = arg
	
	#count how many optional parameters have been given
	optionscounter = 0
	if arg_srcorg != 'null':
		optionscounter += 1
	if arg_dstorg != 'null':
		optionscounter += 1
	if arg_filepath != 'null':
		optionscounter += 1
	
	if arg_apikey == 'null' or optionscounter < 2:
		printhelp()
		sys.exit(2)
	
	#get source organization id corresponding to org name provided by user
	mode_gotsource = True
	if arg_srcorg == 'null':
		mode_gotsource = False
	else:
		srcorgid = getorgid(arg_apikey, arg_srcorg)
		if srcorgid == 'null':
			printusertext('ERROR: Fetching source organization failed')
			sys.exit(2)
		#get shard URL where Org is stored
		srcshardurl = getshardurl(arg_apikey, srcorgid)
		if srcshardurl == 'null':
			printusertext('ERROR: Fetching Meraki cloud shard URL for source org failed')
			printusertext('       Does it have API access enabled?')
			sys.exit(2)
	
	#get destination organization id corresponding to org name provided by user
	mode_gotdestination = True
	if arg_dstorg == 'null':
		mode_gotdestination = False
	else:
		dstorgid = getorgid(arg_apikey, arg_dstorg)
		if dstorgid == 'null':
			printusertext('ERROR: Fetching destination organization failed')
			sys.exit(2)
		#get shard URL where Org is stored
		dstshardurl = getshardurl(arg_apikey, dstorgid)
		if dstshardurl == 'null':
			printusertext('ERROR: Fetching Meraki cloud shard URL for destination org failed')
			printusertext('       Does it have API access enabled?')
			sys.exit(2)
	
	#if user gave a source, fetch networks and their attributes from src org
	if mode_gotsource:
		nwlist = getnwlist(arg_apikey, srcshardurl, srcorgid)
		
		if nwlist[0]['id'] == 'null':
			printusertext('ERROR: Fetching network list from source org failed')
			sys.exit(2)
	
	#open buffer file for writing
	mode_gotfile = True
	if arg_filepath == 'null':
		mode_gotfile = False
	if mode_gotfile:
		#if source given, open file for writing (output)
		if mode_gotsource:
			try:
				f = open(arg_filepath, 'w')
			except:
				printusertext('ERROR: Unable to open file for writing')
				sys.exit(2)
		#if source omitted, open file for reading (input)
		else:
			try:
				f = open(arg_filepath, 'r')
			except:
				printusertext('ERROR: Unable to open file for reading')
				sys.exit(2)
	
	#if user gave a source and a file, dump source org networks to file
	if mode_gotsource and mode_gotfile:
		try:
			json.dump(nwlist, f)
		except:
				printusertext('ERROR: Writing to output file failed')
				sys.exit(2)
	
	#if user did not give source, but gave file, load networks list from file
	if not(mode_gotsource) and mode_gotfile:
		try:
			nwlist = json.load(f)
		except:
				printusertext('ERROR: Reading from input file failed')
				sys.exit(2)
	
	#if user gave destination org, create networks according to nwlist content
	if mode_gotdestination:
		i = 0
		for i in range (0, len(nwlist)):
			createnw (arg_apikey, dstshardurl, dstorgid, nwlist[i])
							
	#reached end of script
	printusertext('End of script.')
				
if __name__ == '__main__':
	main(sys.argv[1:])