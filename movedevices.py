readMe = """This is a Python 3 script that can be used to move all devices from one organization to another.
The script will only process devices that are part of a network. A network tag filter can be used to
select which networks to include for the move and which to omit.

The script works via an intermediate file. You first have to run the script in export mode to export
and unclaim devices from the source organization and then run it again in import mode to import the devices
from the output file of the first run into your target organization. A direct migration is not supported,
to avoid possible issues due to devices not becoming claimable immediately after unclaiming.

Script syntax, Windows:
    python movedevices.py -m <mode> [-k <api_key>] [-o <org_name>] [-t <net_tag>] [-f <file_name>] 

Script syntax, Linux and Mac:
    python3 movedevices.py -m <mode> [-k <api_key>] [-o <org_name>] [-t <net_tag>] [-f <file_name>] 

Mandatory parameters:
    -m <mode>           Choose "export" or "import" to either export devices or import them
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, the script will look for one in
                        environment variable "MERAKI_DASHBOARD_API_KEY".
    -o <org_name>       The name of the organization you want to interact with. This can be omitted if your API key
                        only has access to a single organization
    -t <net_tag>        Only works with export mode. Limits the script to only export devices in networks
                        with a specific network tag
    -f <file_name>      The name of the file to export/import devices to/from. The parameters is mandatory
                        when using import mode. If omitted at export, "devices_<timestamp>.txt" will be used
                        
Example, export all devices in networks tagged "brazil" from organization "Big Industries Inc" into a file:
    python movedevices.py -m export -k 1234 -o "Big Industries Inc" -t brazil 
    
Example, import all devices from the default export file into organization "Big Industries Brazil":
    python movedevices.py -m import -k 1234 -o "Big Industries Brazil" -f devices_2022-01-24_16.53.57.txt
    
Note that you may need to wait several minutes between exporting devices and being able to import them into a
different organization, if the two organizations reside in different cloud shards.                        

You need to have Python 3 and the Requests module installed. You can download the module here: 
https://github.com/kennethreitz/requests or install it using pip:
    pip install requests"""

import sys, getopt, requests, os, datetime

import time

from urllib.parse import urlencode
from requests import Session, utils

def printhelp():
    #prints help text
    print(readMe)
    
def log(text, filePath=None):
    logString = "%s -- %s" % (datetime.datetime.now(), text)
    print(logString)
    if not filePath is None:
        try:
            with open(filePath, "a") as logFile:
                logFile.write("%s\n" % logString)
        except:
            log("ERROR: Unable to append to log file")
            
def killScript(reason=None):
    if reason is None:
        print(readMe)
        sys.exit()
    else:
        log("ERROR: %s" % reason)
        sys.exit()
        
def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get(API_KEY_ENV_VAR_NAME, None)   

class NoRebuildAuthSession(Session):
    def rebuild_auth(self, prepared_request, response):
        """
        This method is intentionally empty. Needed to prevent auth header stripping on redirect. More info:
        https://stackoverflow.com/questions/60358216/python-requests-post-request-dropping-authorization-header
        """

API_MAX_RETRIES             = 3
API_CONNECT_TIMEOUT         = 60
API_TRANSMIT_TIMEOUT        = 60
API_STATUS_RATE_LIMIT       = 429
API_RETRY_DEFAULT_WAIT      = 3

#Set to True or False to enable/disable console logging of sent API requests
FLAG_REQUEST_VERBOSE        = True

API_BASE_URL                = "https://api.meraki.com/api/v1"
API_KEY_ENV_VAR_NAME        = "MERAKI_DASHBOARD_API_KEY"

def merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders=None, p_queryItems=None, 
        p_requestBody=None, p_verbose=False, p_retry=0):
    #returns success, errors, responseHeaders, responseBody
    
    if p_retry > API_MAX_RETRIES:
        if(p_verbose):
            print("ERROR: Reached max retries")
        return False, None, None, None
        
    bearerString = "Bearer " + str(p_apiKey)
    headers = {"Authorization": bearerString}
    if not p_additionalHeaders is None:
        headers.update(p_additionalHeaders)
        
    query = ""
    if not p_queryItems is None:
        qArrayFix = {}
        for item in p_queryItems:
            if isinstance(p_queryItems[item], list):
                qArrayFix["%s[]" % item] = p_queryItems[item]
            else:
                qArrayFix[item] = p_queryItems[item]
        query = "?" + urlencode(qArrayFix, True)
    url = API_BASE_URL + p_endpoint + query
    
    verb = p_httpVerb.upper()
    
    session = NoRebuildAuthSession()
    
    verbs   = {
        'DELETE'    : { 'function': session.delete, 'hasBody': False },
        'GET'       : { 'function': session.get,    'hasBody': False },
        'POST'      : { 'function': session.post,   'hasBody': True  },
        'PUT'       : { 'function': session.put,    'hasBody': True  }
    }

    try:
        if(p_verbose):
            print(verb, url)
            
        if verb in verbs:
            if verbs[verb]['hasBody'] and not p_requestBody is None:
                r = verbs[verb]['function'](
                    url,
                    headers =   headers,
                    json    =   p_requestBody,
                    timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
                )
            else: 
                r = verbs[verb]['function'](
                    url,
                    headers =   headers,
                    timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
                )
        else:
            return False, None, None, None
    except:
        return False, None, None, None
    
    if(p_verbose):
        print(r.status_code)
    
    success         = r.status_code in range (200, 299)
    errors          = None
    responseHeaders = None
    responseBody    = None
    
    if r.status_code == API_STATUS_RATE_LIMIT:
        retryInterval = API_RETRY_DEFAULT_WAIT
        if "Retry-After" in r.headers:
            retryInterval = r.headers["Retry-After"]
        if "retry-after" in r.headers:
            retryInterval = r.headers["retry-after"]
        
        if(p_verbose):
            print("INFO: Hit max request rate. Retrying %s after %s seconds" % (p_retry+1, retryInterval))
        time.sleep(int(retryInterval))
        success, errors, responseHeaders, responseBody = merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders, 
            p_queryItems, p_requestBody, p_verbose, p_retry+1)
        return success, errors, responseHeaders, responseBody        
            
    try:
        rjson = r.json()
    except:
        rjson = None
        
    if not rjson is None:
        if "errors" in rjson:
            errors = rjson["errors"]
            if(p_verbose):
                print(errors)
        else:
            responseBody = rjson  

    if "Link" in r.headers:
        parsedLinks = utils.parse_header_links(r.headers["Link"])
        for link in parsedLinks:
            if link["rel"] == "next":
                if(p_verbose):
                    print("Next page:", link["url"])
                splitLink = link["url"].split("/api/v1")
                success, errors, responseHeaders, nextBody = merakiRequest(p_apiKey, p_httpVerb, splitLink[1], 
                    p_additionalHeaders=p_additionalHeaders, 
                    p_requestBody=p_requestBody, 
                    p_verbose=p_verbose)
                if success:
                    if not responseBody is None:
                        responseBody = responseBody + nextBody
                else:
                    responseBody = None
    
    return success, errors, responseHeaders, responseBody    
    
def getOrganizations(apiKey):
    url = "/organizations"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
def getOrganizationInventoryDevices(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/inventoryDevices"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
def claimNetworkDevices(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/devices/claim"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
def getOrganizationNetworks(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/networks"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
def removeNetworkDevices(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/devices/remove"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    

def fetchNetworkFromListById(networkList, networkId):
    for net in networkList:
        if net['id'] == networkId:
            return net
    return None
    
def fetchNetworkFromListByName(networkList, networkName):
    for net in networkList:
        if net['name'] == networkName:
            return net
    return None
    
def generateOutputFileName(argFile):
    if argFile is None:
        timestampIso = datetime.datetime.now().isoformat()[:19]
        timestampFileNameFriendly = timestampIso.replace(":",".").replace("T","_")
        name = "devices_" + timestampFileNameFriendly + ".txt"
        return name
    else:
        return argFile
        
        
def exportDevices(apiKey, organizationId, fileName, tag=None):
    log("Export mode selected. Net tag filter is %s. " % tag)
    if tag is None:
        log("WARNING: NO NET TAG DEFINED. WILL EXPORT ALL DEVICES. CONTINUING IN 10 SECONDS...\n")
        time.sleep(10)
        
    outputFile = generateOutputFileName(fileName)      
    log('Using file "%s"' % outputFile)
    try:
        f = open(outputFile, 'w')
        f.write("test")
        f.close()
    except:
        killScript('File "%s": Write test failed' % outputFile)
            
    success, errors, allNetworks = getOrganizationNetworks(apiKey, organizationId)
    if allNetworks is None:
        killScript('Unable to fetch organization network list')
        
    filteredNetworks = []
    for net in allNetworks:
        if tag is None or tag in net['tags']:
            filteredNetworks.append(net)
            
    success, errors, allDevices = getOrganizationInventoryDevices(apiKey, organizationId)
    if allDevices is None:
        killScript('Unable to fetch organization network list')
        
    filteredDevices = []
    for device in allDevices:
        if not fetchNetworkFromListById(filteredNetworks, device['networkId']) is None:
            filteredDevices.append(device)
            
    try:
        log('Writing devices to file "%s"...' % outputFile)
        f = open(outputFile, 'w')
        for device in filteredDevices:
            f.write("%s,%s\n" % (device['serial'], fetchNetworkFromListById(filteredNetworks, device['networkId'])['name']))
        f.close()
    except:
        killScript('File "%s": Write devices failed' % outputFile)
        
    log('File written')
    log('Removing devices from networks...')
    
    for device in filteredDevices:
        success, errors, response = removeNetworkDevices(apiKey, device['networkId'], body={'serial':device['serial']})
        if not success:
            log("WARNING: Unable to remove device with serial %s" % device['serial'])
            
            
def importDevices(apiKey, organizationId, fileName):
    log("Import mode selected")
    log('Using source file "%s"' % fileName)
    if fileName is None:
        killScript('Parameter "-f <file_name>" is mandatory for import mode')
        
    rawDeviceList = []
    try:
        file = open(fileName, "r")
        for line in file:
            rawDeviceList.append(line)
        file.close()
    except:
        killScript('Unable to open source file')
    
    deviceList = []
    try:
        for line in rawDeviceList:
            splitLine   = line.split(',')
            record      = {'serial': splitLine[0].strip(), 'networkName': splitLine[1].strip()}
            deviceList.append(record)
    except:
        killScript('Invalid source file format')
        
    success, errors, allNetworks = getOrganizationNetworks(apiKey, organizationId)
    if allNetworks is None:
        killScript('Unable to fetch organization network list')
        
    for device in deviceList:
        targetNetwork = fetchNetworkFromListByName(allNetworks, device['networkName'])    
        if not targetNetwork is None:
            success, errors, response = claimNetworkDevices(apiKey, targetNetwork['id'], body={'serials': [device['serial']]})
            if not success:
                log("WARNING: Unable to claim device with serial %s into network %s" % (device['serial'], targetNetwork['id']))
        else:
            log("WARNING: Skipping device with serial %s: No matching network" % device['serial'])
    
    
      
        
def main(argv):
    #set default values for command line arguments
    arg_apikey      = None
    arg_orgName     = None
    arg_mode        = None
    arg_filepath    = None
    arg_tag         = None
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:m:t:f:')
    except getopt.GetoptError:
        killScript()
    
    for opt, arg in opts:
        if opt == '-h':
            killScript()
        elif opt == '-k':
            arg_apikey = arg
        elif opt == '-o':
            arg_orgName = arg
        elif opt == '-m':
            arg_mode = arg
        elif opt == '-t':
            arg_tag = arg
        elif opt == '-f':
            arg_filepath = arg
            
    apiKey = getApiKey(arg_apikey)
    if apiKey is None:
        killScript()
        
    if not arg_mode in ['export', 'import']:
        killScript()
        
    success, errors, allOrgs = getOrganizations(apiKey)
    
    if allOrgs is None:
        killScript("Unable to fetch organizations for that API key")
    
    organizationId      = None
    organizationName    = ""
    
    if arg_orgName is None:
        if len(allOrgs) == 1:
            organizationId      = allOrgs[0]['id']
            organizationName    = allOrgs[0]['name']
        else:
            killScript("Organization name required for this API key")             
    else:
        for org in allOrgs:
            if org["name"] == arg_orgName:
                organizationId      = org['id']
                organizationName    = org['name']
                break
    if organizationId is None:
        killScript("No matching organizations")
        
    log('Using organization %s "%s"' % (organizationId, organizationName))
    
    if arg_mode == "export":
        exportDevices(apiKey, organizationId, arg_filepath, arg_tag)
    elif arg_mode == "import":
        importDevices(apiKey, organizationId, arg_filepath)
        
    log("End of script.")
            
if __name__ == '__main__':
    main(sys.argv[1:])