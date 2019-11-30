read_me = '''This is a Python 3 script to migrate configuration from Catalyst 3750-X to Meraki MS-series switches.

Usage syntax:
  python migrate_cat3k.py -k <API key> -o <org name> -i <init file> [-u <default user> -p <default pass> -x <proxy>]

Mandatory parameters:
  -k <API key>              : Your Meraki Dashboard API key
  -o <org name>             : Name of the Meraki organization you want to interact with
  -i <init file>            : OS path to the init configuration file
  
Optional parameters:
  -u <default user>         : Catalyst switch SSH username, if none is defined in init config    
  -p <default pass>         : Catalyst switch SSH password, if none is defined in init config  
  -x <proxy>                : Whether to use the new Dashboard API mega proxy or not. Valid forms:
                                -x use_mega_proxy           Sends API requests to "api-mp.meraki.com" (default)
                                -x do_not_use_mega_proxy    Sends API requests to "api.meraki.com"

Usage example:
  python migrate_cat3k.py -k 1234 -o "My Meraki Account" -i init_config.txt

Init configuration file example:
  https://github.com/meraki/automation-scripts/blob/master/migrate_cat3k/migrate_cat3k_init_example.txt

Usage notes:
  SSH sources require a username and password, either by setting the defaults, or providing one in the init file.

Required Python modules:
  Requests     : http://docs.python-requests.org
  Paramiko     : http://www.paramiko.org/installing.html
  
  After installing Python, you can install these additional modules using pip with the following commands:
    pip install requests
    pip install paramiko

General notes:
  * Depending on your operating system, the commands can be "pip3" and "python3" instead of "pip" and "python"
  * In Windows, to pass argument values containing spaces, you will need to use double quotes ""
  * The usernames provided for SSH access to source switches must have a privilege level of 15. In it's
     current form, the script will not attempt to enter the enable command
  * The Meraki Dashboard API key used must have full organization permissions
  * The only IOS platform tested is the Catalyst 3750-X
  * The CLI parser currently supports the following IOS commands:
     hostname
     interface GigabitEthernet
       description
       switchport mode
       switchport access vlan
       switchport voice vlan
       switchport trunk native vlan
     vlan
       name        
'''

import sys, getopt, requests, json, paramiko, re, time, datetime

#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR

API_EXEC_DELAY              = 0.21 #Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

#SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()
API_BASE_URL                = 'https://api-mp.meraki.com/api/v0'
API_BASE_URL_MEGA_PROXY     = 'https://api-mp.meraki.com/api/v0'
API_BASE_URL_NO_MEGA        = 'https://api.meraki.com/api/v0'
ACTION_BATCH_QUEUE          = []


#SECTION: Classes
      

class c_conversion:
    def __init__(self):
        self.hostname           = None
        self.rawConfig          = None
        self.sourceType         = None
        self.sourceValue        = None
        self.sourceUser         = None
        self.sourcePass         = None
        self.targetNetwork      = None
        self.targetDevices      = []
        self.portConfig         = None
#end class


### SECTION: General functions


def printHelpAndExit():
    print(read_me)
    sys.exit(0)
    
    
def portCountsForSwitchModel (p_model):
    copper  = None
    sfp     = None
    if p_model.startswith('MS'):
        splitNumbers = re.findall(r'\d+', p_model)
        #check if switch is a supported device model
        if int(splitNumbers[0]) in [120, 125, 210, 220, 225, 250, 350, 410, 425]:
            copper = int(splitNumbers[1])
            if copper == 8:
                sfp = 2
            elif copper in [24, 48]:
                sfp = 4
            else:
                sfp = 0
                
    return copper, sfp
    

### SECTION: Functions for interacting with SSH and files    
    
    
def loadinitcfg(p_filename, p_defaultuser, p_defaultpass):
    #loads initial configuration from a file with network and device definitions
    
    configtable = []
    netList = []
    serialList = []
    
    failValue = [None, None, None]
    
    networkdefined = False
    currentnet = ''
    dcount = 0
    
    linenum = 0
    try:
        f = open(p_filename, 'r')
    except:
        return(configtable)
    
    #iterate through file and parse lines
    for line in f:
        linenum += 1
        stripped = line.strip()
        #drop blank lines
        if len(stripped) > 0:
            #drop comments
            if stripped[0] != '#':
                #process network definition lines
                if stripped [:4] == 'net=':
                    if len(stripped[4:]) > 0:
                        currentnet = stripped[4:].strip()
                        networkdefined = True
                        netList.append( {'name': currentnet} )
                    else:
                        print('ERROR 01: Init config (line %d): Network name cannot be blank' % linenum)
                        return failValue       
                else:
                    #else process as a device record
                    if networkdefined:
                        splitline = stripped.split()
                        if len(splitline) > 1:
                            configtable.append(c_conversion())
                            lastItem = len(configtable) - 1
                            configtable[lastItem].targetNetwork = currentnet
                            
                            #look for file keyword and load source accordingly
                            if splitline[0] == 'file':
                                configtable[lastItem].sourceType = 'file'
                                if len(splitline) > 2:
                                    configtable[lastItem].sourceValue = splitline[1].strip()
                                    remainingFields = splitline [2:]
                                    
                                else:
                                    print('ERROR 02: Init config (line %d): Invalid definition: %s' % (linenum, stripped))
                                    return failValue
                            else:
                                #not a source file definition. assume FQDN/IP
                                configtable[lastItem].sourceType = 'fqdn'
                                configtable[lastItem].sourceValue = splitline[0].strip()
                                remainingFields = splitline [1:]
                                
                            #map to correct Meraki serial(s)   
                            if len(remainingFields) > 0:
                                serials = remainingFields[0].split(',')
                                for serial in serials:
                                    configtable[lastItem].targetDevices.append(serial)
                                    #configtable[lastItem].targetDevices[len(configtable[lastItem].targetDevices)-1].serial = serial
                                    serialList.append( {'serial': serial, 'networkName': currentnet} )
                                    
                            if len(remainingFields) > 2:
                                #device-specific username and password defined
                                configtable[lastItem].sourceUser = remainingFields[1]
                                configtable[lastItem].sourcePass = remainingFields[2]
                            elif len(remainingFields) > 1:
                                #got either username or password, but not both
                                print('ERROR 03: Init config (line %d): Invalid definition: %s' % (linenum, stripped))
                                return failValue
                            else:
                                #no device-specific username/password configuration. use defaults
                            
                                #abort if default user/password are invalid
                                if (p_defaultuser == None or p_defaultpass == None) and configtable[lastItem].sourceType == 'fqdn':
                                    print('ERROR 04: Default SSH credentials needed, but not defined')
                                    return failValue
                                configtable[lastItem].sourceUser = p_defaultuser
                                configtable[lastItem].sourcePass = p_defaultpass
                        else:
                            print('ERROR 05: Init config (line %d): Invalid definition: %s' % (linenum, stripped))
                            return failValue
                    else:
                        print('ERROR 06: Init config (line %d): Device with no network defined' % linenum)
                        return failValue
                    
    f.close()
                        
    return (configtable, netList, serialList)
    
    
def waitForOutput(p_session, p_timeout):
    increment = 0.1
    i = 0
    while i < p_timeout:
        i += increment
        time.sleep(increment)
        if p_session.recv_ready():
            return p_session.recv(65535).decode('ascii')
    return None  
    

def loadCatalystConfigSsh (p_hostip, p_user, p_pass):
    #logs into a IOS-based device using SSH and pulls its current configuration
    #returns None on error
    
    linetable = []
    configStr = ''
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(p_hostip, username=p_user, password=p_pass)
        session = ssh.invoke_shell()
        output = waitForOutput(session, 10)
        session.send("show running\n")
        output = waitForOutput(session, 10)
        outputHasMorePages = True
        while outputHasMorePages:   
            outputHasMorePages = False
            page = waitForOutput(session, 10)
            if not page is None:
                length = len(page)
                if length > 9:
                    if page[length-9:].strip() == "--More--":
                        configStr += page[:length-9]
                        session.send(" ")
                        outputHasMorePages = True
                    else:
                        configStr += page     
    except:
        print('ERROR 07: Could not connect to source device: "%s"' % p_hostip)
        return None
        
    if configStr == '':
        print('ERROR 08: No config on device: "%s"' % p_hostip)
        return None
        
    for line in configStr.splitlines():
        strippedline = line.strip()
        if len(strippedline) > 0:
            #ignore comments
            if strippedline[0] != '!':
                stringWithoutBackspaces = ''
                for char in strippedline:
                    if char == '\x08': #check if character is a backspace
                        stringWithoutBackspaces += ' '
                    else:
                        stringWithoutBackspaces += char
                linetable.append(stringWithoutBackspaces.strip())
                
    return (linetable)
    
    
def loadCatalystConfigFile(p_filename):
    #loads source device configuration from file
    
    linetable = []
    try:
        f = open(p_filename, 'r')
    except:
        print('ERROR 09: Could not read source config file: %s' % p_filename)
        return None
        
    strippedline = ''
    
    for line in f:
        strippedline = line.strip()
        if len(strippedline) > 0:
            #ignore comments
            if strippedline[0] != '!':
                linetable.append(strippedline)
                
    f.close()
    
    return (linetable)
    
    
def parseHostname(p_rawcfg):
    #extract hostname form device config
    
    #command parser loop
    for cfgline in p_rawcfg:
        pieces = cfgline.split()
        
        if pieces[0] == 'hostname':
            return (pieces[1].strip())
        
    return None
        
def parsePortConfig(p_rawcfg):
    #parses port (interface) configuration from a Catalyst configuration table
        
    stackMembers        = []
    currentStackMember  = 0
    currentModule       = 0
    currentPort         = 0
    currentVlan         = 0
    vlanNames           = {}
    
    intcount = 0
    avlan = '' #string for building allowed VLAN value
    supportedinterface = False
        
    #command parser loop
    for cfgline in p_rawcfg:
        pieces = cfgline.split()
        
        firstPiece = pieces[0].strip()
              
        if firstPiece == 'interface':
            #if interface is of a supported type, create new entry. otherwise ignore it
            #and lock int command parsing functions until a supported one comes up
            if pieces[1].startswith('GigabitEthernet'):
                intNumber           = pieces[1][15:]
                splitNumber         = intNumber.split('/')
                currentStackMember  = int(splitNumber[0]) - 1
                currentModule       = splitNumber[1]
                currentPort         = splitNumber[2]
                
                if len(stackMembers) <= currentStackMember:
                    stackMembers.append({'0':{}, '1':{}})
                                
                supportedinterface = True
            else:
                supportedinterface = False
                                
        elif firstPiece == 'description' and supportedinterface:
            if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                stackMembers[currentStackMember][currentModule][currentPort] = {}
            #set int desc as port name. strip everything except alphanumerics and "_"
            stackMembers[currentStackMember][currentModule][currentPort]['name'] = re.sub(r'\W+','_', cfgline[12:])[:20]
            
        elif firstPiece == 'switchport' and supportedinterface:
            
            if pieces[1] == 'mode':
                if pieces[2] == 'access':
                    if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                        stackMembers[currentStackMember][currentModule][currentPort] = {}
                    stackMembers[currentStackMember][currentModule][currentPort]['mode'] = 'access'

                elif pieces[2] == 'trunk':
                    if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                        stackMembers[currentStackMember][currentModule][currentPort] = {}
                    stackMembers[currentStackMember][currentModule][currentPort]['mode'] = 'trunk'
            
            elif pieces[1] == 'access':
                if pieces[2] == 'vlan':
                    if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                        stackMembers[currentStackMember][currentModule][currentPort] = {}
                    stackMembers[currentStackMember][currentModule][currentPort]['access'] = pieces[3]
                    if not 'tags' in stackMembers[currentStackMember][currentModule][currentPort]:
                        stackMembers[currentStackMember][currentModule][currentPort]['tags'] = ''
                    stackMembers[currentStackMember][currentModule][currentPort]['tags'] += vlanNames[pieces[3]]                   
                    stackMembers[currentStackMember][currentModule][currentPort]['tags'] += ' '                  
                    
            elif pieces[1] == 'voice':
                if pieces[2] == 'vlan':
                    if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                        stackMembers[currentStackMember][currentModule][currentPort] = {}
                    stackMembers[currentStackMember][currentModule][currentPort]['voice'] = pieces[3]
                    if not 'tags' in stackMembers[currentStackMember][currentModule][currentPort]:
                        stackMembers[currentStackMember][currentModule][currentPort]['tags'] = ''
                    stackMembers[currentStackMember][currentModule][currentPort]['tags'] += vlanNames[pieces[3]]                   
                    stackMembers[currentStackMember][currentModule][currentPort]['tags'] += ' '  
                    
            elif pieces[1] == 'trunk':
                if pieces[2] == 'native':
                    if pieces[3] == 'vlan':                
                        if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                            stackMembers[currentStackMember][currentModule][currentPort] = {}
                        stackMembers[currentStackMember][currentModule][currentPort]['native'] = pieces[4]
                        
                        
                elif pieces[2] == 'allowed':
                    if pieces[3] == 'vlan':
                        if not str(currentPort) in stackMembers[currentStackMember][currentModule]:
                            stackMembers[currentStackMember][currentModule][currentPort] = {}
                        stackMembers[currentStackMember][currentModule][currentPort]['allowed'] = []
                        if not 'tags' in stackMembers[currentStackMember][currentModule][currentPort]:
                            stackMembers[currentStackMember][currentModule][currentPort]['tags'] = ''
                        splitStr = pieces[4].split(',')
                        for line in splitStr:
                            stackMembers[currentStackMember][currentModule][currentPort]['allowed'].append(line)
                            stackMembers[currentStackMember][currentModule][currentPort]['tags'] += vlanNames[line]
                            stackMembers[currentStackMember][currentModule][currentPort]['tags'] += ' '
                        
        elif firstPiece == 'vlan':
            try:
                currentVlan = int(pieces[1])
            except:
                currentVlan = 0
            
        elif firstPiece == 'name':
            vlanNames[str(currentVlan)] = pieces[1]
                                    
    return(stackMembers)
        
        
### SECTION: Functions for interacting with Dashboard       


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
    
    
def getNetworks(p_apiKey, p_orgId):
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
    
    
def getInventory(p_apiKey, p_orgId):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations/%s/inventory' % p_orgId, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 11: Unable to get inventory')
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
        print('Committing action batch:')
        print(ACTION_BATCH_QUEUE)
        
        batchId = createActionBatch (p_apiKey, p_orgId, ACTION_BATCH_QUEUE)        
        ACTION_BATCH_QUEUE = []
        
        if not batchId is None:
            return (True, batchId)
        else:
            return (False, None)
    
    return (True, None)
    
    
def getActionBatches(p_apiKey, p_orgId):
    merakiRequestThrottler()
    try:
        r = requests.get( API_BASE_URL + '/organizations/%s/actionBatches' % p_orgId, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 12: Unable to get action batches')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
    
    
def waitForActionBatchesToComplete(p_apiKey, p_orgId, p_batchIds):
    flag_waitSomeMore   = True
    flag_batchHasFailed = False
    
    while flag_waitSomeMore:
        flag_waitSomeMore   = False
        actionBatches       = getActionBatches(p_apiKey, p_orgId)
        for id in p_batchIds:
            for record in actionBatches:
                if record['id'] == id:
                    if not record['status']['completed']:
                        flag_waitSomeMore = True
                        break
                    if record['status']['failed']:
                        return False
        if flag_waitSomeMore:
            time.sleep(2)                        
    return True
    
    
def sendHostnameToQueue(p_apiKey, p_orgId, p_networkId, p_hostname, p_increment, p_serial):
    if not p_hostname is None:
        name = p_hostname
        if p_increment > 0:
            name += '_%s' % p_increment
            
        body = {
            'name'    : name
        }
        action = {
            'resource'  : '/networks/' + p_networkId + '/devices/' + p_serial,
            'operation' : 'update',
            'body'      : body
        }    
        success, batchId = queueActionBatch (p_apiKey, p_orgId, action)
        if not success:
            print('ERROR 13: Failed to queue action batch')
        
    return None
    
    
def sendPortConfigToQueue(p_apiKey, p_orgId, p_portConfig, p_serial, p_copperCount, p_sfpCount):
    #p_portConfig module 0: copper ports, module 1: sfp ports
    portList = []
        
    for port in p_portConfig['0']:
        portNum = int(port)
        config = p_portConfig['0'][port]
        if portNum <= int(p_copperCount):
            portList.append({'number': portNum, 'config': config})
            
    for port in p_portConfig['1']:
        portNum = int(port)
        config = p_portConfig['1'][port]
        if portNum <= int(p_sfpCount):
            portList.append({'number': portNum + int(p_copperCount), 'config': config})
    
    for port in portList:        
        body = {}
        switchportMode = 'access'
        if 'mode' in port['config']:
            body['type']        = port['config']['mode']
            if port['config']['mode'] == 'trunk':
                switchportMode = 'trunk'
        if 'access' in port['config']:
            if switchportMode == 'access':
                body['vlan']    = port['config']['access']
        if 'voice' in port['config']:
            body['voiceVlan']   = port['config']['voice']
        if 'tags' in port['config']:
            body['tags']        = port['config']['tags']
        if 'native' in port['config']:
            if switchportMode == 'trunk':
                body['vlan']    = port['config']['native']
                       
        action = {
            'resource'  : '/devices/' + p_serial + '/switchPorts/' + str(port['number']),
            'operation' : 'update',
            'body'      : body
        }    
        
        success, batchId = queueActionBatch (p_apiKey, p_orgId, action)
        if not success:
            print('ERROR 14: Failed to queue action batch')
    
    return None

  
### SECTION: Main function    

  
def main(argv):
    global API_BASE_URL
    
    #set default values for command line arguments
    arg_apikey      = None
    arg_orgname     = None
    arg_initfile    = None      #a default value that is not a valid filename
    arg_defuser     = None      #a default value that is not a valid username
    arg_defpass     = None      #a default value that is not a valid password
    arg_proxy       = None
        
    try:
        opts, args = getopt.getopt(argv, 'hk:o:i:u:p:x:')
    except getopt.GetoptError:
        printHelpAndExit()
    
    for opt, arg in opts:
        if opt == '-h':
            printHelpAndExit()
        elif opt == '-k':
            arg_apikey = arg
        elif opt == '-o':
            arg_orgname = arg
        elif opt == '-i':
            arg_initfile = arg
        elif opt == '-u':
            arg_defuser = arg
        elif opt == '-p':
            arg_defpass = arg
        elif opt == '-x':
            arg_proxy = arg
                
    #check if all required parameters have been given
    if arg_apikey is None or arg_orgname is None or arg_initfile is None:
        printHelpAndExit()
        
    API_BASE_URL = API_BASE_URL_MEGA_PROXY
    if not arg_proxy is None:
        if arg_proxy == 'do_not_use_mega_proxy':
            API_BASE_URL = API_BASE_URL_NO_MEGA
            
            
    #load configuration file
    print('Reading init config file...')
    conversions, networks, devices = loadinitcfg(arg_initfile, arg_defuser, arg_defpass)
    
    if conversions is None or len(conversions) == 0:
        print('ERROR 15: No valid configuration in init file')
        sys.exit(2)
                        
    #get organization id corresponding to org name provided by user
    print('Fetching dashboard organization...')
    orgId = getOrgId(arg_apikey, arg_orgname)
    if orgId is None:
        print('ERROR 16: Fetching organization id failed')
        sys.exit(2)
                                
    #read configuration from source devices specified in init config
    print('Reading configuration from source devices...')
    for item in conversions:
        if item.sourceType is None:
            print('ERROR 17: No sourceType for sourceValue "%s"' % item.sourceValue)
        else:
            rawConfig = None
            if item.sourceType == 'file':
                rawConfig = loadCatalystConfigFile(item.sourceValue)
            elif item.sourceType == 'fqdn':
                rawConfig = loadCatalystConfigSsh (item.sourceValue, item.sourceUser, item.sourcePass)
            if not rawConfig is None:
                item.rawConfig = rawConfig
            else:
                print('ERROR 18: Unable to read configuration from source "%s"' % item.sourceValue)
            
    #parse hostname and other configuration from raw
    print('Parsing source configration...')
    for item in conversions:
        if item.rawConfig != None:
            item.hostname   = parseHostname(item.rawConfig)
            item.portConfig = parsePortConfig(item.rawConfig)
        
    #check if networks already exist and create missing
    print('Creating networks...')
    existingNetworks = getNetworks(arg_apikey, orgId)
    if existingNetworks is None:
        sys.exit(2)
    
    flag_createdNetworks = False
    batchIds = []
    for net in networks:
        networkFound = False
        for existing in existingNetworks:
            if existing['name'] == net['name']:
                if not existing['type'] in ['switch', 'combined']:
                    print('ERROR 19: Existing network "%s" is of wrong type "%s"' % (existing['name'], existing['type']))
                    sys.exit(2)
                networkFound = True
                break
        if not networkFound:
            body = {
                'name'      : net['name'],
                'type'      : 'switch',
                'tags'      : 'migrate_cat3k'
            }
            action = {
                'resource'  : '/organizations/' + orgId + '/networks',
                'operation' : 'create',
                'body'      : body
            }
            success, batchId = queueActionBatch (arg_apikey, orgId, action)
            if not success:
                print('ERROR 20: Failed to queue action batch')
                sys.exit(2)
            if not batchId is None:
                batchIds.append(batchId)
            flag_createdNetworks = True
               
    if flag_createdNetworks:
        success, batchId = queueActionBatch (arg_apikey, orgId, None, True)
        if not success:
            print('ERROR 21: Failed to queue action batch')
            sys.exit(2)
        if not batchId is None:
            batchIds.append(batchId)

        #check that all action batches have been completed before proceeding
        print('Waiting for action batches to complete...')
        result = waitForActionBatchesToComplete(arg_apikey, orgId, batchIds)
        
        if not result:
            print('ERROR 22: An action batch has failed to execute')
            sys.exit(2)
                    
        existingNetworks = getNetworks(arg_apikey, orgId)
        if existingNetworks is None:
            sys.exit(2)

    #get org inventory to check if devices are already claimed
    inventory = getInventory(arg_apikey, orgId)
    
    if inventory is None:
        sys.exit(2)         
            
    #claim devices into networks
    print('Claiming devices...')
    flag_claimedDevices = False
    batchIds = []
    for device in devices:
        device['netId'] = None
        flag_deviceFoundAndClaimed = False
        for existingDev in inventory:
            if device['serial'] == existingDev['serial']:
                #check if device is associated to a network and if it is the correct one
                if not existingDev['networkId'] is None:
                    for net in existingNetworks:
                        if net['id'] == existingDev['networkId']:
                            if net['name'] == device['networkName']:
                                device['networkId'] = net['id']
                                flag_deviceFoundAndClaimed = True
                            else:
                                print('ERROR 23: Switch "%s" is in use in another network (%s)' % (device['serial'], net['name']))
                                sys.exit(2)
                            break
                flag_deviceFound = True           
                break
        
        for net in existingNetworks:
            if net['name'] == device['networkName']:
                device['networkId'] = net['id']
                            
        if not flag_deviceFoundAndClaimed:
            body = {
                'serial'    : device['serial']
            }
            action = {
                'resource'  : '/networks/' + device['networkId'] + '/devices',
                'operation' : 'claim',
                'body'      : body
            }
            success, batchId = queueActionBatch (arg_apikey, orgId, action)
            if not success:
                print('ERROR 24: Failed to queue action batch')
                sys.exit(2)
            if not batchId is None:
                batchIds.append(batchId)
            flag_claimedDevices = True
            
    if flag_claimedDevices:
        success, batchId = queueActionBatch (arg_apikey, orgId, None, True)
        if not success:
            print('ERROR 25: Failed to queue action batch')
            sys.exit(2)
        if not batchId is None:
            batchIds.append(batchId)

        #check that all action batches have been completed before proceeding
        print('Waiting for action batches to complete...')
        result = waitForActionBatchesToComplete(arg_apikey, orgId, batchIds)
        
        if not result:
            print('ERROR 26: An action batch has failed to execute')
            sys.exit(2)
            
        #refresh inventory to get device models of newly claimed switches
        inventory = getInventory(arg_apikey, orgId)
        
        if inventory is None:
            sys.exit(2)   
                
    #calculate port counts for destination switches to prevent overflow   
    for device in devices:
        for record in inventory:
            if device['serial'] == record['serial']:
                device['model'] = record['model']
                copper, sfp = portCountsForSwitchModel(device['model'])
                if copper is None:
                    print('ERROR 27: Device model "%s" is not supported by this script' % device['model'])
                    sys.exit(2) 
                device['copper']    = copper
                device['sfp']       = sfp                    
                break
                
    #submit config  
    print('Configuring devices...')    
    for line in conversions:
        shortest        = len(line.portConfig)
        deviceListLen   = len(line.targetDevices)
        if deviceListLen < shortest:
            shortest    = deviceListLen
        for i in range(shortest):
            targetNetwork   = None
            copperPortCount = None
            sfpPortCount    = None
            for device in devices:
                if device['serial'] == line.targetDevices[i]:
                    targetNetwork   = device['networkId']
                    copperPortCount = device['copper']
                    sfpPortCount    = device['sfp']                    
                    break
            sendHostnameToQueue(arg_apikey, orgId, targetNetwork, line.hostname, i, line.targetDevices[i])
            sendPortConfigToQueue(arg_apikey, orgId, line.portConfig[i], line.targetDevices[i], copperPortCount, sfpPortCount)
            
    queueActionBatch (arg_apikey, orgId, None, True)    
        
    print('\nEnd of script.')                      
if __name__ == '__main__':
    main(sys.argv[1:])
