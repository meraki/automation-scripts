readMe = '''
Exports CSV of all in-use devices claimed after a specific date. Can include info
for one or more organizations. The script works by fetching the devices in the inventory
of the organizations being processed and creates a report for those that match the following
criteria:
    * They are part of a network
    * Their claim date is equal or later than the start date parameter
    * Their claim date is equal or earlier than the end date parameter (if defined)
    
Note that the script assumes all organizations in scope have unique names.

Syntax, Windows:
    python latest_devices.py [-k <api_key>] -o <org_name> -s <start_date> [-e <end_date>]
    
Syntax, Linux and Mac:
    python3 latest_devices.py [-k <api_key>] -o <org_name> -s <start_date> [-e <end_date>]
    
Mandatory parameters:
    -s <start_date>     The start date of the reporting period. Must be in ISO format (eg. 2023-03-02)
                        
    -o <org_name>       The name of the organization you want to run the report for, or one of the
                        following keywords:
                            /all        Run report for all organizations
                            /ea         Run report for all EA-enabled organizations. EA-organizations
                                        are detected by checking if they have exactly 10000 MR licenses
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, one will be loaded from
                        environment variable MERAKI_DASHBOARD_API_KEY
                        
    -e <end_date>       The end date of the reporting period. If omitted, the present date will be used
    
The CSV file exported will have the following name format:
    devices_s_<start_date>_e_<end_date>_ts_<timestamp>.csv

Example:
    Create CSV with all devices added into EA organizations since 1 January 2022:
        python latest_devices.py -k 1234 -o /ea -s 2022-01-01
    
Required packages:
    requests
    
To install required packages enter the following commands:

Windows:
    pip install requests
    
Linux and Mac:
    pip3 install requests

'''

#### START #### AUTO-GENERATED CODE TO INTERACT WITH MERAKI DASHBOARD ####

# Code generated using: https://github.com/mpapazog/rogue_meraki_python_sdk
    
import time

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

# getOrganizationInventoryDevices
#
# Description: Return the device inventory for an organization
# Endpoint: GET /organizations/{organizationId}/inventory/devices
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-inventory-devices
#
# Query parameters:
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 1000. Default is 1000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     usedState: String. Filter results by used or unused inventory. Accepted values are 'used' or 'unused'.
#     search: String. Search for devices in inventory based on serial number, mac address, or model.
#     macs: Array. Search for devices in inventory based on mac addresses.
#     networkIds: Array. Search for devices in inventory based on network ids.
#     serials: Array. Search for devices in inventory based on serials.
#     models: Array. Search for devices in inventory based on model.
#     tags: Array. Filter devices by tags. The filtering is case-sensitive. If tags are included, 'tagsFilterType' should also be included (see below).
#     tagsFilterType: String. To use with 'tags' parameter, to filter devices which contain ANY or ALL given tags. Accepted values are 'withAnyTags' or 'withAllTags', default is 'withAnyTags'.
#     productTypes: Array. Filter devices by product type. Accepted values are appliance, camera, cellularGateway, sensor, switch, systemsManager, and wireless.
#     licenseExpirationDate: String. Filter devices by license expiration date, ISO 8601 format. To filter with a range of dates, use 'licenseExpirationDate[<option>]=?' in the request. Accepted options include lt, gt, lte, gte.

def getOrganizationInventoryDevices(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/inventory/devices"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getOrganizationLicensesOverview
#
# Description: Return an overview of the license state for an organization
# Endpoint: GET /organizations/{organizationId}/licenses/overview
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-licenses-overview

def getOrganizationLicensesOverview(apiKey, organizationId):
    url = "/organizations/" + str(organizationId) + "/licenses/overview"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
#### END #### AUTO-GENERATED CODE TO INTERACT WITH MERAKI DASHBOARD ####


import sys, getopt, os, datetime, re

# https://stackoverflow.com/questions/41129921/validate-an-iso-8601-datetime-string-in-python
regex = r'^(-?(?:[1-9][0-9]*)?[0-9]{4})-(1[0-2]|0[1-9])-(3[01]|0[1-9]|[12][0-9])$'
matchIsoDateFormat = re.compile(regex).match
def checkIsoDate(str_val):
    try:            
        if matchIsoDateFormat( str_val ) is not None:
            return True
    except:
        pass
    return False

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
    
def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get("MERAKI_DASHBOARD_API_KEY", None) 
    
def main(argv): 
    # [-k <api_key>] [-o <org_name>] -s <start_date> [-e <end_date>]
    arg_apiKey      = None
    arg_orgName     = None
    arg_startDate   = None
    arg_endDate     = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:s:e:h')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-o':
            arg_orgName     = str(arg)
        if opt == '-s':
            arg_startDate   = str(arg)
        if opt == '-e':
            arg_endDate     = str(arg)
        if opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    if apiKey is None:
        log("ERROR: API key not found")
        killScript()
        
    if arg_orgName is None:
        log("ERROR: No organization name or scope provided")
        killScript()
    
    if not checkIsoDate(arg_startDate):
        killScript("Invalid or missing start date (must be YYYY-MM-DD)")
        
    isoNow          = datetime.datetime.now().isoformat()
    isoToday        = isoNow[:10]
        
    if not arg_endDate is None:
        if not checkIsoDate(arg_endDate):
            killScript("Invalid end date (must be YYYY-MM-DD)")
    else:
        arg_endDate = isoToday
        
    nowTimestamp    = str(isoNow)[:19].replace('T','_').replace(':', '.')
    fileName        = "devices_s_%s_e_%s_ts_%s.csv" % (arg_startDate, arg_endDate, nowTimestamp)
    
    log('Organization scope : "%s"' % arg_orgName)
    log("Report start date  : %s" % arg_startDate)
    log("Report end date    : %s" % arg_endDate)
    log("Report filename    : %s" % fileName)

    success, errors, rawOrgs = getOrganizations(apiKey)
    if rawOrgs == None:
        killScript('Unable to fetch organizations')
        
    organizations = []
        
    if arg_orgName == '/all':
        organizations = rawOrgs
    elif arg_orgName == '/ea':
        for org in rawOrgs:
            if org['licensing']['model'] == 'co-term':
                success, errors, licenseState = getOrganizationLicensesOverview(apiKey, org['id'])
                if licenseState == None:
                    continue
                if 'wireless' in licenseState['licensedDeviceCounts'] and licenseState['licensedDeviceCounts']['wireless'] == 10000:
                    organizations.append(org)
    else:
        for org in rawOrgs:
            if org['name'] == arg_orgName:
                organizations.append(org)
                break
                
    for org in organizations:
        org['deviceCounts'] = {}
        deviceCounts = {}
        success, errors, rawDevices = getOrganizationInventoryDevices(apiKey, org['id'])
        if rawDevices == None:
            continue
        for device in rawDevices:
            claimDate = device['claimedAt'][:10]
            if device['networkId'] != None and claimDate >= arg_startDate and claimDate <= arg_endDate:
                if not device['model'] in deviceCounts:
                    deviceCounts[device['model']] = 0
                deviceCounts[device['model']] += 1
        org['deviceCounts'] = deviceCounts
        
    models      = []
    orgNames    = []
    for org in organizations:
        if org['deviceCounts'] != {}:
            orgNames.append(org['name'])
        for model in org['deviceCounts']:
            if not model in models:
                models.append(model)
    models.sort()
    orgNames.sort()
    
    headersArray = ['orgName', 'orgId']
    for model in models:
        headersArray.append(model)
    headersString = ','.join(headersArray)
    
    reportLines = []
    for orgName in orgNames:
        for org in organizations:
            if org['name'] == orgName:
                line = [org['name'], org['id']]
                for model in models:
                    amountStr = '0'
                    if model in org['deviceCounts']:
                        amountStr = str(org['deviceCounts'][model])
                    line.append(amountStr)
                reportLines.append(','.join(line))
                break
        
    try:
        f = open(fileName, 'w')
        f.write("%s\n" % headersString)
        for line in reportLines:
            f.write("%s\n" % line)            
        f.close()
    except:
        killScript('Unable to write to file "%s"' % fileName)
    
    log('File "%s" written' % fileName)
    
    log('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])