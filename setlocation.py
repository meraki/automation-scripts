# This is a simple script that updates the street address for all
#  devices in a network to a value given as a command line parameter.
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#
# To run the script, enter:
#  python setlocation.py -k <Meraki API key> -o <org name> -n <network name> -l <street address> [-m <mode>]
#
# Valid options for attribute <network name> in parameter "-n":
#  * Name of a network in the given organisation: Update a single network with matching name
#  * /all: Update all networks in the given organisation
#
# Parameter "-m" is optional. Valid options for attribute <mode>:
#  * keep_marker: Update the street address field only without moving the map markers (default behaviour)
#  * move_marker: Update the street address field and move map markers to reflect changes
#  * move_marker_except_mr: Update street address for all devices in scope. Only move markers for non-MR devices
#
# Example:
#  python setlocation.py -k 1234 -o "My Customer" -n /all -l "500 Terry Francois, San Francisco"
#
# This file was last modified on 2017-07-03



import sys, getopt, requests, json

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

def printhelp():
    #prints help text

    printusertext(' This script updates the street address of every device in a network or organisation')
    printusertext('  to a value given as a parameter. Optionally, it also moves map markers.')
    printusertext('')
    printusertext(' To run the script, enter:')
    printusertext('  python setlocation.py -k <Meraki API key> -o <org name> -n <network name> -l <street address> [-m <mode>]')
    printusertext('')
    printusertext('Valid options for attribute <network name> in parameter "-n":')
    printusertext('  * Name of a network in the given organisation: Update a single network with matching name')
    printusertext('  * /all: Update all networks in the given organisation')
    printusertext('')
    printusertext(' Parameter "-m" is optional. Valid options for attribute <mode>:')
    printusertext('  * keep_marker: Update the street address field only, without moving the map markers (default mode)')
    printusertext('  * move_marker: Update the street address field and move map markers to reflect changes')
    printusertext('  * move_marker_except_mr: Update street address for all devices in scope. Only move markers for non-MR devices')
    printusertext('')
    printusertext(' Example:')
    printusertext('  python setlocation.py -k 1234 -o "My Customer" -n /all -l "500 Terry Francois, San Francisco" -m move_marker')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive')
    
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
    
def getnetworks(p_apikey, p_shardurl, p_orgid):
    #returns a list of all networks associated to an organisation ID.
        
    r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append('null')
        return (returnvalue)
        
    rjson = r.json()
    
    for i in range (0, len(rjson)):
        returnvalue.append(rjson[i]['id'])
    
    return (returnvalue)
    
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
        returnvalue.append({'serial':'null'})
        return(returnvalue)
    
    rjson = r.json()
    
    return(rjson) 

def getdeviceinfo(p_apikey, p_shardurl, p_nwid, p_serial):
	#returns info for a single device
	#on failure returns lone device record, with serial number 'null'

	r = requests.get('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_serial), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
	
	returnvalue = []
	if r.status_code != requests.codes.ok:
		returnvalue = {'serial':'null'}
		return(returnvalue)
	
	rjson = r.json()
	
	return(rjson)
	
def setdevicedata(p_apikey, p_shardurl, p_nwid, p_devserial, p_field, p_value, p_movemarker):
	#modifies value of device record. Returns the new value
	#on failure returns 'null'
	#p_movemarker is boolean: True/False
	
	movevalue = "false"
	if p_movemarker:
		movevalue = "true"
	
	r = requests.put('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_devserial), data=json.dumps({p_field: p_value, 'moveMapMarker': movevalue}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
			
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
    arg_orgname = 'null'
    arg_nwname = 'null'
    arg_location = 'null'
    arg_mode = 'keep_marker'
        
    try:
        opts, args = getopt.getopt(argv, 'hk:o:n:l:m:')
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
        elif opt == '-n':
            arg_nwname = arg
        elif opt == '-l':
            arg_location = arg
        elif opt == '-m':
            arg_mode = arg
            
    if arg_apikey == 'null' or arg_orgname == 'null' or arg_nwname == 'null' or arg_location == 'null':
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
    
    #create a list of network ids to be processed. If a name was given, it will only have one entry
    nwidlist = []
    nwid = 'null'
    
    if arg_nwname == '/all':
        nwidlist = getnetworks(arg_apikey, shardurl, orgid)
        if nwidlist[0] == 'null':
            printusertext('ERROR: Fetching network list failed')
            sys.exit(2)
           
    else:
        # get network id corresponding to network name provided by user
        nwid = getnwid(arg_apikey, shardurl, orgid, arg_nwname)
        if nwid == 'null':
            printusertext('ERROR: Fetching network failed')
            sys.exit(2)   
        nwidlist.append(nwid)
                
    nwdevicelist = []
    mappos = {}
    mc = 0
    
    #loop through the network ID list and process all of their devices
    for i in range( 0, len(nwidlist) ):        
        #compile a list of device info for network
        nwdevicelist = getnwdevices(arg_apikey, shardurl, nwidlist[i])
    
        if len(nwdevicelist) > 0:
            #check if issues with cloud communication
            if nwdevicelist[0]['serial'] == 'null':
                printusertext('ERROR: Fetching devices failed for network ID %s' % nwidlist[i])
                sys.exit(2)
                       
            #if not updating markers, just update address attribute for all devices
            if arg_mode == 'keep_marker':
                for j in range( 0, len(nwdevicelist) ):
                    setdevicedata(arg_apikey, shardurl, nwidlist[i], nwdevicelist[j]['serial'], 'address', arg_location, False)
                    
            elif arg_mode == 'move_marker':
                #updating markers for all devices
            
                #update location of the first device in the list
                setdevicedata(arg_apikey, shardurl, nwidlist[i], nwdevicelist[0]['serial'], 'address', arg_location, True)
          
                #get coordinates calculated for first device by the Meraki Cloud to use it as a seed
                deviceinfo = getdeviceinfo(arg_apikey, shardurl, nwidlist[i], nwdevicelist[0]['serial'])
                if deviceinfo['serial'] == 'null':
                    printusertext('ERROR: Setting or fetching device info failed')
                    sys.exit(2)   
                    
                #calculate map positions for additional devices
                mappos = mappositions(float(deviceinfo['lat']), float(deviceinfo['lng']), len(nwdevicelist), 0.0001)
                
                #place other devices in a spiral around the seed location
                for j in range ( 1, len(nwdevicelist)):
                    setdeviceaddress(arg_apikey, shardurl, nwidlist[i], nwdevicelist[j]['serial'], arg_location, '%f' % mappos['lat'][j], '%f' % mappos['lng'][j])
                
            elif arg_mode == 'move_marker_except_mr':
                #updating markers for non-MR devices
            
                #keep setting address info for MR devices until you hit a MS/MX device
                for j in range( 0, len(nwdevicelist) ):
                    if nwdevicelist[j]['model'][:2] == 'MR':
                        setdevicedata(arg_apikey, shardurl, nwidlist[i], nwdevicelist[j]['serial'], 'address', arg_location, False)
                    else:
                        break
                
                #if a MS/MX device was found, use its location as a seed location
                if j < len(nwdevicelist):
                    #update location of the next device in the list
                    setdevicedata(arg_apikey, shardurl, nwidlist[i], nwdevicelist[j]['serial'], 'address', arg_location, True)
          
                    #get coordinates calculated for next device by the Meraki Cloud to use it as a seed
                    deviceinfo = getdeviceinfo(arg_apikey, shardurl, nwidlist[i], nwdevicelist[j]['serial'])
                    if deviceinfo['serial'] == 'null':
                        printusertext('ERROR: Setting or fetching device info failed')
                        sys.exit(2)
                
                    #calculate map positions for rest of devices
                    mappos = mappositions(float(deviceinfo['lat']), float(deviceinfo['lng']), len(nwdevicelist)-j, 0.0001)
                    #map position counter
                    mc = 1
                    
                    #loop from where you left off and set coordinates
                    for k in range( j+1, len(nwdevicelist) ):
                        if nwdevicelist[k]['model'][:2] == 'MR':
                            setdevicedata(arg_apikey, shardurl, nwidlist[i], nwdevicelist[k]['serial'], 'address', arg_location, False)
                        else:
                            setdeviceaddress(arg_apikey, shardurl, nwidlist[i], nwdevicelist[k]['serial'], arg_location, '%f' % mappos['lat'][mc], '%f' % mappos['lng'][mc])
                            mc += 1                
                
            else:
                printusertext('ERROR: Invalid mode (argument -m)')
                sys.exit(2)   
        
        printusertext('INFO: Updated %d devices for network %s' % (len(nwdevicelist), nwidlist[i]))
    
    printusertext('INFO: End of script')
        
if __name__ == '__main__':
    main(sys.argv[1:])