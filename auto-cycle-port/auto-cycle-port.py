readMe = """Python 3 script that auto-cycles a switch port if a particular device in
the same network is unreachable. For example, if a MG21 is unreachable, it cycles the
PoE port it is connected to.

Requires a YAML configuration file. You can find an example of such a file here:
https://github.com/meraki/automation-scripts/tree/master/auto-cycle-port

Script syntax:
    python auto-cycle-port.py -c <config_file>

Required Python 3 modules:
    requests
    pyyaml
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    pip install pyyaml
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""

import sys, getopt, yaml, time, datetime

from urllib.parse import urlencode
from requests import Session, utils

class NoRebuildAuthSession(Session):
    def rebuild_auth(self, prepared_request, response):
        """
        This method is intentionally empty. Needed to prevent auth header stripping on redirect. More info:
        https://stackoverflow.com/questions/60358216/python-requests-post-request-dropping-authorization-header
        """

API_MAX_RETRIES         = 3
API_CONNECT_TIMEOUT     = 60
API_TRANSMIT_TIMEOUT    = 60
API_STATUS_RATE_LIMIT   = 429

#Set to True or False to enable/disable console logging of sent API requests
FLAG_REQUEST_VERBOSE    = True

API_BASE_URL            = "https://api.meraki.com/api/v1"


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
        query = "?" + urlencode(p_queryItems, True)
    url = API_BASE_URL + p_endpoint + query
    
    verb = p_httpVerb.upper()
    
    session = NoRebuildAuthSession()

    try:
        if(p_verbose):
            print(verb, url)
        if verb == "GET":
            r = session.get(
                url,
                headers =   headers,
                timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
            )
        elif verb == "PUT":
            if not p_requestBody is None:
                if (p_verbose):
                    print("body", p_requestBody)
                r = session.put(
                    url,
                    headers =   headers,
                    json    =   p_requestBody,
                    timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
                )
        elif verb == "POST":
            if not p_requestBody is None:
                if (p_verbose):
                    print("body", p_requestBody)
                r = session.post(
                    url,
                    headers =   headers,
                    json    =   p_requestBody,
                    timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
                )
        elif verb == "DELETE":
            r = session.delete(
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
        if(p_verbose):
            print("INFO: Hit max request rate. Retrying %s after %s seconds" % (p_retry+1, r.headers["Retry-After"]))
        time.sleep(int(r.headers["Retry-After"]))
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
  

def getOrganizations(p_apiKey):
    endpoint = "/organizations"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
def getOrganizationDevicesStatuses(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/devices/statuses" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
def getOrganizationInventoryDevices(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/inventoryDevices" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response

def cycleDeviceSwitchPorts(p_apiKey, p_serial, p_portNumber):
    endpoint = "/devices/%s/switch/ports/cycle" % p_serial
    body = { "ports": [str(p_portNumber)]}
    success, errors, headers, response = merakiRequest(p_apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response

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


def loadConfig(filePath):
    log("Loading %s" % filePath)
    
    config = None

    try:
        with open(filePath) as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
    except:
        return None

    return config


def performScan(config):
    log("Initiating scan")  
    
    success, errors, headers, deviceStatuses = getOrganizationDevicesStatuses(config['apiKey'], config['organizationId'])
    
    if deviceStatuses is None:
        return False
        
    success, errors, headers, inventoryDevices = getOrganizationInventoryDevices(config['apiKey'], config['organizationId'])
        
    if inventoryDevices is None:
        return False
        
    for device in deviceStatuses:
        model = None
        for invDevice in inventoryDevices:
            if device['serial'] == invDevice['serial']:
                model = invDevice['model']
                break
            
        if not model is None:
            if model == config['trackedDeviceModel']:
                if device['status'] != 'online':
                    log("Device %s is not online!" % device['serial'], config["logFilePath"])
                    switchSerial = None
                    for invDevice in inventoryDevices:
                        if invDevice['model'].startswith("MS") and (invDevice["networkId"] == device["networkId"]):
                            switchSerial = invDevice['serial']
                            log("Cycling port %s on switch %s" % (config['targetPortNumber'], switchSerial), config["logFilePath"])
                            cycleDeviceSwitchPorts(config['apiKey'], switchSerial, config['targetPortNumber'])
                            break
                            
    
    
def main(argv):    
    argConfigFile = None
    
    try:
        opts, args = getopt.getopt(argv, 'c:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-c':
            argConfigFile = arg
            
    if argConfigFile is None:
        killScript()
    
    try:
        config = loadConfig(argConfigFile)
        print(str(datetime.datetime.now()) + " -- Initializing script")
    except:
        killScript()
        
    success, errors, headers, organizations = getOrganizations(config['apiKey'])
    
    if organizations is None:
        killScript("Unable to fetch organizations for that API key")
    
    config['organizationId'] = None
    for org in organizations:
        if org['name'] == config['organizationName']:
            config['organizationId'] = org['id']
            break
            
    if config['organizationId'] is None:
        killScript("No organization found with that name")
                
    while(True):
        performScan(config)
        print(str(datetime.datetime.now()) + " -- Next scan in " + str(config['scanIntervalMinutes']) + " minutes")
        time.sleep(config['scanIntervalMinutes']*60)    
    
if __name__ == '__main__':
    main(sys.argv[1:])
