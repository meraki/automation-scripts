# This is a script to migrate the switchport configuration of one organization to another.
#
# The script can be used to export switchport configuration of a source org to a file and 
#  import it to a destination org. The script will look for the exact same network names and
#  device serial numbers, as they were in the source org. Use copynetworks.py and movedevices.py
#  to migrate networks and devices if needed. The recommended migration workflow is:
#   * Copy networks with copynetworks.py
#   * Export device info with movedevices.py -m export
#   * Export switchport configuration with copyswitchcfg.py -m export
#   * Run additional export scripts
#   * Remove devices from networks with movedevices.py -m remove
#   * Unclaim devices manually and wait for them to become claimable again
#   * Import device info with movedevices.py -m import
#   * Import switchport configuration with copyswitchcfg.py -m import
#   * Run additional import scripts
#
# The script will only process devices that are part of a network.
# It has 2 modes of operation:
#  * python copyswitchcfg.py -k <key> -o <org> -m export -f <file>
#     This mode will export switchport configuration of all swithces in the org to a file.
#	  This is the default mode.
#  * python copyswitchcfg.py -k <key> -o <org> -m import -f <file>
#     Import all switchport configuration in <file> to the specified organization. 
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python copyswitchcfg.py -k <key> -o <org> [-m export/import] -f <file>
#
# If option -m is not defined, export mode will be assumed. The 2 valid forms of this parameter are:
#  -m export
#  -m import
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @

import sys, getopt, requests, json

def printusertext(p_message):
	#prints a line of text that is meant for the user to read
	#do not process these lines when chaining scripts
	print('@ %s' % p_message)

def printhelp():
	#prints help text

	printusertext('# This is a script to migrate the switchport configuration of one organization to another.')
	printusertext('')
	printusertext('Usage:')
	printusertext('python copyswitchcfg.py -k <key> -o <org> [-m export/import] -f <file>')
	printusertext('')
	printusertext('If option -m is not defined, export mode will be assumed.')
	printusertext('The 2 valid forms of this parameter are:')
	printusertext(' -m export')
	printusertext(' -m import')
	printusertext('')
	printusertext(' # python copyswitchcfg.py -k <key> -o <org> -m export -f <file>')
	printusertext('    This mode will export switchport configuration of all swithces in the org to a file.')
	printusertext('	   This is the default mode.')
	printusertext(' # python copyswitchcfg.py -k <key> -o <org> -m import -f <file>')
	printusertext('    Import all switchport configuration in <file> to the specified organization.')
	printusertext('')
	printusertext('The script will only process devices that are part of a network.')
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
	return("api.meraki.com")
	
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
	
def getswitchports(p_apikey, p_shardurl, p_devserial):
	#returns switchport info for a device
	
	r = requests.get('https://%s/api/v0/devices/%s/switchPorts' % (p_shardurl, p_devserial), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
		
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue.append({'number': 'null'})
		return(returnvalue)
	
	return(r.json())
	
def setswportconfig(p_apikey, p_shardurl, p_devserial, p_portnum, p_portcfg):
	#sets switchport configuration to match table given as parameter
	
	r = requests.put('https://%s/api/v0/devices/%s/switchPorts/%s' % (p_shardurl, p_devserial, p_portnum), data=json.dumps({'isolationEnabled': p_portcfg['isolationEnabled'], 'rstpEnabled': p_portcfg['rstpEnabled'], 'enabled': p_portcfg['enabled'], 'stpGuard': p_portcfg['stpGuard'], 'accessPolicyNumber': p_portcfg['accessPolicyNumber'], 'type': p_portcfg['type'], 'allowedVlans': p_portcfg['allowedVlans'], 'poeEnabled': p_portcfg['poeEnabled'], 'name': p_portcfg['name'], 'tags': p_portcfg['tags'], 'number': p_portcfg['number'], 'vlan': p_portcfg['vlan'], 'voiceVlan': p_portcfg['voiceVlan']}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
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
			
	#check if parameter -m has one a valid value. blank is also OK, as export is default
	mode_export = True
	modenotvalid = True
	if arg_mode == 'import':
		modenotvalid = False
		mode_export = False
	elif arg_mode == 'export':
		modenotvalid = False
	
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
	
	#if export mode, open file for writing. if import mode, open file for reading
	if mode_export:
		#if parameter -m export, open file for writing
		try:
			f = open(arg_filepath, 'w')
		except:
			printusertext('ERROR: Unable to open file for writing')
			sys.exit(2)
	else:
		#if parameter -m import, open file for reading
		try:
			f = open(arg_filepath, 'r')
		except:
			printusertext('ERROR: Unable to open file for reading')
			sys.exit(2)
		
	#define list for all switchports for source org
	orgswitchports = []
		
	if mode_export:
		#devices in network
		devicelist = []
		#switchports in a single device
		devswitchports = []
		
		for nwrecord in nwlist:
			#all switchports in a single network
			nwswitchports = []
			devicelist = getdevicelist(arg_apikey, shardurl, nwrecord['id'])
			for devrecord in devicelist:
				#get switchports in device
				devswitchports = getswitchports(arg_apikey, shardurl, devrecord['serial'])
				#devswitchports [0]['number'] will be 'null' if anything went wrong (device not an MS switch, etc)
				if devswitchports [0]['number'] != 'null':
					#append dev switchports to network list
					nwswitchports.append( {'serial': devrecord['serial'], 'devports' : devswitchports} )
			if len(nwswitchports) > 0:
				orgswitchports.append( {'network': nwrecord['name'], 'nwports': nwswitchports} )
			else:
				printusertext('WARNING: Skipping network "%s": No switchports' % nwrecord['name'])

		#write org switchports' list to file
		try:
			json.dump(orgswitchports, f)
		except:
			printusertext('ERROR: Writing to output file failed')
			sys.exit(2)		
	else:
		#import mode
		
		#read org switchports' list from file
		try:
			orgswitchports = json.load(f)
		except:
			printusertext('ERROR: Reading from file failed')
			sys.exit(2)	
				
		#upload switchport configuration to Dashboard
		for nwrecord in orgswitchports:
			for devrecord in nwrecord['nwports']:
				printusertext('INFO: Configuring device %s' % devrecord['serial'])
				for swport in devrecord['devports']:
					setswportconfig(arg_apikey, shardurl, devrecord['serial'], swport['number'], swport)
		
	printusertext('End of script.')
			
if __name__ == '__main__':
	main(sys.argv[1:])