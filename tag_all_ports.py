readMe = """Python 3 script that tags all MS switchports in an organization 
with a user-defined tag.

Script syntax, Windows:
    python tag_all_ports.py -k <api_key> [-o <org_name>] [-f <filter>] -t <tag>
 
Script syntax, Linux and Mac:
    python3 tag_all_ports.py -k <api_key> [-o <org_name>] [-f <filter>] -t <tag>
    
Mandatory parameters:
    -k <api_key>            Your Meraki Dashboard API key
    -t <tag>                Tag to be added to the switchport
    
Optional parameters:
    -o <org_name>           If multiple organizations are accessible by your
                            API key, you need to provide the name of the one
                            to apply the changes to
    -f <filter>             Filter ports by attribute. Filter must be entered in
                            form "<key>:<value>"
                            
Example, tag all access ports in the only organization I have access to with "video":
    python tag_all_ports.py -k 1234 -f type:access -t video
    
For examples of valid key filters that can be used, please read: 
    https://developer.cisco.com/meraki/api-v1/#!get-device-switch-ports

Required Python 3 modules:
    requests
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""

import sys, getopt, time, datetime

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
        
def getOrganizationInventoryDevices(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/inventoryDevices" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response

def getDeviceSwitchPorts(p_apiKey, p_serial):
    endpoint = "/devices/%s/switch/ports" % p_serial
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
def updateDeviceSwitchPort(p_apiKey, p_serial, p_portNumber, p_body):
    endpoint = "/devices/%s/switch/ports/%s" % (p_serial, p_portNumber)
    body = p_body
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
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
                            
    
    
def main(argv):    
    arg_apiKey  = None
    arg_orgName = None
    arg_tag     = None
    arg_filter  = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:t:f:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey  = str(arg)
        if opt == '-o':
            arg_orgName = str(arg)
        if opt == '-t':
            arg_tag     = str(arg)
        if opt == '-f':
            arg_filter  = str(arg)
            
    if arg_apiKey is None or arg_tag is None:
        killScript()
            
    success, errors, headers, organizations = getOrganizations(arg_apiKey)
    
    if organizations is None:
        killScript("Unable to fetch organizations for that API key")
    
    if len(organizations) == 1:
        organizationId = organizations[0]['id']
    else:
        if arg_orgName is None:
            killScript("API key has access to multiple organizations. Please use parameter -o <org_name>")
        
        organizationId      = None
        organizationName    = None
        
        for org in organizations:
            if org['name'] == arg_orgName:
                organizationId = org['id']
                organizationName = org['name']
                break
                
        if organizationId is None:
            killScript("No organization found with that name")
    
    success, errors, headers, inventory = getOrganizationInventoryDevices(arg_apiKey, organizationId)
    
    if inventory is None:
        killScript('Unable to fetch inventory for org %s "%s"' % (organizationId, organizationName))
        
    filter = None
    if not arg_filter is None:
        splitStr = arg_filter.split(":")
        if len(splitStr) > 1:
            filter = {splitStr[0]: splitStr[1]}
        else:
            killScript("Invalid port attribute filter")
    
    for device in inventory:
        if device['model'][:2] == "MS" and not device['networkId'] is None:
            log("Processing device %s" % device['serial']) 
            success, errors, headers, ports = getDeviceSwitchPorts(arg_apiKey, device['serial'])
            if ports is None:
                log("Error fetching port info")
            else:
                for port in ports:
                    flag_portMatchesFilter = False
                    if filter is None:
                        flag_portMatchesFilter = True
                    else:
                        for key in filter:
                            if key in port:
                                if port[key] == filter[key]:                    
                                    flag_tagExists = False
                                    for tag in port['tags']:
                                        if tag == arg_tag:
                                            flag_tagExists = True
                                            break
                                    if not flag_tagExists:
                                        newTags = []
                                        for tag in port['tags']:
                                            newTags.append(tag)
                                        newTags.append(arg_tag)
                                        
                                        requestBody = {'tags': newTags}                        
                                        success, errors, headers, result = updateDeviceSwitchPort(arg_apiKey, device['serial'], port['portId'], requestBody)
    
if __name__ == '__main__':
    main(sys.argv[1:])
