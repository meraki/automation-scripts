readMe = """This is a script to count how many and what type of Meraki Insight licenses would
be required to fully cover all the MX and Z-series appliances used in networks in an organization.

Script syntax, Windows:
    python mi_bom_tool.py -k <api_key> [-o <org_name>] [-i <net_tag>] [-e <net_tag>]
 
Script syntax, Linux and Mac:
    python3 mi_bom_tool.py -k <api_key> [-o <org_name>] [-i <net_tag>] [-e <net_tag>]
    
Mandatory parameters:
    -k <api_key>    Your Meraki Dashboard API key
    -o <org_name>   If your Meraki Dashboard API key has access to multiple
                    organizations, you will need to specify the name of the
                    organization to be processed. This can be omitted for
                    keys with access to a single organization only
    
Optional parameters:
    -i <net_tag>    "Include" filter. Only process networks WITH specified network tag
    -e <net_tag>    "Exclude" filter. Only process networks WITHOUT specified tag
    
Note: parameters "-i" and "-i" are incmpatible with each other.
                            
Example count all Insight licenses needed for networks tagged "sales-office" in organization
"Big Industries Inc":
    python mi_bom_tool.py -k 1234 -o "Big Industries Inc" -i sales-office
    
Required Python 3 modules:
    requests
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""


import sys, getopt, time, datetime, yaml, re

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
        retryInterval = 2
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
    endpoint = "/organizations"
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getOrganizationInventoryDevices(apiKey, organizationId):
    endpoint = "/organizations/%s/inventoryDevices" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getOrganizationNetworks(apiKey, organizationId):
    endpoint = "/organizations/%s/networks" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
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
        

def findNetworkWithId(netId, netList):
    for net in netList:
        if net["id"] == netId:
            return net
    return None


def findApplianceForNetworkId(netId, applianceList):
    for appliance in applianceList:
        if appliance["networkId"] == netId:
            return appliance
    return None
    
    
def findLicenseForModel(model):
    if model.startswith("Z"):
        return "MI-XS"
    if model.startswith("MX6"):
        return "MI-S"
    if model.startswith("MX7") or model.startswith("MX8") or model.startswith("MX9") or model.startswith("MX10"):
        return "MI-M"
    if model.startswith("MX250"):
        return "MI-L"
    if model.startswith("MX450"):
        return "MI-XL"
    return None
    
                                      
    
def main(argv):    
    arg_apiKey      = None
    arg_orgName     = None
    arg_includeTag  = None
    arg_excludeTag  = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:i:e:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-o':
            arg_orgName     = str(arg)
        if opt == '-i':
            arg_includeTag  = str(arg)
        if opt == '-e':
            arg_excludeTag  = str(arg)
            
    if arg_apiKey is None:
        killScript()      

    if (not arg_includeTag is None) and (not arg_excludeTag is None):
        killScript("Include and Exclude tag filters cannot be used at the same time")
        
    success, errors, headers, organizations = getOrganizations(arg_apiKey)
    
    if organizations is None:
        killScript("Unable to fetch organizations for that API key")
    
    organizationId      = None
    organizationName    = None
    
    if len(organizations) == 1 and arg_orgName is None:
        organizationId      = organizations[0]["id"]
        organizationName    = organizations[0]["name"]
    
    for org in organizations:
        if org['name'] == arg_orgName:
            organizationId = org['id']
            organizationName = org['name']
            break
            
    if organizationId is None:
        killScript("No organization found with that name")
                                        
    success, errors, headers, allNetworks = getOrganizationNetworks(arg_apiKey, organizationId)
    
    if allNetworks is None:
        killScript("Unable to fetch networks for that organization")
        
        
    networks = []
        
    for net in allNetworks:
        if "appliance" in net["productTypes"]:
            networkIsInScope = True
            if (not arg_includeTag is None) and (not (arg_includeTag in net["tags"])):
                networkIsInScope = False
                
            if (not arg_excludeTag is None) and (arg_excludeTag in net["tags"]):
                networkIsInScope = False
            
            if networkIsInScope:
                networks.append(net)
                               
    success, errors, headers, allDevices = getOrganizationInventoryDevices(arg_apiKey, organizationId)
    
    if allDevices is None:
        killScript("Unable to fetch devices for that organization")
        
    appliances = []
    
    for device in allDevices:
        if not device["networkId"] is None and (device["model"].startswith("MX") or device["model"].startswith("Z")):
            if not findNetworkWithId(device["networkId"], networks) is None:
                appliances.append(device)
    
    counters = {
        "MI-XS" : 0,
        "MI-S"  : 0,
        "MI-M"  : 0,
        "MI-L"  : 0,
        "MI-XL" : 0
    }
    
    # looping networks and not appliances to eliminate HA pair duplicates more easily
    for net in networks:
        appliance = findApplianceForNetworkId(net["id"], appliances)
        if not appliance is None:
            licenseType = findLicenseForModel(appliance["model"])
            if licenseType is None:
                log("WARNING: Unsupported security appliance model. Results may be inaccurate")
            else:
                counters[licenseType] += 1
                
    print('\nTotal MI license capacity needed for networks in scope:\n')
    
    for size in counters:
        if counters[size] > 0:
            print("%-6s: %s" % (size, counters[size]))
    
if __name__ == '__main__':
    main(sys.argv[1:])
