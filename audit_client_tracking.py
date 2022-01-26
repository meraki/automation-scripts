readMe = """This is a Python 3 script to verify if the MX client tracking setting on a set of
networks have a client tracking setting different than the one required.

Script syntax, Windows:
    python audit_client_tracking.py -m <tracking_mode> [-k <api_key>] [-o <org_name>] [-t <net_tag>]

Script syntax, Linux and Mac:
    python3 audit_client_tracking.py -m <tracking_mode> [-k <api_key>] [-o <org_name>] [-t <net_tag>]

Mandatory parameters:
    -m <mode>           Valid options:
                            "IP address"
                            "MAC address"
                            "Unique client identifier"
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, the script will look for one in
                        environment variable "MERAKI_DASHBOARD_API_KEY".
    -o <org_name>       The name of the organization you want to interact with. This can be omitted if your API key
                        only has access to a single organization
    -t <net_tag>        If defined, networks must have a matching network tag to be processed. Default is all
                        
                 
Example, verify if any networks tagged "Brazil" in organization "Big Industries Inc" have client tracking mode 
other than "MAC address":
    python audit_client_tracking.py -m "MAC address" -k 1234 -o "Big Industries Inc" -t Brazil                       

You need to have Python 3 and the Requests module installed. You can install the module via PIP 
with the following command:
    pip install requests

"""

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
    
def getOrganizationNetworks(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/networks"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceSettings
#
# Description: Return the appliance settings for a network
# Endpoint: GET /networks/{networkId}/appliance/settings
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-settings

def getNetworkApplianceSettings(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/settings"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
      
        
def main(argv):
    #set default values for command line arguments
    arg_apikey      = None
    arg_orgName     = None
    arg_mode        = None
    arg_tag         = None
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:m:t:')
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
            
    apiKey = getApiKey(arg_apikey)
    if apiKey is None:
        killScript()
        
    if not arg_mode in ['MAC address', 'IP address', 'Unique client identifier']:
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
    
    success, errors, allNetworks = getOrganizationNetworks(apiKey, organizationId)
    if allNetworks is None:
        killScript("Unable to fetch networks")
    
    filteredNetworks = []
    for net in allNetworks:
        if arg_tag is None or arg_tag in net['tags']:
            if 'appliance' in net['productTypes']:
                success, errors, response = getNetworkApplianceSettings(apiKey, net['id'])
                if not success:
                    log('WARNING: Unable to get tracking mode for net %s "%s"' % (net['id'], net['name']))
                elif not response is None:
                    if 'clientTrackingMethod' in response and response['clientTrackingMethod'] != arg_mode:
                        log('POLICY VIOLATION: Network %s "%s" is set to mode "%s"' % (net['id'], net['name'], response['clientTrackingMethod']))
        
    log("End of script.")
            
if __name__ == '__main__':
    main(sys.argv[1:])