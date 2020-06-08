# This script that can be used to move all devices from one organization to another.
# The script will only process devices that are part of a network.
# It has 3 modes of operation:
#  # python movedevices.py -k <key> -o <org> -m export -f <file>
#     This mode will export a list of all devices in an organization and the networks 
#     they belong to to a file. This is the default mode.
#  # python movedevices.py -k <key> -o <org> -m remove -f <file>
#     Export a list of all devices in an org by network and remove them from their networks.
#     Please note that this will not unclaim the devices from the original org, since unclaiming 
#     via API is not supported at time of writing.
#  # python movedevices.py -k <key> -o <org> -m import -f <file>
#     Import all devices listed in <file> to the specified organization. 
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python movedevices.py -k <key> -o <org> [-m export/remove/import] -f <file>
#
# If option -r is not defined, devices will not be removed from their networks.
# If option -m is not defined, export mode will be assumed. The 3 valid forms of this parameter are:
#  -m export
#  -m remove
#  -m import
#
# To make script chaining easier, all lines not containing a 
#  device record start with the character @

import sys, getopt, requests, json

def printusertext(p_message):
	#prints a line of text that is meant for the user to read
	#do not process these lines when chaining scripts
	print('@ %s' % p_message)

def printhelp():
	#prints help text

	printusertext('This script that can be used to move all devices from one organization to another.')
	printusertext('The script will only process devices that are part of a network.')
	printusertext('')
	printusertext('Usage:')
	printusertext('python movedevices.py -k <Meraki API key> -o <Organization name> [-m export/remove/import] -f <file>')
	printusertext('')
	printusertext('The script has 3 modes of operation:')
	printusertext(' # python movedevices.py -k <key> -o <org> -m export -f <file>')
	printusertext('    This mode will export a list of all devices in an organization and the networks')
	printusertext('    they belong to to a file. This is the default mode.')
	printusertext(' # python movedevices.py -k <key> -o <org> -m remove -f <file>')
	printusertext('    Export a list of all devices in an org by network and remove them from their networks.')
	printusertext('    Please note that this will not unclaim the devices from the original org, since unclaiming')
	printusertext('    via API is not supported at time of writing.')
	printusertext(' # python movedevices.py -k <key> -o <org> -m import -f <file>')
	printusertext('    Import all devices listed in <file> to the specified organization.')
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
	#patch
	return("api-mp.meraki.com")
	
def getnwlist(p_apikey, p_shardurl, p_orgid):
	#returns a list of all networks in an organization
	#on failure returns a single record with 'null' name and id
	
	r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue.append({'name': 'null', 'id': 'null'})
		return(returnvalue)
	
	return(r.json())
	
def getdevicelist(p_apikey, p_shardurl, p_nwid):
	#returns a list of all devices in a network
	
	r = requests.get('https://%s/api/v0/networks/%s/devices' % (p_shardurl, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
		
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue.append({'serial': 'null', 'model': 'null'})
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
	
def removedevicefromnw(p_apikey, p_shardurl, p_nwid, p_devserial):
	#removes a device from its parent network. does not unclaim it
	
	r = requests.post('https://%s/api/v0/networks/%s/devices/%s/remove' % (p_shardurl, p_nwid, p_devserial), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	return (0)
	
def claimdevice(p_apikey, p_shardurl, p_nwid, p_devserial):
	#claims a device into an org
	
	r = requests.post('https://%s/api/v0/networks/%s/devices/claim' % (p_shardurl, p_nwid), data=json.dumps({'serial': p_devserial}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	return (0)
		
def main(argv):
	#set default values for command line arguments
	arg_apikey = 'null'
	arg_orgname = 'null'
	arg_mode = 'export'
	arg_filepath = 'null'
		
	#get command line arguments
	try:
		opts, args = getopt.getopt(argv, 'hk:o:m:f:')
	except getopt.GetoptError:
		printhelp()
		sys.exit(2)
	
	for opt, arg in opts:
		if opt == '-h':
			printhelp()
			sys.exit()
		elif opt == '-k':
			arg_apikey = arg
		elif opt == '-o':
			arg_orgname = arg
		elif opt == '-m':
			arg_mode = arg
		elif opt == '-f':
			arg_filepath = arg
			
	#check if parameter -m has one of three valid values. blank is also OK, as export is default
	mode_import = False
	mode_remove = False
	modenotvalid = True
	if arg_mode == 'import':
		modenotvalid = False
		mode_import = True
	elif arg_mode == 'export':
		modenotvalid = False
	elif arg_mode == 'remove':
		modenotvalid = False
		mode_remove = True
	
	#check if all parameters are required parameters have been given
	if arg_apikey == 'null' or arg_orgname == 'null' or arg_filepath == 'null' or modenotvalid:
		printhelp()
		sys.exit(2)
	
	#get organization id corresponding to org name provided by user
	orgid = getorgid(arg_apikey, arg_orgname)
	if orgid == 'null':
		printusertext('ERROR: Fetching organization failed')
		sys.exit(2)
	
	#get shard URL where Org is stored
	shardurl = getshardurl(arg_apikey, orgid)
	if shardurl == 'null':
		printusertext('ERROR: Fetching Meraki cloud shard URL failed')
		sys.exit(2)
	
	#get network list for fetched org id
	nwlist = getnwlist(arg_apikey, shardurl, orgid)
		
	if nwlist[0]['id'] == 'null':
		printusertext('ERROR: Fetching network list failed')
		sys.exit(2)
	
	#if export or remove mode, open file for writing. if import mode, open file for reading
	if mode_import:
		#if parameter -m import, open file for reading
		try:
			f = open(arg_filepath, 'r')
		except:
			printusertext('ERROR: Unable to open file for reading')
			sys.exit(2)
	else:
	#if parameter -m export or remove, open file for reading
		try:
			f = open(arg_filepath, 'w')
		except:
			printusertext('ERROR: Unable to open file for writing')
			sys.exit(2)
	
	if not(mode_import):
		devicelist = []
		for nwrecord in nwlist:
			#write network name to file
			try:
				#MODIFY THE LINE BELOW TO CHANGE OUTPUT FORMAT
				f.write('#%s\n' % nwrecord['name'])
			except:
				printusertext('ERROR: Unable to write network info to file')
				sys.exit(2)
			#get devices' list
			devicelist = getdevicelist(arg_apikey, shardurl, nwrecord['id'])
			#append list to file or stdout
			for i in range (0, len(devicelist)):
				try:
					#MODIFY THE LINE BELOW TO CHANGE OUTPUT FORMAT
					f.write('%s\n' % (devicelist[i]['serial']))
				except:
					printusertext('ERROR: Unable to write device info to file')
					sys.exit(2)
				if mode_remove:
					removedevicefromnw(arg_apikey, shardurl, nwrecord['id'], devicelist[i]['serial'])
	else:
		#parameter -m import
		printusertext('Attempting to claim devices. If nothing happens, please check that the device')
		printusertext('serial numbers have been unclaimed and wait before running again. It can take')
		printusertext('up to a few hours for a device to become available for claiming.')
		
		nwname = 'null'
		nwid = 'null'
		devserial = 'null'
		for line in f:
			if line[0] == '#':
				nwname = line[1:].rstrip()
				nwid = getnwid(arg_apikey, shardurl, orgid, nwname)
				if nwid == 'null':
					printusertext('ERROR: Network "%s" does not exist in target org.' % nwname)
					sys.exit(2)
			else:
				devserial = line.rstrip()
				claimdevice(arg_apikey, shardurl, nwid, devserial)
	
	printusertext('End of script.')
			
if __name__ == '__main__':
	main(sys.argv[1:])