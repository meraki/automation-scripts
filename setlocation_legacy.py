# This is a simple script that updates the street address for all
#  devices in a network to a value given as a command line parameter.
#
# This is an earlier version of script setlocation.py that was created before the option to move
#  map markers when changing the street address of a device via API was introduced. Please refer to
#  setlocation.py for a more efficient way to set device location, without the need for a Google API
#  key. This script has been preserved as an example of how multiple APIs can be combined.
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#
# To use parameter "-g", you will need to have the Google Geocoding API activated.
#  Read more and activate your key here:
#  https://developers.google.com/maps/documentation/geocoding/intro
#
# To run the script, enter:
#  python setlocation_legacy.py -k <Meraki API key> [-g <Google API key>] -o <org name> -n <network name> -l <street address>
#
# Parameter "-g" is optional. If a valid Google API key is provided, the script will attempt to geocode the address
#  and move the map markers close to the street address defined in parameter "-l".
#
# This file was last modified on 2017-07-04



import sys, getopt, requests, json

def printhelp():
	#prints help text

	print('This script updates the street address of every device in a network to a value given as a parameter.')
	print('Map markers will also be moved close to this address if a Google API key is given (parameter "-g").')
	print('')
	print('Script syntax:')
	print('python setlocation_legacy.py -k <Meraki API key> [-g <Google API key>] -o <org name> -n <network name> -l <street address>')
	print('')
	print('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive')
	
def getgooglecoordinates(p_googlekey, p_address):
	#looks up for the Geocoordinates of an address
	# in the Google Geolocation API
		
	r = requests.get('https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s' % (p_address, p_googlekey) )
	
	rjson = r.json()
		
	returnvalue = {}
	if (r.status_code != requests.codes.ok) or (rjson['status'] != 'OK'):
		returnvalue['status'] = 'null'
		return(returnvalue)
	
	return(rjson)
	
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
	
def getnwdevices(p_apikey, p_shardurl, p_nwid):
	#returns list of devices in a network
	#on failure returns list with one device record, with all values 'null'

	r = requests.get('https://%s/api/v0/networks/%s/devices' % (p_shardurl, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue.append({'lat':0.0,'lng':0.0,'address':'null','lanIp':'null','serial':'null','mac':'null','tags':'null','name':'null','model':'null','networkId':'null'})
		return(returnvalue)
	
	rjson = r.json()
	
	return(rjson) 

def setdevicedata(p_apikey, p_shardurl, p_nwid, p_devserial, p_field, p_value):
	#modifies value of device record. Returns the new value
	#on failure returns one device record, with all values 'null'
	
	r = requests.put('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_devserial), data=json.dumps({p_field: p_value}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
			
	if r.status_code != requests.codes.ok:
		return ('null')
	
	return('ok')
	
def setdeviceaddress(p_apikey, p_shardurl, p_nwid, p_devserial, p_address, p_lat, p_lng):
	r = requests.put('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_devserial), data=json.dumps({'address' : p_address, 'lat' : p_lat, 'lng' : p_lng}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
			
	if r.status_code != requests.codes.ok:
		return ('null')
	
	return('ok')
	
def mappositions(p_latseed, p_lngseed, p_length, p_increment):
	#returns a list of map position data for placing
	#devices in in a cluster around a seed location
    #may return up to 3 extra location records. These should be ignored
	
	mpos = {'lat': [p_latseed], 'lng': [p_lngseed]}
	
	step = 1
	#MODIFY latmod AND lngmod IF AP CLUSTER LAT AND LNG DISTANCES ARE NOT PROPORTIONAL
	latmod = p_increment * 0.5
	lngmod = -1*p_increment
	i = 0
	
	while (len(mpos['lng']) < p_length):
		for j in range (i, step):
			mpos['lng'].append(mpos['lng'][len(mpos['lng'])-1])
			mpos['lat'].append(mpos['lat'][len(mpos['lat'])-1] + latmod)
		for j in range (i, step):
			mpos['lng'].append(mpos['lng'][len(mpos['lng'])-1] + lngmod)
			mpos['lat'].append(mpos['lat'][len(mpos['lat'])-1])
		step += 2
		latmod = -1 * latmod
		lngmod = -1 * lngmod
		i += 1
	
	return(mpos)

def main(argv):

	#get command line arguments
	arg_apikey = 'null'
	arg_googlekey = 'null'
	arg_orgname = 'null'
	arg_nwname = 'null'
	arg_location = 'null'
		
	try:
		opts, args = getopt.getopt(argv, 'hk:g:o:n:l:')
	except getopt.GetoptError:
		printhelp()
		sys.exit(2)
	
	for opt, arg in opts:
		if opt == '-h':
			printhelp()
			sys.exit()
		elif opt == '-k':
			arg_apikey = arg
		elif opt == '-g':
			arg_googlekey = arg
		elif opt == '-o':
			arg_orgname = arg
		elif opt == '-n':
			arg_nwname = arg
		elif opt == '-l':
			arg_location = arg
			
	if arg_apikey == 'null' or arg_orgname == 'null' or arg_nwname == 'null' or arg_location == 'null':
		printhelp()
		sys.exit(2)
			
	#check if Google API key has been provided, flag if not
	if arg_googlekey != 'null':
		#get X,Y coordinates corresponding to street address
		gresponse = getgooglecoordinates(arg_googlekey, arg_location)
		if gresponse['status'] == 'null':
			print('Unable to get coordinates for street address using Google Geocoding API')
			sys.exit(2)

		glatitude = gresponse['results'][0]['geometry']['location']['lat']
		glongitude = gresponse['results'][0]['geometry']['location']['lng']
	else:
		#no google key received, flag it
		glatitude = 'null'
		glongitude = 'null'
						
	#get organization id corresponding to org name provided by user
	orgid = getorgid(arg_apikey, arg_orgname)
	if orgid == 'null':
		print('Fetching organization failed')
		sys.exit(2)
	
	#get shard URL where Org is stored
	shardurl = getshardurl(arg_apikey, orgid)
	if shardurl == 'null':
		print('ERROR: Fetching Meraki cloud shard URL failed')
		sys.exit(2)	
	
	# get network id corresponding to nw name provided by user
	nwid = getnwid(arg_apikey, shardurl, orgid, arg_nwname)
	if nwid == 'null':
		print('Fetching network failed')
		sys.exit(2)
	
	#compile a list of device info for network
	nwdevicelist = getnwdevices(arg_apikey, shardurl, nwid)
	
	if nwdevicelist[0]['serial'] == 'null':
		print('Fetching devices failed')
		sys.exit(2)
	
	#update all devices in list one by one
	#check if Google API key has been provided or not. set address and (lat,lng) accordingly
	mappos = {}
	if glongitude != 'null': 
		#calculate map positions for devices to place them in a nice cluster around the geocoded address
		mappos = mappositions(float(glatitude), float(glongitude), len(nwdevicelist), 0.00005)
		
		print('Setting street address for network ID %s to %s (%s, %s)' % (nwid, arg_location, glatitude, glongitude))
	
		for i in range (0, len(nwdevicelist)):
			print('Updating device %s...' % (nwdevicelist[i]['serial']))	
			setdeviceaddress(arg_apikey, shardurl, nwid, nwdevicelist[i]['serial'], arg_location, '%f' % mappos['lat'][i], '%f' % mappos['lng'][i])
	else:
		print('Setting street address for network ID %s to %s' % (nwid, arg_location))
		
		for i in range (0, len(nwdevicelist)):
			print('Updating device %s...' % (nwdevicelist[i]['serial']))
			setdevicedata(arg_apikey, shardurl, nwid, nwdevicelist[i]['serial'], 'address', arg_location)
		
	print('End of script')
		
if __name__ == '__main__':
	main(sys.argv[1:])