# This is a script to migrate the MX VLAN configuration of one organization to another.
#
# The script can be used to export MX VLAN configuration of a source org to a file and 
#  import it to a destination org. The script will look for the exact same network names
#  as they were in the source org. Use copynetworks.py and movedevices.py
#  to migrate networks and devices if needed. The recommended migration workflow is:
#   * Copy networks with copynetworks.py
#   * Export device info with movedevices.py -m export
#   * Export MX VLAN configuration with copymxvlans.py -m export
#   * Run additional export scripts
#   * Remove devices from networks with movedevices.py -m remove
#   * Unclaim devices manually and wait for them to become claimable again
#   * Import device info with movedevices.py -m import
#	* Manually enable VLAN support on every MX you want to copy VLANs for
#   * Import MX VLAN configuration with copymxvlans.py -m importall or copymxvlans.py -m importnew
#   * Run additional import scripts
#
# The script will only process devices that are part of a network.
# It has 3 modes of operation:
#  * python copymxvlans.py -k <key> -o <org> -m export -f <file>
#     This mode will export MX VLAN configuration of all MX appliances in the org to a file.
#	  This is the default mode.
#  * python copymxvlans.py -k <key> -o <org> -m importall -f <file>
#     Import all MX VLAN configuration in <file> to the specified organization. If a VLAN exists, it 
#     will be updated to match the configuration in <file>.
#  * python copymxvlans.py -k <key> -o <org> -m importnew -f <file>
#     Import MX VLAN configuration in <file> to the specified organization for VLANs that don't already
#	  exist in destination org. If a VLAN exists, it will be skipped.
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python copymxvlans.py -k <key> -o <org> [-m export/importall/importnew] -f <file>
#
# If option -m is not defined, export mode will be assumed. The 3 valid forms of this parameter are:
#  -m export
#  -m importall
#  -m importnew
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-05-10

import sys, getopt, requests, json

def printusertext(p_message):
	#prints a line of text that is meant for the user to read
	#do not process these lines when chaining scripts
	print('@ %s' % p_message)

def printhelp():
	#prints help text

	printusertext('')
	printusertext('This is a script to migrate the MX VLAN configuration of one organization to another.')
	printusertext('For import modes to work, the target MX will need to have VLAN support enabled.')
	printusertext('')
	printusertext('Usage:')
	printusertext('python copymxvlans.py -k <key> -o <org> [-m export/importall/importnew] -f <file>')
	printusertext('')
	printusertext('If option -m is not defined, export mode will be assumed.')
	printusertext('The 3 valid forms of this parameter are:')
	printusertext(' -m export')
	printusertext(' -m importall')
	printusertext(' -m importnew')
	printusertext('')
	printusertext(' # python copymxvlans.py -k <key> -o <org> -m export -f <file>')
	printusertext('    This mode will export MX VLAN configuration of all MX appliances in the org to a file.')
	printusertext('	   This is the default mode.')
	printusertext(' # python copymxvlans.py -k <key> -o <org> -m importall -f <file>')
	printusertext('    Import all MX VLAN configuration in <file> to the specified organization. Update')
	printusertext('    VLANs to match configuration found in file.')
	printusertext(' # python copymxvlans.py -k <key> -o <org> -m importnew -f <file>')
	printusertext('    Import MX VLAN configuration in <file> to the specified organization. Skip VLANs')
	printusertext('    that already exist.')
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
	
def getvlanlist(p_apikey, p_shardurl, p_nwid):
	#returns list of all MX VLANs in a network
	
	r = requests.get('https://%s/api/v0/networks/%s/vlans' % (p_shardurl, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
		
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue.append({'id': 'null'})
		return(returnvalue)
	
	return(r.json())
	
def getvlandetails(p_apikey, p_shardurl, p_nwid, p_vlanid):
	#returns details for specified VLAN in specified network 
	
	#UNTESTED

	r = requests.get('https://%s/api/v0/networks/%s/vlans/%s' % (p_shardurl, p_nwid, p_vlanid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
		
	if r.status_code != requests.codes.ok:
		return({'id': 'null'})
	
	return(r.json())
	
def createvlan(p_apikey, p_shardurl, p_nwid, p_vlandata):
	#creates a new MX VLAN into the specified network
	
	#UNTESTED
	
	r = requests.post('https://%s/api/v0/networks/%s/vlans' % (p_shardurl, p_nwid), data=json.dumps({'id': p_vlandata['id'], 'name': p_vlandata['name'], 'applianceIp': p_vlandata['applianceIp'], 'subnet': p_vlandata['subnet'], 'fixedIpAssignments': p_vlandata['fixedIpAssignments'], 'reservedIpRanges': p_vlandata['reservedIpRanges'], 'dnsNameservers': p_vlandata['dnsNameservers']}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	return (0)
	
def updatevlan(p_apikey, p_shardurl, p_nwid, p_vlandata):
	#updates an existing MX VLAN in the specified org
	
	#UNTESTED
	
	r = requests.put('https://%s/api/v0/networks/%s/vlans/%s' % (p_shardurl, p_nwid, p_vlandata['id']), data=json.dumps({'name': p_vlandata['name'], 'applianceIp': p_vlandata['applianceIp'], 'subnet': p_vlandata['subnet'], 'fixedIpAssignments': p_vlandata['fixedIpAssignments'], 'reservedIpRanges': p_vlandata['reservedIpRanges'], 'dnsNameservers': p_vlandata['dnsNameservers']}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
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
	mode_updateexisting = False
	if arg_mode == 'importall':
		modenotvalid = False
		mode_export = False
		mode_updateexisting = True
	if arg_mode == 'importnew':
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
		
	#define list for all VLANS for source/destination org
	orgvlans = []
		
	if mode_export:
		#iterate all networks in org and gather their VLANs in a list. write list to file
		for nwrecord in nwlist:
			#VLANs in network
			nwvlanlist = getvlanlist(arg_apikey, shardurl, nwrecord['id'])
			if nwvlanlist[0]['id'] == 'null':
				printusertext('WARNING: Skipping network "%s": No MX VLANs' % nwrecord['name'])
			else:
				orgvlans.append( {'nwname': nwrecord['name'], 'nwvlans': nwvlanlist} )
			
		#write org MX VLANs' list to file
		try:
			json.dump(orgvlans, f)
		except:
			printusertext('ERROR: Writing to output file failed')
			sys.exit(2)		
	else:
		#import mode
		
		#read org VLANs' list from file
		try:
			orgvlans = json.load(f)
		except:
			printusertext('ERROR: Reading from file failed')
			sys.exit(2)	

		#upload MX VLAN configuration to Dashboard
		for nwrecord in orgvlans:
			#network ID might be different in destination org. get network id
			nwid = getnwid(arg_apikey, shardurl, orgid, nwrecord['nwname'])
			if nwid == 'null':
				printusertext('WARNING: Skipping network "%s": Does not exist' % nwrecord['nwname'])
			else:
				printusertext('INFO: Processing network "%s"' % nwrecord['nwname'])
				for vlanrecord in nwrecord['nwvlans']:
					#if VLAN exists, update it. else create VLAN
					vlanfound = getvlandetails(arg_apikey, shardurl, nwid, vlanrecord['id'])
					if vlanfound['id'] == 'null':
						#VLAN does not exist, create it
						createvlan(arg_apikey, shardurl, nwid, vlanrecord)
					elif mode_updateexisting == True:
						#if VLAN exists and user has selected to update existing
						updatevlan(arg_apikey, shardurl, nwid, vlanrecord)
					else:
						#if VLAN exists and user has selected to skip existing
						printusertext('WARNING: Skipping VLAN %s in network "%s": Already exists' % (vlanrecord['id'], nwrecord['nwname']) )
		
	printusertext('End of script.')
			
if __name__ == '__main__':
	main(sys.argv[1:])