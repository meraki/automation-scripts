read_me = '''This is a Python 3 script to provision template-based networks with manually defined VLAN subnets
 to Meraki dashboard.
 
Syntax:
  python provision_sites.py -k <api key> -o <org name> -i <input file> [-n <net type> -u <update mode> -x <proxy mode>]
  
Mandatory parameters:
  -k <api key>          : Your Meraki Dashboard API key
  -o <org name>         : The name of the dashboard organization you want to provision the sites into
  -i <input file>       : Name of the CSV file containing info for the networks to be created
  
Optional parameters:
  -n <net type>         : Product types to create networks for. Must match templates used. Valid options:
                            -n appliance                  MX/Z3 appliances only (default)
                            -n appliance-wireless         MX/Z3 appliances and MR Wi-Fi access points
                            -n appliance-switch           MX/Z3 appliances and MS switches
                            -n appliance-wireless-switch  MX/Z3 appliances, MR Wi-Fi APs and MS switches
  -u <update mode>      : Whether to update existing or fail script if the organization already contains networks
                           with names that match the ones in the input file. Valid forms:
                            -u fail                       Interrupts script if network is not new (default)
                            -u update                     Attempts to update existing networks to match input file
  -x <proxy mode>       : Whether to use the new Dashboard API mega proxy or not. Valid forms:
                            -x use-mega-proxy             Sends API requests to "api-mp.meraki.com" (default)
                            -x do-not-use-mega-proxy      Sends API requests to "api.meraki.com"
  
Usage example:
  python provision_sites.py -k 1234 -o "Big Industries Inc" -i site_info.csv
  
Example input CSV file and CSV generator Excel sheet here:
  [TODO: INSERT GITHUB LINK]
  
Required Python 3 modules:
  Requests     : http://docs.python-requests.org
  
  After installing Python, you can install these additional modules using pip with the following commands:
    pip install requests
    
Notes:
  * Depending on your operating system, the commands for python and pip may be "python3" and "pip3" instead
  * Use double quotes to enter names containing spaces in the Windows command line
  * For the script to work, VLANs to be modified will need to be set to "unique" subnetting in dashboard
  * The script executes most configuration tasks as action batches for scalability. If one task fails, its 
     whole batch will fail with it. Refer to the script's command line output for which tasks have been grouped
     together as batches and whether executing a batch has produced errors
  * Including the location (street address) of your network to the input file will result in devices being
     repositioned on the world map to match this address. If you wish to prevent this for a network, leave
     this cell blank
'''

import sys, getopt, requests, json, time, datetime, ipaddress


### SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR


#Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate
API_EXEC_DELAY              = 0.21 

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

#Max number of loops to try when waiting for action batches to complete and retry interval in seconds
ABWAIT_MAX_LOOPS            = 20
ABWAIT_RETRY_INTERVAL       = 2


### SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY


LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()
API_BASE_URL                = 'https://api-mp.meraki.com/api/v0'
API_BASE_URL_MEGA_PROXY     = 'https://api-mp.meraki.com/api/v0'
API_BASE_URL_NO_MEGA        = 'https://api.meraki.com/api/v0'
ACTION_BATCH_QUEUE          = []


### SECTION: CLASS DEFINITIONS


class c_network:
    def __init__(self):
        self.name           = None
        self.id             = None
        self.templateName   = None
        self.templateId     = None
        self.skipBinding    = False
        self.location       = None
        self.serials        = []
        self.vlanOverrides  = {}
#end class


### SECTION: GENERAL USE FUNCTIONS


def printHelpAndExit():
    print(read_me)
    sys.exit(0)


def killScript():
    print('ERROR 01: Execution interrupted.')
    sys.exit(2)


def debugDumpNetwork(p_network):
    dump = []
    dump.append(p_network.id)
    dump.append(p_network.name)
    dump.append(p_network.location)
    dump.append(p_network.templateId)
    dump.append(p_network.templateName)
    dump.append(p_network.vlanOverrides)
    dump.append(p_network.serials)
    print(dump)


def parseVlansFromHeader(p_line, p_delimeter):
    returnList = []
    splitLine = p_line.split(p_delimeter)
    for item in splitLine:
        stripped = item.strip()
        if stripped.startswith('VLAN'):
            if len(stripped) > 5:
                if stripped[5] != 'X':
                    try:
                        number = int(stripped[5:])
                        returnList.append(number)
                    except:
                        print('ERROR 02: Invalid VLAN number "%s" in input file' % stripped[5:])
                        return None
                else:
                    #push flag to ignore this column, as it is disabled by user choice
                    returnList.append(None)
            else:
                print('ERROR 03: Invalid VLAN number definition in input file')
                return None
            
    return returnList
    
    
def parseNetwork(p_line, p_delimeter, p_vlans):

    network     = c_network()
    splitLine   = p_line.split(p_delimeter)
    lenSplit    = len(splitLine)
    lenVlans    = len(p_vlans)
    
    if lenSplit < (lenVlans + 4):
        print(p_line)
        print('ERROR 04: Invalid network definition in input file')
        return None
        
    network.name            = splitLine[0].strip()
    network.location        = splitLine[1].strip()
    network.templateName    = splitLine[2].strip()
    
    for i in range(lenVlans):
        label = p_vlans[i]
        if not label is None:
            cellValue = splitLine[i+3].strip()
            if cellValue != '':
                network.vlanOverrides[str(label)] = cellValue
            
    serials = splitLine[lenSplit-1].split(' ')
    
    for item in serials:
        sItem = item.strip()
        if sItem != '':
            network.serials.append(sItem)
        
    return network
    

def loadCsv(p_fileName):
    
    try:
        f = open(p_fileName, 'r')    
    except:
        print('ERROR 05: Unable to open input file')
        return None
        
    delimeter       = ';'
    headerNotFound  = True
    vlanNumbers     = None
    networksList    = []
    templatesList   = []
        
    for line in f:
        stripped = line.strip()
        if len(stripped) > 0:
            if not stripped[0] in ['#', '"']:
                if headerNotFound and stripped.startswith('meta:delimeter-detector-line'):
                    #this is a delimeter detector line
                    if len(stripped) > 28 and stripped[28] in [',', ';']:
                        delimeter = stripped[28]
                    else:
                        print('ERROR 06: Invalid delimeter detector line in input file')
                        return None
                        
                elif headerNotFound and stripped.startswith('Network name'):
                    #this is a table header line
                    headerNotFound = False
                    vlanNumbers = parseVlansFromHeader(stripped, delimeter)
                    
                    if vlanNumbers is None:
                        print('ERROR 07: VLAN numbers defined incorrectly in input file')
                        return None
                    
                else:
                    #this is a network definition line                    
                    network = parseNetwork(stripped, delimeter, vlanNumbers)
                    
                    if network is None:
                        print('ERROR 08: Invalid network definition')
                        return None
                                                
                    networksList.append(network)
                                        
    f.close()
    
    return networksList
    
    
def changeSubnet(p_oldNet, p_newNet, p_oldRouterIp):
    oldNet      = ipaddress.ip_network(p_oldNet, False)
    oldPrefix   = str(oldNet.prefixlen)
    try:
        newNet  = ipaddress.ip_network(p_newNet + '/' + oldPrefix, False)
    except:
        print('ERROR 09: Invalid subnet %s/%s' % (p_newNet, oldPrefix))
        return None, None
        
    oldHosts    = list(oldNet.hosts())
    oldRouterIp = ipaddress.IPv4Address(p_oldRouterIp)
    routerIndex = oldHosts.index(oldRouterIp)
    newHosts    = list(newNet.hosts())
    newRouterIp = newHosts[routerIndex]
        
    return newNet, newRouterIp
    
    
### SECTION: FUNCTIONS FOR MERAKI DASHBOARD COMMUNICATION


def merakiRequestThrottler():
    #prevents hitting max request rate shaper of the Meraki Dashboard API
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return


def getOrgId(p_apiKey, p_orgName):
    #returns the organizations' list for a specified admin, with filters applied
        
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations', headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
        
    rjson = r.json()
    
    for org in rjson:
        if org['name'] == p_orgName:
            return org['id']
    
    return None
    
    
def getOrgTemplates(p_apiKey, p_orgId):
    #returns the organizations' list for a specified admin, with filters applied
        
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations/%s/configTemplates' % p_orgId, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
        
    rjson = r.json()
        
    return rjson
    
    
def getOrgNetworks(p_apiKey, p_orgId):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations/%s/networks' % (p_orgId), headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 10: Unable to get networks')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
        
    
def createActionBatch (p_apiKey, p_orgId, p_actions):   
    merakiRequestThrottler()
    
    payload = json.dumps(
        {
            'confirmed':True, 
            'synchronous':False,
            'actions': p_actions
        }
    )
        
    try:
        r = requests.post( API_BASE_URL + '/organizations/%s/actionBatches' % p_orgId, data=payload, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        return None
    
    if 200 <= r.status_code < 300:
        rjson = r.json()
        return rjson['id']
      
    return None
        
    
def queueActionBatch (p_apiKey, p_orgId, p_action, p_forceCommit=False):
    #return success, batchId
    global ACTION_BATCH_QUEUE
    
    if not p_action is None:
        ACTION_BATCH_QUEUE.append(p_action)
    queueLength = len(ACTION_BATCH_QUEUE)
    if queueLength == 100 or (queueLength > 0 and p_forceCommit):
        print('Submitting action batch:')
        print(ACTION_BATCH_QUEUE)
        
        batchId = createActionBatch (p_apiKey, p_orgId, ACTION_BATCH_QUEUE)     
        ACTION_BATCH_QUEUE = []
        
        if not batchId is None:
            print('Submitted with batchId %s' % batchId)
            return (True, str(batchId))
        else:
            return (False, None)
    
    return (True, None)
    
    
def getActionBatches(p_apiKey, p_orgId):
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations/%s/actionBatches' % p_orgId, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 11: Unable to get action batches')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
    
    
def waitForActionBatchesToComplete(p_apiKey, p_orgId, p_batchIds):
    flag_waitSomeMore   = True
    flag_batchHasFailed = False
        
    i = -1
    while flag_waitSomeMore:
        i += 1
        if i >= ABWAIT_MAX_LOOPS:
            break
        flag_waitSomeMore   = False
        actionBatches       = getActionBatches(p_apiKey, p_orgId)
        #print(actionBatches)
        for id in p_batchIds:
            for record in actionBatches:
                if record['id'] == id:
                    if not record['status']['completed'] and not record['status']['failed']:
                        flag_waitSomeMore = True
                        break
                    if record['status']['failed']:
                        print('ERROR 12: Action batch with batchId %s has failed' % id)
                        if 'errors' in record['status']:
                            print(record['status']['errors'])
                        return False
        if flag_waitSomeMore:
            time.sleep(ABWAIT_RETRY_INTERVAL)                        
    return True
    
    
def sendCreateNetworkToActionBatchQueue(p_apiKey, p_orgId, p_name, p_type):    
            
    body = {
        'name'    : p_name,
        'type'    : p_type
    }
    action = {
        'resource'  : '/organizations/' + p_orgId + '/networks',
        'operation' : 'create',
        'body'      : body
    }    
    success, batchId = queueActionBatch (p_apiKey, p_orgId, action)
    if not success:
        print('ERROR 13: Failed to queue action batch')
        
    return success, batchId
    
    
def sendUpdateVlanSubnetToActionBatchQueue(p_apiKey, p_orgId, p_networkId, p_vlanId, p_vlanSubnet, p_routerIp):    
            
    body = {
        'subnet'        : p_vlanSubnet,
        'applianceIp'   : p_routerIp
    }
    action = {
        'resource'  : '/networks/' + p_networkId + '/vlans/' + p_vlanId,
        'operation' : 'update',
        'body'      : body
    }    
    success, batchId = queueActionBatch (p_apiKey, p_orgId, action)
    if not success:
        print('ERROR 14: Failed to queue action batch')
        
    return success, batchId
    
    
def sendClaimDeviceToActionBatchQueue(p_apiKey, p_orgId, p_networkId, p_serial):    
            
    body = {
        'serial'        : p_serial
    }
    action = {
        'resource'  : '/networks/' + p_networkId + '/devices',
        'operation' : 'claim',
        'body'      : body
    }    
    success, batchId = queueActionBatch (p_apiKey, p_orgId, action)
    if not success:
        print('ERROR 15: Failed to queue action batch')
        
    return success, batchId
    
    
def sendUpdateDeviceLocationToActionBatchQueue(p_apiKey, p_orgId, p_networkId, p_serial, p_location):  
    
    body = {
        'address'       : p_location,
        'moveMapMarker' : True
    }
    action = {
        'resource'  : '/networks/' + p_networkId + '/devices/' + p_serial,
        'operation' : 'update',
        'body'      : body
    }    
    success, batchId = queueActionBatch (p_apiKey, p_orgId, action)
    if not success:
        print('ERROR 16: Failed to queue action batch')
        
    return success, batchId
    
    
def bindNetworkToTemplate (p_apiKey, p_networkId, p_templateId):   
    merakiRequestThrottler()
    
    payload = json.dumps(
        {
            'configTemplateId': p_templateId, 
            'autoBind':False
        }
    )
        
    try:
        r = requests.post( API_BASE_URL + '/networks/%s/bind' % p_networkId, data=payload, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        return False
    
    if 200 <= r.status_code < 300:
        return True
      
    return False
    
    
def getNetworkVlans(p_apiKey, p_networkId):
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/networks/%s/vlans' % p_networkId, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 17: Unable to get VLANs for network id %s' % p_networkId)
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
    
    
def getOrgInventory(p_apiKey, p_orgId):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations/%s/inventory' % p_orgId, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 18: Unable to get inventory')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())


### SECTION: MAIN


def main(argv):
    global API_BASE_URL
    
    #set default values for command line arguments
    arg_apikey          = None
    arg_orgname         = None
    arg_initfile        = None
    arg_nettype         = None
    arg_proxy           = None
    arg_updateExisting  = None
    
    try:
        opts, args = getopt.getopt(argv, 'hk:o:i:n:u:x:')
    except getopt.GetoptError:
        printHelpAndExit()
    
    for opt, arg in opts:
        if opt == '-h':
            printHelpAndExit()
        elif opt == '-k':
            arg_apikey          = arg
        elif opt == '-o':
            arg_orgname         = arg
        elif opt == '-i':
            arg_initfile        = arg
        elif opt == '-n':
            arg_nettype         = arg
        elif opt == '-u':
            arg_updateExisting  = arg
        elif opt == '-x':
            arg_proxy           = arg
            
    #check if all required parameters have been given
    if arg_apikey is None or arg_orgname is None or arg_initfile is None:
        printHelpAndExit()
        
    netType = 'appliance '
    if not arg_nettype is None:
        if arg_nettype.find('wireless') != -1:
            netType += 'wireless '
        if arg_nettype.find('switch') != -1:
            netType += 'switch '
        
    flag_doNotUpdateExisting = True
    if (not arg_updateExisting is None) and arg_updateExisting == 'update':
        flag_doNotUpdateExisting = False
        
    API_BASE_URL = API_BASE_URL_MEGA_PROXY
    if (not arg_proxy is None) and arg_proxy == 'do-not-use-mega-proxy':
        API_BASE_URL = API_BASE_URL_NO_MEGA
        

    print('Reading input file...')
    networks = loadCsv(arg_initfile)
    
    if networks is None:
        killScript()
        
    print('Fetching organization info...')
    orgId = getOrgId(arg_apikey, arg_orgname)
    
    if orgId is None:
        print('ERROR 19: Unable to resolve organization Id')
        killScript()
         
    orgTemplates = getOrgTemplates(arg_apikey, orgId)
    
    if orgTemplates is None:
        print('ERROR 20: Unable to fetch organization templates')
        killScript()
        
    for net in networks:
        nameNotFound = True
        for item in orgTemplates:
            if net.templateName == item['name']:
                nameNotFound = False
                net.templateId = item['id']        
                break
        if nameNotFound:
            print('ERROR 21: Template with name "%s" not found in org' % name)
            killScript()
                            
    orgNetworks = getOrgNetworks(arg_apikey, orgId)
    
    if orgNetworks is None:
        print('ERROR 22: Unable to fetch organization networks')
        killScript()
            
    print('Creating networks...')
    batchIdList = []
    for net in networks:
        nameNotFound = True
        for item in orgNetworks:
            if net.name == item['name']:
                nameNotFound = False
                net.id = item['id']
                if 'configTemplateId' in item:
                    if not item['configTemplateId'] is None:
                        if item['configTemplateId'] != net.templateId:
                            print('ERROR 23: Network "%s" is already bound to a different template' % net.name)
                            killScript()
                        net.skipBinding = True
                break
        if nameNotFound:
            success, batchId = sendCreateNetworkToActionBatchQueue(arg_apikey, orgId, net.name, netType)
            if success:
                if not batchId is None:
                    batchIdList.append(batchId)
            else:
                print('ERROR 24: Error queueing network creation to action batch')
                killScript()
        elif flag_doNotUpdateExisting:
            print('ERROR 25: Network with name "%s" already exists. Use "-u update" to override' % net.name)
            killScript()
            
    #if unsubmitted net creation commands, submit last batch
    success, batchId = queueActionBatch (arg_apikey, orgId, None, True)
    if success:
        if not batchId is None:
            batchIdList.append(batchId)
    else:
        print('ERROR 26: Error submitting action batch')
        killScript()
        
    if len(batchIdList) > 0:
        #check that all action batches have been completed before proceeding
        print('Waiting for action batches to complete...')
        success = waitForActionBatchesToComplete(arg_apikey, orgId, batchIdList)
        
        if not success:
            print('ERROR 27: An action batch has failed to execute')
            killScript()
        
    #Resolve network Ids of new networks
    orgNetworks = getOrgNetworks(arg_apikey, orgId)
    
    if orgNetworks is None:
        print('ERROR 28: Unable to fetch organization networks')
        killScript()
        
    for net in networks:
        nameNotFound = True
        for item in orgNetworks:
            if net.name == item['name']:
                nameNotFound = False
                net.id = item['id']
                break
        if nameNotFound:
            print('ERROR 29: Failed to create network "%s" (%s)' % (net.name, net.id))
            killScript()    

    print('Binding networks to templates...')
    for net in networks:
        if not net.skipBinding:
            bindNetworkToTemplate (arg_apikey, net.id, net.templateId)
        
    #Clear batchIdList to only check for VLAN/device claim batch success at the end of the script
    batchIdList = []
    
    #Update VLAN parameters
    print('Updating VLAN IP parameters...')
    for net in networks:
        if len(net.vlanOverrides) > 0:
            #Get VLANs from dashboard to resolve correct netmask and MX host IP address
            orgNetVlans = getNetworkVlans(arg_apikey, net.id)
            if orgNetVlans is None:
                print('ERROR 30: Failed to get VLAN info for network "%s" (%s)' % (net.name, net.id))
            else:
                for vlan in net.vlanOverrides:
                    vlanNotFound = True
                    for orgVlan in orgNetVlans:
                        if str(orgVlan['id']) == vlan:
                            vlanNotFound = False
                            #Calculate new subnet/prefix and appliance VLAN default gateway IP address and submit to dashboard
                            newSubnet, newRouterIp = changeSubnet(orgVlan['subnet'], net.vlanOverrides[vlan], orgVlan['applianceIp'])
                            if not newSubnet is None:
                                if str(newSubnet) != str(orgVlan['subnet']) and str(newRouterIp) != str(orgVlan['applianceIp']):
                                    success, batchId = sendUpdateVlanSubnetToActionBatchQueue(arg_apikey, orgId, net.id, vlan, str(newSubnet), str(newRouterIp))
                                    if success:
                                        if not batchId is None:
                                            batchIdList.append(batchId)
                                    else:
                                        print('ERROR 31: Error submitting action batch')
                            else:
                                print('ERROR 32: Subnet for net "%s" VLAN %s must be in form x.x.x.x with no mask/prefix' % (net.name, vlan))
                            break
                    if vlanNotFound:
                        print('ERROR 33: Template for network "%s" does not contain VLAN %s' % (net.name, vlan))
                        
    #Check if any networks have devices to claim
    aNetworkHasDevicesToClaim   = False
    gotDeviceClaimConflicts     = False
    for net in networks:
        if len(net.serials) > 0:
            aNetworkHasDevicesToClaim = True
            break
            
    if aNetworkHasDevicesToClaim:
        print('Claiming devices...')
        
        inventory = getOrgInventory(arg_apikey, orgId)
        if not inventory is None:
            for net in networks:
                for serial in net.serials:                 
                    deviceIsAvailable = True
                    deviceBelongsToAnotherNetwork = False
                    for orgDevice in inventory:
                        if orgDevice['serial'] == serial:   
                            if 'networkId' in orgDevice and not orgDevice['networkId'] is None:
                                deviceIsAvailable = False
                                if orgDevice['networkId'] != net.id:
                                    deviceBelongsToAnotherNetwork = True
                            break
                    
                    if deviceIsAvailable:
                        success, batchId = sendClaimDeviceToActionBatchQueue(arg_apikey, orgId, net.id, serial)
                        if success:
                            if not batchId is None:
                                batchIdList.append(batchId)
                        else:
                            print('ERROR 34: Error submitting action batch')
                    else:
                        if deviceBelongsToAnotherNetwork:
                            gotDeviceClaimConflicts = True
                            print('ERROR 35: Device %s belongs to another network' % serial)
                             
        else:
            print('ERROR 37: Failed to fetch organization inventory')
                
    #if unsubmitted VLAN update or device config commands, submit last batch
    success, batchId = queueActionBatch (arg_apikey, orgId, None, True)
    if success:
        if not batchId is None:
            batchIdList.append(batchId)
    else:
        print('ERROR 38: Error submitting action batch')
    
    #Get the status of device claim batches before continuing to next step. Endpoints to update devices are not available
    # before devices are claimed into a network, and will cause an error if called prematurely
    if len(batchIdList) > 0:
        print('Waiting for action batches to complete...')
        success = waitForActionBatchesToComplete(arg_apikey, orgId, batchIdList)
        
        if not success:
            print('ERROR 40: An action batch has failed to execute')
            killScript()
        
    if aNetworkHasDevicesToClaim and not gotDeviceClaimConflicts:
        print('Updating device location information...')
        batchIdList = []
        for net in networks:
            if not (net.location is None or net.location.strip() == ''):
                for serial in net.serials:
                    success, batchId = sendUpdateDeviceLocationToActionBatchQueue(arg_apikey, orgId, net.id, serial, net.location)
                    if success:
                        if not batchId is None:
                            batchIdList.append(batchId)
                    else:
                        print('ERROR 36: Error submitting action batch') 
                        
        #if unsubmitted location updates, submit last batch
        success, batchId = queueActionBatch (arg_apikey, orgId, None, True)
        if success:
            if not batchId is None:
                batchIdList.append(batchId)
        else:
            print('ERROR 39: Error submitting action batch')
        
        #Get the status of any remaining action batches before exiting
        if len(batchIdList) > 0:
            print('Waiting for action batches to complete...')
            waitForActionBatchesToComplete(arg_apikey, orgId, batchIdList)
            
    print('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])