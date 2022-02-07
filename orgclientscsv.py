readMe = '''This is a script to create a CSV file with all of the client devices in an organization. 
 The CSV file will be created in the same folder where this script is located. The script makes no attempt 
 to remove or combine duplicate entries. If you see the same client being reported several times, this is
 typically an indication of a client that has been moving.

Usage:
 python orgclientcsv.py [-k <api key>] [-o <org name>]

Parameters:
  -k <api key>          :   Optional. Your Meraki Dashboard API key. If omitted, the script will look for a key in
                            OS environment variable "MERAKI_DASHBOARD_API_KEY"
  -o <org name>         :   Optional. Name of the organization you want to process. Use keyword "/all" to explicitly
                            specify all orgs. Default is "/all"

Example:
  python orgclientcsv.py -k 1234 -o "Big Industries Inc" 

Notes:
 * In Windows, use double quotes ("") to enter command line parameters containing spaces.
 * This script was built for Python 3.7.1.
 * Depending on your operating system, the command to start python can be either "python" or "python3". 

Required Python modules:
  Requests     : http://docs.python-requests.org
After installing Python, you can install these additional modules using pip with the following commands:
  pip install requests

Depending on your operating system, the command can be "pip3" instead of "pip".'''

#ADD MAC OUIS IN THIS LIST TO IGNORE DEVICES SPECIFIC VENDORS, LIKE NETWORK DEVICES
MAC_OUI_IGNORE_LIST     = []


import time, sys, getopt, os, datetime

from urllib.parse import urlencode
from requests import Session, utils

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
    
# getOrganizations
#
# Description: List the organizations that the user has privileges on
# Endpoint: GET /organizations
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organizations

def getOrganizations(apiKey):
    url = "/organizations"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getOrganizationNetworks
#
# Description: List the networks that the user has privileges on in an organization
# Endpoint: GET /organizations/{organizationId}/networks
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-networks
#
# Query parameters:
#     configTemplateId: String. An optional parameter that is the ID of a config template. Will return all networks bound to that template.
#     tags: Array. An optional parameter to filter networks by tags. The filtering is case-sensitive. If tags are included, 'tagsFilterType' should also be included (see below).
#     tagsFilterType: String. An optional parameter of value 'withAnyTags' or 'withAllTags' to indicate whether to return networks which contain ANY or ALL of the included tags. If no type is included, 'withAnyTags' will be selected.
#     productTypes: Array. An optional parameter to filter networks by product type. Results will have at least one of the included product types.
#     hasOrgAdminVideoAccess: Boolean. An optional parameter, when true, only the networks in which organization admins have video access to will be returned.
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 100000. Default is 1000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.

def getOrganizationNetworks(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/networks"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkClients
#
# Description: List the clients that have used this network in the timespan
# Endpoint: GET /networks/{networkId}/clients
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-clients
#
# Query parameters:
#     t0: String. The beginning of the timespan for the data. The maximum lookback period is 31 days from today.
#     timespan: Number. The timespan for which the information will be fetched. If specifying timespan, do not specify parameter t0. The value must be in seconds and be less than or equal to 31 days. The default is 1 day.
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 1000. Default is 10.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     statuses: Array. Filters clients based on status. Can be one of 'Online' or 'Offline'.
#     ip: String. Filters clients based on a partial or full match for the ip address field.
#     ip6: String. Filters clients based on a partial or full match for the ip6 address field.
#     ip6Local: String. Filters clients based on a partial or full match for the ip6Local address field.
#     mac: String. Filters clients based on a partial or full match for the mac address field.
#     os: String. Filters clients based on a partial or full match for the os (operating system) field.
#     description: String. Filters clients based on a partial or full match for the description field.
#     vlan: String. Filters clients based on the full match for the VLAN field.
#     recentDeviceConnections: Array. Filters clients based on recent connection type. Can be one of 'Wired' or 'Wireless'.
#     clientTypes: Array. Filter clients based on their type. Can be one of 'clientVpn'.

def getNetworkClients(apiKey, networkId, query=None):
    url = "/networks/" + str(networkId) + "/clients"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response


def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get(API_KEY_ENV_VAR_NAME, None)  
    
def log(text, filePath=None):
    logString = "%s -- %s" % (str(datetime.datetime.now())[:19], text)
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
    
def printhelp():
    print(readMe) 
    
    
def main(argv):
    #set default values for command line arguments
    arg_apikey  = None
    arg_org     = '/all'
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:')
    except getopt.GetoptError:
        killScript()
    
    for opt, arg in opts:
        if   opt == '-h':
            killScript()
        elif opt == '-k':
            arg_apikey  = str(arg)
        elif opt == '-o':
            arg_org     = arg
            
    apiKey = getApiKey(arg_apikey)
    if apiKey is None:
        killScript()
        
    success, errors, rawOrganizations = getOrganizations(apiKey)
    if rawOrganizations is None:
        killScript("Unable to fetch organizations' list")
        
    organizations = []
    
    for org in rawOrganizations:
        if arg_org == '/all' or org['name'] == arg_org:
            organizations.append(org)
            
    outputBuffer = []
                
    for org in organizations:
        success, errors, networks = getOrganizationNetworks(apiKey, org['id'])
        
        if networks is None:
            continue
        
        for net in networks:
            success, errors, networkClients = getNetworkClients(apiKey, net['id'], query={'timespan': 2678400})
            if networkClients is None:
                continue
                
            for client in networkClients:
                record = [
                    org['name'],
                    org['id'],
                    net['name'],
                    net['id'],
                    client['description'],
                    client['id'],
                    client['mac'],
                    client['ip'],
                    client['ip6'],
                    client['ip6Local'],
                    client['user'],
                    client['firstSeen'],
                    client['lastSeen'],
                    client['manufacturer'],
                    client['os'],
                    client['deviceTypePrediction'],
                    client['recentDeviceSerial'],
                    client['recentDeviceName'],
                    client['recentDeviceMac'],
                    client['recentDeviceConnection'],
                    client['ssid'],
                    client['vlan'],
                    client['switchport'],
                    int(client['usage']['sent']),
                    int(client['usage']['recv']),
                    int(client['usage']['total']),
                    client['status'],
                    client['notes'],
                    client['smInstalled'],
                    client['groupPolicy8021x'],
                    client['adaptivePolicyGroup']
                ]
                
                strRecord = []
                
                for item in record:
                    if item is None:
                        strRecord.append ("")
                    else:
                        strRecord.append(str(item))
                        
                outputBuffer.append(",".join(strRecord) )
            
    if len(outputBuffer) == 0:
        killScript('No clients in scope')
    
    csvHeader   = ','.join([
                        "organizationName",
                        "organizationId",
                        "networkName",
                        "networkId",
                        "clientDescription",
                        "clientId",
                        "clientMac",
                        "clientIpv4Address",
                        "clientIpv6Address",
                        "clientIpv6LocalAddress",
                        "user",
                        "firstSeen",
                        "lastSeen",
                        "manufacturer",
                        "os",
                        "deviceTypePrediction",
                        "lastConnectedNetworkDeviceSerial",
                        "lastConnectedNetworkDeviceName",
                        "lastConnectedNetworkDeviceMac",
                        "lastConnectedNetworkConnectionType",
                        "ssid",
                        "vlan",
                        "switchport",
                        "usageSentKBytes",
                        "usageRecvKBytes",
                        "usageTotalKBytes",
                        "status",
                        "notes",
                        "systemsManagerInstalled",
                        "groupPolicy8021x",
                        "adaptivePolicyGroup"
                    ])
    
    reportFileName = 'clients_' + '{:%Y-%m-%d_%H.%M.%S}'.format(datetime.datetime.now())[:19] + '.csv'
    
    log('Writing output to file "%s"...' % reportFileName)
    
    try:
        f = open(reportFileName, 'w')
        f.write("%s\n" % csvHeader)
    except:
        killScript("Unable to open file for writing")
    for line in outputBuffer:
        try:
            f.write("%s\n" % line)            
        except:
            killScript("Write failed")
    try:
        f.close()
    except:
        killScript("Failed to close file")
    
    log('End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])
