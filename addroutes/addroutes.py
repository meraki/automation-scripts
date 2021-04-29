readMe = """
This is a script to add static routes to a network from a CSV file.

Usage:
  python addroutes.py -k <api key> -o <org name> -n <net name> -f <input file name>
  
Example:
  python addroutes.py -k 1234 -o "My Beautiful Company" -n "VPN Hub" -f routes.csv
  
Input file example:
  https://github.com/meraki/automation-scripts/blob/master/addroutes/routes.txt
  
Notes:    
 * In Windows, use double quotes ("") to enter command line parameters containing spaces.
 * This script was built for Python 3.7.1.
 * Depending on your operating system, the command to start python can be either "python" or "python3". 

Required Python modules:
  Requests     : http://docs.python-requests.org
After installing Python, you can install these additional modules using pip with the following commands:
  pip install requests

Depending on your operating system, the command can be "pip3" instead of "pip".
"""

import sys, getopt, requests, time, datetime, ipaddress, json

#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR

API_EXEC_DELAY              = 0.21 #Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

#SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()


#SECTION: General use functions


def merakiRequestThrottler():
    #prevents hitting max request rate shaper of the Meraki Dashboard API
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return
    
    
def printhelp():
    print(readMe)
    
    
def loadFile(p_fileName):
    returnValue = []

    try:
        f = open(p_fileName, 'r')
    
        for line in f:
            if len(line) > 0:
                stripped = line.strip()
                if len(stripped) > 0:
                    if stripped[0] != "#":
                        returnValue.append(stripped)
            
        f.close()
    except:
        print('ERROR 01: Error loading file "%s"' % p_fileName)
        return None     
        
    return returnValue
    
    
def parseCSV(p_csv):
    retval = []
    unnamed = 0
    for line in p_csv:
        splitStr = line.split(',')
        lenSplit = len(splitStr)
        try:
            if splitStr[0].find('/') == -1:
                raise 'Destination must contain a "/"'
            destination = str(ipaddress.IPv4Network(splitStr[0].strip(), False))
            gateway     = str(ipaddress.IPv4Address(splitStr[1].strip()))
        except:
            print('ERROR 02: Input file line not valid: "%s"' % line)
            return None 
        if len(splitStr) > 2:
            name = splitStr[2].strip()
        else:
            name = "addroutes.py " + str(unnamed)
            unnamed += 1
            
        retval.append({"name":name, "subnet":destination, "gatewayIp":gateway})
            
    return retval
    
       
#SECTION: Meraki Dashboard API communication functions


def getOrgId(p_apiKey, p_orgName):
    #returns the organizations' list for a specified admin, with filters applied
        
    merakiRequestThrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
        
    rjson = r.json()
    
    for org in rjson:
        if org['name'] == p_orgName:
            return org['id']
    
    return(None)
    
    
def getNetId(p_apiKey, p_orgId, p_shard, p_netName):
    merakiRequestThrottler()
    
    requestUrl = "https://%s/api/v0/organizations/%s/networks" % (p_shard, p_orgId)
    
    try:
        r = requests.get(requestUrl, headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
        
    rjson = r.json()
    
    for net in rjson:
        if net['name'] == p_netName:
            return net['id']
    
    return(None)
    
    
def getShardHost(p_apiKey, p_orgId):
    #patch
    return("api.meraki.com")
    
    
def addRoute(p_apiKey, p_shard, p_netId, p_routeData):

    merakiRequestThrottler()
    
    requestUrl = "https://%s/api/v0/networks/%s/staticRoutes" % (p_shard, p_netId)
    
    if True:
        r = requests.post(requestUrl, data=json.dumps(p_routeData), headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    else:
        print('ERROR 03: Unable to contact Meraki cloud')
        return False
        
    if r.status_code >= 400:
        print ("ERROR 04: %s" % r.json()['errors'][0])
        return False
    return True

    
#SECTION: main
    
def main(argv):
    argApiKey   = ""
    argOrgName  = ""
    argNetName  = ""
    argFile     = ""
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:n:f:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
        
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            argApiKey   = arg
        elif opt == '-o':
            argOrgName  = arg
        elif opt == '-n':
            argNetName  = arg
        elif opt == '-f':
            argFile     = arg
            
    #make sure all mandatory arguments have been given
    if argApiKey == '' or argOrgName == '' or argNetName == '' or argFile == '':
        printhelp()
        sys.exit(2)
        
    rawFile = loadFile(argFile)    
    if rawFile is None:
        sys.exit(2)
        
    routeList = parseCSV(rawFile)    
    if routeList is None:
        sys.exit(2)
        
    orgId = getOrgId(argApiKey, argOrgName)    
    if orgId is None:
        print("ERROR 05: Unable to fetch organization Id")
        sys.exit(2)
    print ('Organization ID is %s' % orgId)
        
    shard = getShardHost(argApiKey, orgId)    
    if shard is None:
        print("WARNING: Shard host is None")
        shard = "api.meraki.com"
        
    netId = getNetId(argApiKey, orgId, shard, argNetName)    
    if netId is None:
        print("ERROR 06: Unable to fetch network Id")
        sys.exit(2)        
    print ('Network ID is %s' % netId)
        
    for route in routeList:
        print("Adding route: %s" % json.dumps(route))
        r = addRoute(argApiKey, shard, netId, route)
 
        
if __name__ == '__main__':
    main(sys.argv[1:])