readMe = '''
This is a script to set attributes of a switch port, if a client with a matching MAC OUI is found connected to it.

 *** TO PREVENT UNWANTED CHANGES, PLEASE RUN IN SIMULATION MODE FIRST ***

Usage:
 python setSwitchPortOnMacOui.py -k <api key> -f <MAC file> -c <Conf file> [-o <org name>] [-m <mode>]

Parameters:
  -k <api key>    :   Mandatory. Your Meraki Dashboard API key
  -f <MAC file>   :   Mandatory. Path to file containing MAC/OUI definitions to match
  -c <CFG file>   :   Mandatory. Path to file containing configuration changes to execute
  -o <org name>   :   Optional. Name of the organization you want to process. Use keyword "/all" to explicitly
                       specify all orgs. Default is "/all"
  -m <mode>       :   Optional. Defines whether changes will be committed to the Meraki cloud. Valid values:
                       simulation       Do not commit changes, just print logs (default)
                       commit           Commit changes to Meraki cloud

Example:
  python setSwitchPortOnMacOui.py -k 1234 -o "Big Industries Inc" -f macs.txt -c cfg.txt -m commit
  
Example MAC OUI file:
  https://github.com/meraki/automation-scripts/blob/master/setSwitchPortOnMacOui/ouilist.txt

Example configuration file:
  https://github.com/meraki/automation-scripts/blob/master/setSwitchPortOnMacOui/cmdlist.txt

Notes:
 * This script uses two endpoints that were in Beta at time of writing. If the script fails to fetch client lists
    with a status code of 404, you will need to have these enabled by Meraki for your organization:
        "List the clients that have used this network in the timespan"
        "Action batches"        
 * In Windows, use double quotes ("") to enter command line parameters containing spaces.
 * This script was built for Python 3.7.1.
 * Depending on your operating system, the command to start python can be either "python" or "python3". 

Required Python modules:
  Requests     : http://docs.python-requests.org
After installing Python, you can install these additional modules using pip with the following commands:
  pip install requests

Depending on your operating system, the command can be "pip3" instead of "pip".'''

import sys, getopt, requests, json, time, datetime

#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR

API_EXEC_DELAY              = 0.21 #Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

#page length for network clients' call. Range: 3-1000 clients/page
NET_CLIENTS_PAGE_LENGTH     = 1000

#fetch info on clients present during the past X days. Range: 1-30 days
NET_CLIENT_LOOKUP_TIME_DAYS = 7

#how many configuration changes the script will attempt to commit with a single call. Range: 1-1000 changes.
ACTION_BATCH_SIZE           = 100

#SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()
ARG_APIKEY                  = '' #DO NOT STATICALLY SET YOUR API KEY HERE
ARG_ORGNAME                 = '' #DO NOT STATICALLY SET YOUR ORGANIZATION NAME HERE
SECONDS_IN_DAY              = 86400
           
class c_Net:
    def __init__(self):
        self.id          = ''
        self.name        = ''
        self.shard       = 'api.meraki.com'
        self.devices     = []
        
class c_Organization:
    def __init__(self):
        self.id          = ''
        self.name        = ''
        self.shard       = 'api.meraki.com'
        self.nets        = []
        
        
#SECTION: General use functions

def merakiRequestThrottler():
    #makes sure there is enough time between API requests to Dashboard not to hit shaper
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return
    
def printhelp():
    print(readMe)
    
    
def matchOui(p_mac, p_ouiList):
    for oui in p_ouiList:
        if p_mac.lower().startswith(oui.lower()):
            return True

    return False
    
    
def loadFile(p_fileName):
    returnValue = []

    try:
        f = open(p_fileName, 'r')
    
        for line in f:
            if len(line) > 0:
                returnValue.append(line.strip())
            
        f.close()
    except:
        print('ERROR 06: Error loading file "%s"' % p_fileName)
        return None     
        
    return returnValue
    
    
def parseConfig(p_rawConfig):
    ret = []

    for line in p_rawConfig:
        splitLine = line.split(':')
        if len(splitLine) == 2:
            ret.append([splitLine[0].strip(), splitLine[1].strip()])
        else:
            return None
    return ret
    
    
def buildAccessSwitchList(p_org):
    returnValue = []

    orgInventory = getInventory(p_org)
    if orgInventory == None:
        return None
            
    for device in orgInventory:
        if device['model'].startswith('MS'):
            if not device['model'].startswith('MS4'):
                returnValue.append(device)
                
    return returnValue


def checkIfOnValidAccessSwitch(p_serial, p_switchList):
    for switch in p_switchList:
        if p_serial == switch['serial']:
            return True

    return False
    
    
#SECTION: Meraki Dashboard API communication functions

def getInventory(p_org):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    if True:
        r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_org.shard, p_org.id), headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    else:
        print('ERROR 00: Unable to contact Meraki cloud')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
    

def getNetworks(p_org):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_org.shard, p_org.id), headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 01: Unable to contact Meraki cloud')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
        

def getOrgs():
    #returns the organizations' list for a specified admin, with filters applied
        
    merakiRequestThrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 02: Unable to contact Meraki cloud')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
        
    rjson = r.json()
    orglist = []
    listlen = -1
    
    if ARG_ORGNAME.lower() == '/all':
        for org in rjson:
            orglist.append(c_Organization())
            listlen += 1
            orglist[listlen].id     = org['id']
            orglist[listlen].name   = org['name']
    else:
        for org in rjson:
            if org['name'] == ARG_ORGNAME:
                orglist.append(c_Organization())
                listlen += 1
                orglist[listlen].id     = org['id']
                orglist[listlen].name   = org['name']
    
    return(orglist)
    
    
def getShardHost(p_org):
    #patch
    return("api.meraki.com")
    
    
def getNetworkClients(p_org, p_net):
    # Returns all clients in a network, or None on failure
    
    returnValue = []    
    networkHasMoreClientPages = True        
    requestUrl = 'https://%s/api/v0/networks/%s/clients?perPage=%s&timespan=%s' % (p_org.shard, p_net, NET_CLIENTS_PAGE_LENGTH, NET_CLIENT_LOOKUP_TIME_DAYS*SECONDS_IN_DAY)
    
    while networkHasMoreClientPages:
        merakiRequestThrottler()
    
        try:
            r = requests.get( requestUrl, headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
        except:
            print('ERROR 04: Error fetching client list for network %s' % p_net)
            return None
                        
        if r.status_code != requests.codes.ok:
            print('ERROR 05: Error fetching client list for network %s (Status: %s)' % (p_net, r.status_code))
            return None
            
        returnValue += r.json()
            
        responseHeaders = r.headers
            
        if 'Link' in responseHeaders:
            link        = responseHeaders['Link']
            nextPageEnd = link.find('>; rel=next')
            if nextPageEnd == -1:
                networkHasMoreClientPages = False
            else:
                croppedLink     = link[:nextPageEnd]
                nextPageStart   = croppedLink.rfind('https://')
                requestUrl      = croppedLink[nextPageStart:]

    return returnValue
    

def executeActionBatch (p_org, p_portList, p_config):
    print('Executing action batch...')
        
    requestUrl = 'https://%s/api/v0/organizations/%s/actionBatches' % (p_org.shard, p_org.id)
    
    payload = {'confirmed':True, 'synchronous':False}
    
    actions = []

    for item in p_portList:
        a = {'resource':'/devices/%s/switchPorts/%s' % (item[0],item[1]), 'operation': 'update'}
        b = {}
        for cmd in p_config:
            b[cmd[0]] = cmd[1]
        a['body'] = b
        
        actions.append(a)
    
    payload['actions'] = actions
    
    
    merakiRequestThrottler()
    try:
        r = requests.post(requestUrl, data=json.dumps(payload), headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 07: Unable to contact Meraki cloud')
        return False
        
    if r.status_code >= 400:
        print (r.status_code)
        return False
                
    return True
       

    
#SECTION: main
    
def main(argv):
    global ARG_APIKEY
    global ARG_ORGNAME
    
    #initialize command line arguments
    ARG_APIKEY      = ''
    ARG_ORGNAME     = ''
    arg_macFile     = ''
    arg_cfgFile     = ''
    arg_mode        = ''   
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:f:c:o:m:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
        
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            ARG_APIKEY      = arg
        elif opt == '-f':
            arg_macFile     = arg
        elif opt == '-c':
            arg_cfgFile     = arg
        elif opt == '-o':
            ARG_ORGNAME     = arg
        elif opt == '-m':
            arg_mode        = arg
            
    #check that all mandatory arguments have been given
    if ARG_APIKEY == '' or arg_macFile == '' or arg_cfgFile == '':
        printhelp()
        sys.exit(2)        
            
    #set defaults for empty command line arguments
    if ARG_ORGNAME  == '':
        ARG_ORGNAME = '/all'
        
    if arg_mode     == '':
        arg_mode    = 'simulation'
        
        
    #script main body    
       
    ouiList     = loadFile(arg_macFile)
    if ouiList is None:
        print ('ERROR 08: Unable to load OUI file')
        sys.exit(2)  
    
    rawCfg      = loadFile(arg_cfgFile)
    if rawCfg  is None:
        print ('ERROR 09: Unable to load config file')
        sys.exit(2)  
        
    cfgList     = parseConfig(rawCfg)
    if cfgList is None:
        print ('ERROR 10: Unable to parse configuration')
        sys.exit(2)  
    
    orglist     = getOrgs()
    
    if not orglist is None:
        for org in orglist:
            print('Processing org "%s"' % org.name)
            
            actionBatchQueue    = []
            
            orgshard            = getShardHost(org)
            
            if not orgshard is None:
                org.shard       = orgshard
                
            netlist             = getNetworks(org)
            devlist             = buildAccessSwitchList(org)
                            
            if not devlist is None and not netlist is None:
                for net in netlist:
                
                    clientList = getNetworkClients(org, net['id'])
                    
                    if not clientList is None:
                        for client in clientList:
                            if matchOui(client['mac'], ouiList):
                                if checkIfOnValidAccessSwitch(client['recentDeviceSerial'], devlist):
                                    print ('QUEUED: Will edit port for MAC %s: "%s" (%s) Port %s' % (client['mac'], client['recentDeviceName'], client['recentDeviceSerial'], client['switchport']) )
                                    if arg_mode == 'commit':
                                        actionBatchQueue.append([client['recentDeviceSerial'], client['switchport']])
                                        if len(actionBatchQueue) >= ACTION_BATCH_SIZE:
                                            batchSuccess = executeActionBatch (org, actionBatchQueue, cfgList)
                                            if batchSuccess:
                                                print ('SUCCESS: Batch operation successful')
                                            else:
                                                print ('ERROR 11: Batch operation failed')
                                            actionBatchQueue = []
                                            
                                            
                                else:
                                    print ('Skipping client "%s". Owner device "%s" (%s) not an access switch' % (client['mac'], client['recentDeviceName'], client['recentDeviceSerial']))
            
            if arg_mode == 'commit':            
                if len(actionBatchQueue) > 0:
                    batchSuccess = executeActionBatch (org, actionBatchQueue, cfgList)
                    if batchSuccess:
                        print ('SUCCESS: Batch operation successful')
                    else:
                        print ('ERROR 12: Batch operation failed')
                
                
        
if __name__ == '__main__':
    main(sys.argv[1:])