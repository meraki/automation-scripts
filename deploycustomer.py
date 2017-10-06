# This is a script to create a new customer account into Dashboard by cloning an existing customer,
#  claim their initial order into their Organization, add all of their devices into a new network and
#  bind that network to a template. Switch templates must be eligible for auto-bind (Auto-bind is not valid
#  unless the switch template has at least one profile and has at most one profile per switch model.)
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# To run the script, enter:
#  python deploycustomer.py -k <API k> -s <src> -d <dst> -o <ord> [-c <cfgt> -a <adr> -t <tag> -g <gogl k> -m <mode>]
#
# PREREQUISITES:
#  * Source org must have at least one template configured
#  * All templates in source org must be type "wireless switch appliance"
#  * All templates in source org must be eligible for switch autobind
#  * To use the Google Maps API, you must have a Google API key and the following APIs must be enabled:
#     1. Google Maps Geocoding API
#     2. Google Maps Time Zone API
#
# PLEASE NOTE:
#  Organizations created through API can take several hours to be synced across the different nodes/shards
#   that dashboard is segmented into. This means there may be latency in the orgs appearing in the MSP
#   portal, depending on which shard you access the portal from. If you need to make changes through 
#   the dashboard GUI to organizations created through this script immediately after creation, please first
#   navigate to the source organization used for cloning and then the MSP portal, so that you access the 
#   MSP portal instance running on that node.
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-10-06

import sys, getopt, requests, json, time, re, datetime

class c_devicedata:
    def __init__(self):
        self.serial     = ''
        self.model      = ''
#end class   

#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

def printhelp():
    #prints help text

    printusertext('Script to automatically create a new customer account and set initial config.')
    printusertext('')
    printusertext('Usage:')
    printusertext('python deploycustomer.py -k <API k> -s <src> -d <dst> -o <ord> [-c <cfgt> -a <adr> -t <tag> -g <gogl k> -m <mode>]')
    printusertext('')
    printusertext('Mandatory arguments:')
    printusertext(' * -k <API k> : Your Meraki Dashboard API key')
    printusertext(' * -s <src>   : Source organization name (the one to be cloned)')
    printusertext(' * -d <dst>   : Destination organization name (new customer)')
    printusertext(' * -o <ord>   : Space separated list of order numbers and/or serial numbers to be claimed')
    printusertext('Optional arguments:')
    printusertext(' * -c <cfgt>  : Name of configuration template to be used')
    printusertext(' * -a <adr>   : Street address of customer headquarters')
    printusertext(' * -t <tag>   : Network tags to apply (for custom admin access)')
    printusertext(' * -g <gogl k>: Google API key for dynamic timezone lookups')
    printusertext(' * -m <mode>  : Resolve conflicts if destination org name already exists. Valid options:')
    printusertext('       -m fail_on_error  : Stop script if conflict detected (default mode)')
    printusertext('       -m add_timestamp  : Create new unique org name by adding timestamp')
    printusertext('       -m modify_existing: Ignore conflict and use existing org as destination')
    printusertext('')
    printusertext('Example:')
    printusertext(' python deploycustomer.py -k 1234 -s TemplateOrg -d "Tasty Bread Inc" -o 4567')
    printusertext('')
    printusertext('Read script comments for source org prerequisites.')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')
    
def getorgid(p_apikey, p_orgname):
    #looks up org id for a specific org name
    #on failure returns 'null'
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 01: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_orgname:
            return record['id']
    return('null')
    
def getshardhost(p_apikey, p_orgid):
    #Looks up shard URL for a specific org. Use this URL instead of 'dashboard.meraki.com'
    # when making API calls with API accounts that can access multiple orgs.
    #On failure returns 'null'
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations/%s/snmp' % p_orgid, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 02: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
        
    rjson = r.json()

    return(rjson['hostname'])
    
def getnwid(p_apikey, p_shardhost, p_orgid, p_nwname):
    #looks up network id for a network name
    #on failure returns 'null'

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
        
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_nwname:
            return record['id']
    return('null') 
    
def createnw(p_apikey, p_shardhost, p_dstorg, p_nwdata):
    #creates network if one does not already exist with the same name
    
    #check if network exists
    getnwresult = getnwid(p_apikey, p_shardhost, p_dstorg, p_nwdata['name'])
    if getnwresult != 'null':
        printusertext('WARNING: Skipping network "%s" (Already exists)' % p_nwdata['name'])
        return('null')
    
    if p_nwdata['type'] == 'combined':
        #find actual device types
        nwtype = 'wireless switch appliance'
    else:
        nwtype = p_nwdata['type']
    if nwtype != 'systems manager':
        time.sleep(API_EXEC_DELAY)
        try:
            r = requests.post('https://%s/api/v0/organizations/%s/networks' % (p_shardhost, p_dstorg), data=json.dumps({'timeZone': p_nwdata['timeZone'], 'tags': p_nwdata['tags'], 'name': p_nwdata['name'], 'organizationId': p_dstorg, 'type': nwtype}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
        except:
            printusertext('ERROR 04: Unable to contact Meraki cloud')
            sys.exit(2)
    else:
        printusertext('WARNING: Skipping network "%s" (Cannot create SM networks)' % p_nwdata['name'])
        return('null')
        
    return('ok')
    
def updatenw(p_apikey, p_shardhost, p_nwid, p_field, p_value):
    #updates network data    
        
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.put('https://%s/api/v0/networks/%s' % (p_shardhost, p_nwid), data=json.dumps({p_field: p_value}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 05: Unable to contact Meraki cloud')
        sys.exit(2)
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')
    
def gettemplateid(p_apikey, p_shardhost, p_orgid, p_tname):
    #looks up config template id for a config template name
    #on failure returns 'null'

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/configTemplates' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 06: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_tname:
            return record['id']
    return('null') 
    
def getrandomtemplateid(p_apikey, p_shardhost, p_orgid):
    #returns a template ID that belongs to target org
        
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/configTemplates' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 07: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
        
    rjson = r.json()
        
    for record in rjson:
        return record['id']
    
    return ('null')
    
def getnwssids(p_apikey, p_shardhost, p_nwid):
    #returns all SSIDs in network or template
        
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/networks/%s/ssids' % (p_shardhost, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 08: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'number':0, 'name':'getnwssids_FlagOperationFailed'})
        return(returnvalue)
    
    rjson = r.json()
    
    return(rjson)
    
def updatessidname(p_apikey, p_shardhost, p_nwid, p_ssidnumber, p_name):
    #Modifies SSID names in a template
        
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.put('https://%s/api/v0/networks/%s/ssids/%d' % (p_shardhost, p_nwid, p_ssidnumber), data=json.dumps({'name':p_name}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 09: Unable to contact Meraki cloud')
        sys.exit(2)
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')
    
def bindnw(p_apikey, p_shardhost, p_nwid, p_templateid, p_autobind):
    #binds a network to a template
    
    if p_autobind:
        autobindvalue = 'true'
    else:
        autobindvalue = 'false'
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.post('https://%s/api/v0/networks/%s/bind' % (p_shardhost, p_nwid), data=json.dumps({'configTemplateId': p_templateid, 'autoBind': autobindvalue}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 10: Unable to contact Meraki cloud')
        sys.exit(2)
        
    if r.status_code != requests.codes.ok:
        return 'null'
        
    return('ok')
    
def claimdeviceorg(p_apikey, p_shardhost, p_orgid, p_device):
    #claims a device into an org without adding to a network
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.post('https://%s/api/v0/organizations/%s/claim' % (p_shardhost, p_orgid), data=json.dumps({'serial': p_device}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 11: Unable to contact Meraki cloud')
        sys.exit(2)
    
    return(0)
    
def claimlicenseorg(p_apikey, p_shardhost, p_orgid, p_licensekey):
    #claims a license key into an org
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.post('https://%s/api/v0/organizations/%s/claim' % (p_shardhost, p_orgid), data=json.dumps({'licenseKey': p_licensekey, 'licenseMode': 'addDevices'}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 12: Unable to contact Meraki cloud')
        sys.exit(2)
    
    return(0)
    
def claimorderorg(p_apikey, p_shardhost, p_orgid, p_ordernum):
    #claims a device into an org without adding to a network
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.post('https://%s/api/v0/organizations/%s/claim' % (p_shardhost, p_orgid), data=json.dumps({'order': p_ordernum, 'licenseMode': 'addDevices'}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 13: Unable to contact Meraki cloud')
        sys.exit(2)
    
    return(0)
    
def claimdevice(p_apikey, p_shardhost, p_nwid, p_device):
    #claims a device into a network
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.post('https://%s/api/v0/networks/%s/devices/claim' % (p_shardhost, p_nwid), data=json.dumps({'serial': p_device}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 14: Unable to contact Meraki cloud')
        sys.exit(2)
    
    return(0)
    
def getdeviceinfo(p_apikey, p_shardhost, p_nwid, p_serial):
    #returns info for a single device
    #on failure returns lone device record, with serial number 'null'

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/networks/%s/devices/%s' % (p_shardhost, p_nwid, p_serial), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 15: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue = {'serial':'null', 'model':'null'}
        return(returnvalue)
    
    rjson = r.json()
    
    return(rjson) 
    
def setdevicedata(p_apikey, p_shardhost, p_nwid, p_device, p_field, p_value, p_movemarker):
    #modifies value of device record. Returns the new value
    #on failure returns one device record, with all values 'null'
    #p_movemarker is boolean: True/False
    
    movevalue = "false"
    if p_movemarker:
        movevalue = "true"
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.put('https://%s/api/v0/networks/%s/devices/%s' % (p_shardhost, p_nwid, p_device), data=json.dumps({p_field: p_value, 'moveMapMarker': movevalue}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 16: Unable to contact Meraki cloud')
        sys.exit(2)
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')

def getorgdeviceinfo (p_apikey, p_shardhost, p_orgid, p_device):
    #gets basic device info from org inventory. device does not need to be part of a network
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 17: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = {}
    if r.status_code != requests.codes.ok:
        returnvalue = {'serial':'null', 'model':'null'}
        return(returnvalue)
    
    rjson = r.json()
    
    foundserial = False
    for record in rjson:
        if record['serial'] == p_device:
            foundserial = True
            returnvalue = {'mac': record['mac'], 'serial': record['serial'], 'networkId': record['networkId'], 'model': record['model'], 'claimedAt': record['claimedAt'], 'publicIp': record['publicIp']}
                
    if not foundserial:
        returnvalue = {'serial':'null', 'model':'null'}
    return(returnvalue) 
    
def getorginventory(p_apikey, p_shardhost, p_orgid):
    #returns full org inventory

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 18: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        return(returnvalue) #return empty table
    
    rjson = r.json()
    
    return (rjson)
    
def clonecreateorg(p_apikey, p_shardhost, p_srcorgid, p_dstorgname):
    #Creates a new organization by cloning an existing one
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.post('https://%s/api/v0/organizations/%s/clone' % (p_shardhost, p_srcorgid), data=json.dumps({'name': p_dstorgname}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 19: Unable to contact Meraki cloud')
        sys.exit(2)
            
    return (0)
    
def getgoogletimezone(p_googlekey, p_address):
    #returns the timezone associated to a specified address by using Google Maps APIs
    try:
        r = requests.get('https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s' % (p_address, p_googlekey) )
    except:
        printusertext('WARNING: Unable to contact Google cloud')
        return('null')
        
    rjson = r.json()
    
    if rjson['status'] != 'OK':
        return('null')

    glatitude  = rjson['results'][0]['geometry']['location']['lat']
    glongitude = rjson['results'][0]['geometry']['location']['lng']
    
    try:
        s = requests.get('https://maps.googleapis.com/maps/api/timezone/json?location=%s,%s&timestamp=%f&key=%s' % (glatitude, glongitude, time.time(), p_googlekey) )
    except:
        printusertext('WARNING: Unable to contact Google cloud')
        return('null')

    sjson = s.json()
    
    if sjson['status'] == 'OK':
        return(sjson['timeZoneId'])

    return('null')
    
def main(argv):
    #set default values for command line arguments
    arg_apikey     = ''
    arg_srcorg     = ''
    arg_dstorg     = ''
    arg_orderstr   = ''
    arg_template   = ''
    arg_address    = ''
    arg_nwtags     = ''
    arg_googlekey  = ''
    arg_modeignore = ''
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:s:d:o:c:a:t:g:m:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey     = arg
        elif opt == '-s':
            arg_srcorg     = arg
        elif opt == '-d':
            arg_dstorg     = arg
        elif opt == '-o':
            arg_orderstr   = arg
        elif opt == '-c':
            arg_template   = arg
        elif opt == '-a':
            arg_address    = arg
        elif opt == '-t':
            arg_nwtags     = arg
        elif opt == '-g':
            arg_googlekey  = arg
        elif opt == '-m':
            arg_modeignore = arg
                      
    #check if all parameters are required parameters have been given
    if arg_apikey == '' or arg_srcorg == '' or arg_dstorg == '' or arg_orderstr == '':
        printhelp()
        sys.exit(2)
    
    #set flags:
    mode_notemplate  = False
    if arg_template == '':
        mode_notemplate  = True
        
    mode_noaddress   = False
    if arg_address == '':
        mode_noaddress   = True
        
    flag_mode_arg_invalid = True
    mode_fail_on_error    = True
    mode_add_timestamp    = False
    mode_modify_existing  = False
    if   arg_modeignore == '':
        flag_mode_arg_invalid = False
    elif arg_modeignore == 'fail_on_error':
        flag_mode_arg_invalid = False
    elif arg_modeignore == 'add_timestamp':
        flag_mode_arg_invalid = False
        mode_add_timestamp    = True
    elif arg_modeignore == 'modify_existing':
        flag_mode_arg_invalid = False
        mode_modify_existing  = True
        
    if flag_mode_arg_invalid:   
        printusertext('ERROR 33: Argument -m <mode> is invalid')
        sys.exit(2)
        
    #get source organization id corresponding to org name provided by user
    #source org must exist
    srcorgid = getorgid(arg_apikey, arg_srcorg)
    if srcorgid == 'null':
        printusertext('ERROR 20: Fetching source organization ID failed')
        sys.exit(2)
        
    #clean up suspicious characters from destination org name
    pattern = re.compile('([^\s\w]|_)+')
    dstorgname = pattern.sub('', arg_dstorg)
    dstorgname = dstorgname.strip()
    MAX_RENAME_TRIES = 10
    #get destination organization id corresponding to org name provided by user
    #destination org must NOT exist
    dstorgid = getorgid(arg_apikey, dstorgname)
    if dstorgid != 'null':
        if mode_add_timestamp:
            for i in range (0, MAX_RENAME_TRIES):
                time.sleep(2)
                timestamp = ' {:%Y%m%d %H%M%S}'.format(datetime.datetime.now())
                dstorgname = arg_dstorg + timestamp
                dstorgid = getorgid(arg_apikey, dstorgname)
                if dstorgid == 'null':
                    break
            if i == MAX_RENAME_TRIES:
                printusertext('ERROR 21: Unable to assign unique destination org name')
                sys.exit(2)    
        elif mode_modify_existing:
            printusertext('INFO: Modifying existing destination org')
        else:
            #default: fail on error
            printusertext('ERROR 22: Destination org name is already taken (%s)' % dstorgname)
            sys.exit(2)
        
    printusertext('INFO: Destination org name is "%s"' % dstorgname)
    
    #clone org based on source
    if not mode_modify_existing:
        clonecreateorg(arg_apikey, 'dashboard.meraki.com', srcorgid, dstorgname)
    dstorgid = getorgid(arg_apikey, dstorgname)
    if dstorgid == 'null':
        printusertext('ERROR 23: Unable to create destination org')
        sys.exit(2)
                
    #get shard URL where destination org is stored
    #this call sometimes fails. implementing a try-verify-wait-repeat loop
    MAX_SHARD_RESOLVE_TRIES = 10
    flag_unabletoresolveshard = True
    
    for i in range (0, MAX_SHARD_RESOLVE_TRIES):
        
        dstshardhost = getshardhost(arg_apikey, dstorgid)
        if dstshardhost == 'null':
            time.sleep(API_EXEC_DELAY*(i+1))
        else:
            flag_unabletoresolveshard = False
            break
    
    if flag_unabletoresolveshard:
        printusertext('ERROR 24: Fetching Meraki cloud shard FQDN failed')
        sys.exit(2)
             
    #identify serials, orders and claim accordingly
    printusertext('INFO: Claiming orders and serial numbers')
    
    #get serial numbers from parameter -s
    claimlist = arg_orderstr.split(" ")
    
    for i in range (0, len(claimlist) ):
        if len(claimlist[i]) > 4: #prevent next line from crashing if invalid argument
            if claimlist[i][4] == '-': #string is a device serial or license
                claimdeviceorg(arg_apikey, dstshardhost, dstorgid, claimlist[i])
        
                #check if device has been claimed successfully
                deviceinfo = getorgdeviceinfo (arg_apikey, dstshardhost, dstorgid, claimlist[i])
                if deviceinfo['serial'] == 'null':
                    printusertext('INFO: Unable to claim %s as a device' % claimlist[i])
                    claimlicenseorg(arg_apikey, dstshardhost, dstorgid, claimlist[i])
            else: #string is an order number
                claimorderorg(arg_apikey, dstshardhost, dstorgid, claimlist[i])
        else:
            printusertext('WARNING: Serial number %s is not valid' % claimlist[i])
            
    #get inventory
    orginventory = getorginventory(arg_apikey, dstshardhost, dstorgid)
        
    inventorylen = len(orginventory)
    if inventorylen == 0:
        printusertext('ERROR 25: Destination org does not contain any devices')
        sys.exit(2)
        
    #from inventory pick all LAN devices (MS, MR) and the largest MX/Z. leave the rest be
    devicetypes = {'mx': False, 'ms': False, 'mr': False}
    devices = []
    largestmx = c_devicedata()
    largestmx.model = '0'
    for orgdevice in orginventory:
        if orgdevice['model'][:2] == 'MX' or orgdevice['model'][:1] == 'Z':
            devicetypes['mx'] = True
            if int(re.search(r'\d+', orgdevice['model']).group()) > int(re.search(r'\d+', largestmx.model).group()):
                largestmx.serial = orgdevice['serial']
                largestmx.model  = orgdevice['model']
        elif orgdevice['model'][:2] == 'MS':
            devicetypes['ms'] = True
            devices.append(c_devicedata())
            devices[len(devices)-1].serial = orgdevice['serial']
            devices[len(devices)-1].model  = orgdevice['model']
        elif orgdevice['model'][:2] == 'MR':
            devicetypes['mr'] = True
            devices.append(c_devicedata())
            devices[len(devices)-1].serial = orgdevice['serial']
            devices[len(devices)-1].model  = orgdevice['model']
            
    #if found a suitable MX, append it to the end of the devices list to optimize claiming code
    if largestmx.model != '0':
        devices.append(c_devicedata())
        devices[len(devices)-1].serial = largestmx.serial
        devices[len(devices)-1].model  = largestmx.model
            
    #build network type string for network creation
    nwtypestring = ''
    if devicetypes['mr']:
        nwtypestring += 'wireless '
    if devicetypes['ms']:
        nwtypestring += 'switch '
    if devicetypes['mx']:
        nwtypestring += 'appliance'
    nwtypestring = nwtypestring.strip()
    
    #create correct network type as HQ network
    printusertext('INFO: Creating headquarters network')    
        
    #compile parameters to create network
    #timeZone will be overwritten by template
    hqnwname = arg_dstorg + ' HQ'
    nwparams = {'name': hqnwname, 'timeZone': 'Europe/Helsinki', 'tags': arg_nwtags, 'organizationId': dstorgid, 'type': nwtypestring}
                
    #create network and get its ID
    createstatus = createnw (arg_apikey, dstshardhost, dstorgid, nwparams)
    if createstatus == 'null' and not mode_modify_existing:
        printusertext('ERROR 26: Unable to create network')
        sys.exit(2)
    nwid = getnwid(arg_apikey, dstshardhost, dstorgid, hqnwname)
    if nwid == 'null':
        printusertext('ERROR 27: Unable to get ID for new network')
        sys.exit(2)    
    
    if arg_template != '':
        #get template ID for template name argument
        templateid = gettemplateid(arg_apikey, dstshardhost, dstorgid, arg_template)
        if templateid == 'null':
            printusertext('ERROR 28: Unable to find template: ' + arg_template)
            sys.exit(2)  
    else:    
        #if argument omitted just select the first one
        templateid = getrandomtemplateid(arg_apikey, dstshardhost, dstorgid)
        if templateid == 'null':
            printusertext('ERROR 29: Unable to find a config template')
            sys.exit(2)  
            
    #claim into HQ network the largest MX, all switches, all wireless
    printusertext('INFO: Adding devices to network')
    
    for device in devices:
        #claim device into newly created network
        claimdevice(arg_apikey, dstshardhost, nwid, device.serial)
    
        #check if device has been claimed successfully
        deviceinfo = getdeviceinfo(arg_apikey, dstshardhost, nwid, device.serial)
        if deviceinfo['serial'] == 'null':
            printusertext('ERROR 30: Claiming or moving device unsuccessful')
            sys.exit(2)
               
    printusertext('INFO: Editing template and binding network')
    
    #Rewrite template SSID names
    #get template SSIDs
    templatessids = getnwssids(arg_apikey, dstshardhost, templateid)
    if templatessids[0] == 'getnwssids_FlagOperationFailed':
        printusertext('ERROR 31: Unable get template SSIDs')
        sys.exit(2)        
    #find the ones that are enabled and rewrite as needed
    ssidname = []
    for ssid in templatessids:
        if ssid['enabled'] == True:
            ssidname = "%s %s" % (dstorgname, ssid['name'])
            updatessidname(arg_apikey, dstshardhost, templateid, ssid['number'], ssidname)
                            
    #bind network to template. If switches in template, attempt to autobind them
    bindstatus = bindnw(arg_apikey, dstshardhost, nwid, templateid, devicetypes['ms'])
    if bindstatus == 'null' and not mode_modify_existing:
        printusertext('ERROR 32: Unable to bind network to template')
        sys.exit(2)
                           
    # THE REST IS BEST EFFORT STUFF. MOVED TO END OF SCRIPT SINCE THEIR FAILURE IS NOT CRITICAL
    
    printusertext('INFO: Setting device hostnames and locations')
    
    MAX_ADDRESS_SET_TRIES = 10 #how many times to try setting device address before failing

    for device in devices:
        #set device hostname
        ### DEVICE HOSTNAME IS DEFINED AS "<MODEL>_<SERIAL>". MODIFY LINE BELOW TO CHANGE ###
        hostname = deviceinfo['model'] + '_' + device.serial
        setdevicedata(arg_apikey, dstshardhost, nwid, device.serial, 'name', hostname, False)
        
        #if street address is given as a parameter, set device location
        #this API call does not always go through, so it is implemented in a "try-verify-wait" loop
        flag_unabletosetaddress = True
        if arg_address != 'null':
            for i in range (0, MAX_ADDRESS_SET_TRIES):
                setdevicedata(arg_apikey, dstshardhost, nwid, device.serial, 'address', arg_address, True)
                #check if device address has been set correctly
                deviceinfo = getdeviceinfo(arg_apikey, dstshardhost, nwid, device.serial)
                if deviceinfo['serial'] == 'null':
                    time.sleep(API_EXEC_DELAY*(i+1))
                elif deviceinfo['address'] != '':
                    flag_unabletosetaddress = False
                    break
                else:
                    time.sleep(API_EXEC_DELAY*(i+1))
            if flag_unabletosetaddress:
                printusertext('WARNING: Unable to set address for device %s' % device.serial)
                           
    #attempt to override template timezone by fetching the right one from Google API    
    flag_unabletosettime = True
    if arg_googlekey != '' and arg_address != '':
        printusertext('INFO: Setting time zone')
        gtimezone = getgoogletimezone(arg_googlekey, arg_address)
        if gtimezone != 'null':
            udstatus = updatenw(arg_apikey, dstshardhost, nwid, 'timeZone', gtimezone)
            if udstatus == 'ok':
                flag_unabletosettime = False
        if flag_unabletosettime:
            printusertext('WARNING: Unable to set time zone using Google Maps API')
                
    printusertext('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])