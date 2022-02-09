readMe = '''This is a script to list the inventory of a specific organization or all organizations
 accessible by an administrator to a CSV file.
 
Syntax, Windows:
 python inventorycsv.py -k [<api key>] [-o <org name>] [-f <file path>]
 
Syntax, Linux and Mac:
 python3 inventorycsv.py -k [<api key>] [-o <org name>] [-f <file path>]
 
Optional parameters:
 -k <api key>       Your Meraki Dashboard API key. Requires org-level privilege. If omitted, script
                    looks for an API key in OS environment variable "MERAKI_DASHBOARD_API_KEY"
 -o <org name>      The name of the organization to list inventory for. Omit or use "/all" for all 
 -f <file path>     The file name or path of the file to be used for output. If omitted, default
                     is file name "inventory_[timestamp].csv" in the current directory. Use
                     "/print" to display on the monitor instead.
                     
Examples:
    python inventorycsv.py -k 1234
    python inventorycsv.py -k 1234 -o "Big Industries Inc" -f /print
    
Required Python 3 modules:
 Requests     : http://docs.python-requests.org
  
 After installing Python, you can install these additional modules using pip with the following commands:
    pip install requests   

Notes:
 * Depending on your operating system, the commands for python and pip may be "python3" and "pip3" instead
 * Use double quotes to enter names containing spaces in the Windows command line    
'''

import sys, getopt, requests, time, datetime, os

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


### SECTION: FUNCTIONS FOR MERAKI DASHBOARD COMMUNICATION


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
    
# getOrganizationInventoryDevices
#
# Description: Return the device inventory for an organization
# Endpoint: GET /organizations/{organizationId}/inventoryDevices
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-inventory-devices
#
# Query parameters:
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 1000. Default is 1000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     usedState: String. Filter results by used or unused inventory. Accepted values are "used" or "unused".
#     search: String. Search for devices in inventory based on serial number, mac address, or model.
#     macs: Array. Search for devices in inventory based on mac addresses.
#     networkIds: Array. Search for devices in inventory based on network ids.
#     serials: Array. Search for devices in inventory based on serials.
#     models: Array. Search for devices in inventory based on model.
#     tags: Array. An optional parameter to filter devices by tags. The filtering is case-sensitive. If tags are included, 'tagsFilterType' should also be included (see below).
#     tagsFilterType: String. An optional parameter of value 'withAnyTags' or 'withAllTags' to indicate whether to return devices which contain ANY or ALL of the included tags. If no type is included, 'withAnyTags' will be selected.
#     productTypes: Array. Optional parameter to filter devices by product type. Valid types are wireless, appliance, switch, systemsManager, camera, cellularGateway, and sensor.

def getOrganizationInventoryDevices(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/inventoryDevices"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getOrganizationDevicesStatuses
#
# Description: List the status of every Meraki device in the organization
# Endpoint: GET /organizations/{organizationId}/devices/statuses
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-devices-statuses
#
# Query parameters:
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 1000. Default is 1000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     networkIds: Array. Optional parameter to filter devices by network ids.
#     serials: Array. Optional parameter to filter devices by serials.
#     statuses: Array. Optional parameter to filter devices by statuses. Valid statuses are ["online", "alerting", "offline", "dormant"].
#     productTypes: Array. An optional parameter to filter device statuses by product type. Valid types are wireless, appliance, switch, systemsManager, camera, cellularGateway, and sensor.
#     powerSuppliesStatuses: Array. An optional parameter to filter power supply by status. Valid types are disconnected, connected, powered, available, powering and standby
#     models: Array. Optional parameter to filter devices by models.
#     tags: Array. An optional parameter to filter devices by tags. The filtering is case-sensitive. If tags are included, 'tagsFilterType' should also be included (see below).
#     tagsFilterType: String. An optional parameter of value 'withAnyTags' or 'withAllTags' to indicate whether to return devices which contain ANY or ALL of the included tags. If no type is included, 'withAnyTags' will be selected.
#     configurationUpdatedAfter: String. Optional parameter to filter results by whether or not the device's configuration has been updated after the given timestamp
#     useMtunData: Boolean. Use mtun data for device statuses. This is less accurate, but quicker. This should only be used on selective Dashboard pages.

def getOrganizationDevicesStatuses(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/devices/statuses"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response


### SECTION: GENERAL USE FUNCTIONS


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

def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get(API_KEY_ENV_VAR_NAME, None)

def generateFileName():
    timestamp = '{:%Y-%m-%d_%H.%M.%S}'.format(datetime.datetime.now())
    return 'inventory_' + timestamp + '.csv'

    
### SECTION: MAIN


def main(argv):    
    #set default values for command line arguments
    arg_apikey          = None
    arg_orgname         = "/all"
    arg_file            = None
    
    try:
        opts, args = getopt.getopt(argv, 'hk:o:f:')
    except getopt.GetoptError:
        killScript()
    
    for opt, arg in opts:
        if opt == '-h':
            printHelpAndExit()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-o':
            arg_orgname = arg
        elif opt == '-f':
            arg_file    = arg
            
    #check if all required parameters have been given
    apiKey = getApiKey(arg_apikey)
    if apiKey is None:
        killScript()
        
    flag_printToScreen  =       arg_file    == "/print"
    flag_useDefaultFile =      (arg_file    is None    )
    
    success, errors, response = getOrganizations(apiKey)
    if response is None:
        killScript("Unable to fetch organizations")

    organizations = []
    for org in response:
        if arg_orgname == "/all" or org['name'] == arg_orgname:
            organizations.append(org)

    if len(organizations) == 0:
        killScript("No matching organizations")
        
    for org in organizations:
        org["inventory"] = []
        success, errors, inventory = getOrganizationInventoryDevices(apiKey, org['id'])
        if inventory is None:
            continue
            
        success, errors, networks = getOrganizationNetworks(apiKey, org['id'])
        
        success, errors, statuses = getOrganizationDevicesStatuses(apiKey, org['id'])
        
        for device in inventory:
            device["networkName"]       = ""
            device["networkTags"]       = []
            if not networks is None:
                if not device["networkId"] is None:
                     for net in networks:
                        if net["id"] == device["networkId"]:
                            device["networkName"] = net["name"]
                            if not net["tags"] is None:
                                device["networkTags"] = net["tags"]
                            break
                            
            device["status"]            = ""
            device["lastReportedAt"]    = ""
            device["publicIp"]          = ""
            device["lanIp"]             = ""
            device["wan1Ip"]            = ""
            device["wan2Ip"]            = ""
            device["tags"]              = []
            
            if not statuses is None:
                for statDevice in statuses:
                    if device['serial'] == statDevice['serial']:
                        if "status" in statDevice and not statDevice["status"] is None:
                            device["status"] = statDevice['status']
                        if "lastReportedAt" in statDevice and not statDevice["lastReportedAt"] is None:
                            device["lastReportedAt"] = statDevice['lastReportedAt']
                        if "publicIp" in statDevice and not statDevice["publicIp"] is None:
                            device["publicIp"] = statDevice['publicIp']
                        if "lanIp" in statDevice and not statDevice["lanIp"] is None:
                            device["lanIp"] = statDevice['lanIp']
                        if "wan1Ip" in statDevice and not statDevice["wan1Ip"] is None:
                            device["wan1Ip"] = statDevice['wan1Ip']
                        if "wan2Ip" in statDevice and not statDevice["wan2Ip"] is None:
                            device["wan2Ip"] = statDevice['wan2Ip']
                        if "tags" in statDevice and not statDevice["tags"] is None:
                            device["tags"] = statDevice['tags']
                        
            org["inventory"].append(device)
                    
    #print tree structure to desired output destination
    
    if flag_printToScreen:
        for org in organizations:
            if not org["inventory"] is None and len(org["inventory"]) > 0:
                print('\nInventory for organization: %s' % org["name"])
                print( "%-20s %-12s %-32s %-8s %s" % ("Serial", "Model", "Device name", "Status", "Network name") )
                for device in org["inventory"]:
                    print( "%-20s %-12s %-32s %-8s %s" % (device["serial"],device["model"], device["name"], device["status"], device["networkName"]) )
    else:
        if flag_useDefaultFile:
            filepath = generateFileName()
        else:
            filepath = arg_file
            
        print('Writing file "%s"...' % filepath)
        
        headers = [
            "serial",
            "model",
            "name",
            "mac",
            "productType",
            "status",
            "lanIp",
            "wan1Ip",
            "wan2Ip",
            "publicIp",
            "lastReportedAt",
            "deviceTags",
            "organizationId",
            "organizationName",
            "networkId",
            "networkName",
            "networkTags",
            "orderNumber",
            "claimedAt"
        ]
        
        try:
            f = open(filepath, 'w')
            f.write("%s\n" % ",".join(headers))
        except:
            killScript("Unable to open file for writing")
            
        for org in organizations:
            if not org["inventory"] is None:
                for device in org["inventory"]:
                    strDevice = {}
                    for key in device:
                        if device[key] is None:
                            strDevice[key] = ""
                        elif isinstance(device[key], list):
                            strDevice[key] = " ".join(device[key])
                        else:
                            strDevice[key] = str(device[key])
                  
                    elements = [
                        strDevice["serial"],
                        strDevice["model"],
                        strDevice["name"],
                        strDevice["mac"],
                        strDevice["productType"],
                        strDevice["status"],
                        strDevice["lanIp"],
                        strDevice["wan1Ip"],
                        strDevice["wan2Ip"],
                        strDevice["publicIp"],
                        strDevice["lastReportedAt"],
                        strDevice["tags"],
                        str(org["id"]),
                        org["name"],
                        strDevice['networkId'],
                        strDevice["networkName"],
                        strDevice['networkTags'],
                        strDevice["orderNumber"],
                        strDevice["claimedAt"]
                    ]
                        
                    line = ','.join(elements)
                    try:
                        f.write(line + '\n')
                    except:
                        killScript(" Unable to write to file")
                        
        try:
            f.close()
        except:
            killScript ('Unable to close file')
        
    print('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])
