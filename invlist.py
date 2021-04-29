# This script prints a list of all in-use devices in an organization
#  to sdtout or a file (Devices which are part of a network are considered in-use).
#  The fields printed are 'serial' and 'model' separated by a comma (,).
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python invlist.py -k <API key> -o <org name> [-f <file path>]
#
# If option -f is not defined, the script will print to stdout.
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

	printusertext("This is a script that prints a list of an organization's devices to sdtout or a file.")
	printusertext('')
	printusertext('Usage:')
	printusertext('python invlist.py -k <API key> -o <org name> [-f <file path>]')
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
	
		
def main(argv):
	#get command line arguments
	arg_apikey = 'null'
	arg_orgname = 'null'
	arg_filepath = 'null'
		
	try:
		opts, args = getopt.getopt(argv, 'hk:o:f:')
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
		elif opt == '-f':
			arg_filepath = arg
			
	if arg_apikey == 'null' or arg_orgname == 'null':
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
	
	#if user selected to print in file, set flag & open for writing
	filemode = False
	if arg_filepath != 'null':
		try:
			f = open(arg_filepath, 'w')
		except:
			printusertext('ERROR: Unable to open output file for writing')
			sys.exit(2)
		filemode = True
	
	devicelist = []
	for nwrecord in nwlist:
		#get devices' list
		devicelist = getdevicelist(arg_apikey, shardurl, nwrecord['id'])
		#append list to file or stdout
		if filemode:
			for i in range (0, len(devicelist)):
				try:
					#MODIFY THE LINE BELOW TO CHANGE OUTPUT FORMAT
					f.write('%s,%s\n' % (devicelist[i]['serial'], devicelist[i]['model']))
				except:
					printusertext('ERROR: Unable to write device info to file')
					sys.exit(2)
		else:
			for i in range (0, len(devicelist)):
				#MODIFY THE LINE BELOW TO CHANGE OUTPUT FORMAT
				print('%s,%s' % (devicelist[i]['serial'], devicelist[i]['model']))
			
if __name__ == '__main__':
	main(sys.argv[1:])