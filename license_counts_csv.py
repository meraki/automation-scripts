readMe = '''Exports license types and counts for one or more co-term organizations to a
CSV file.

Note: The script does not try to detect if the MX license edition is Secure SD-WAN Plus.
It will falsely mark Secure SD-WAN Plus licenses as Advanced Security.

Syntax, Windows:
    python license_counts_csv.py [-k <api_key>] [-o <org_name>] [-f <filename>]
    
Syntax, Linux and Mac:
    python3 license_counts_csv.py [-k <api_key>] [-o <org_name>] [-f <filename>]
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, one will be loaded from
                        environment variable MERAKI_DASHBOARD_API_KEY
    -o <org_name>       Name of the organization you want license information exported
                        for. If omitted, will process all organizations    
    -f <filename>       Name of the file to export license info to. If omitted, default
                        is licenses_<timestamp>.csv
              
Example, export license information for all organizations your admin has access to:
    python license_counts_csv.py -k 1234
        
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
    
# getNetworkApplianceSecurityIntrusion
#
# Description: Returns all supported intrusion settings for an MX network
# Endpoint: GET /networks/{networkId}/appliance/security/intrusion
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-security-intrusion

def getNetworkApplianceSecurityIntrusion(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/security/intrusion"
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
#     isBoundToConfigTemplate: Boolean. An optional parameter to filter config template bound networks. If configTemplateId is set, this cannot be false.
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
    
    
#### END #### AUTO-GENERATED CODE TO INTERACT WITH MERAKI DASHBOARD ####


import sys, getopt, datetime, os

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
    
def generateOutputFileName(userInput):
    if userInput is None:
        timestamp = datetime.datetime.now().isoformat().replace("T", "_").replace(":", ".")
        return "licenses_%s.csv" % timestamp
    return userInput


def main(argv):  
    arg_apiKey      = None
    arg_orgName     = None
    arg_fileName    = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:f:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-o':
            arg_orgName     = str(arg)
        if opt == '-f':
            arg_fileName    = str(arg)
        if opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    if apiKey is None:
        killScript("API key not found")
    
    success, errors, allOrgs = getOrganizations(apiKey)
    if allOrgs is None:
        killScript("Unable to fetch organizations")
        
    organizations = []
    for org in allOrgs:
        if arg_orgName is None or org['name'] == arg_orgName:
            organizations.append(org)
            
    if len(organizations) == 0:
        killScript("No matching organizations found")
            
    errorCounter                = 0
    invalidLicenseStateCounter  = 0
    file                        = None
    licenseTypes                = []
    
    for org in allOrgs:
        success, errors, licenseState = getOrganizationLicensesOverview(apiKey, org['id'])
        if licenseState is None:
            errorCounter += 1
            continue
        if not 'expirationDate' in licenseState and not 'licensedDeviceCounts' in licenseState:
            invalidLicenseStateCounter += 1
            continue
            
        org['licenseState']     = licenseState
        org['licenseEditions']  = {'appliance': 'Enterprise'}
        
        try:
            expirationDate = datetime.datetime.strptime(licenseState['expirationDate'], '%b %d, %Y UTC')
            org['licenseState']['expirationDate'] = expirationDate.isoformat()[:10]        
        except:
            log('WARNING: Unable to convert date "%s" to ISO format' % licenseState['expirationDate'])
                
        for licenseType in licenseState['licensedDeviceCounts']:
            if licenseType.startswith('MX'):
                success, errors, orgNetworks = getOrganizationNetworks(apiKey, org['id'])
                if not orgNetworks is None:
                    for net in orgNetworks:
                        if 'appliance' in net['productTypes']:
                            success, errors, ipsSettings = getNetworkApplianceSecurityIntrusion(apiKey, net['id'])
                            if not ipsSettings is None:
                                org['licenseEditions']['appliance'] = 'Advanced Security'
                            break
                break
        
        for licenseType in licenseState['licensedDeviceCounts']:
            if not licenseType in licenseTypes:
                licenseTypes.append(licenseType)
                
    header = [
        'organizationName', 
        'organizationId', 
        'expirationDate', 
        'licenseStatus', 
        'mxLicenseEdition'
    ]
    for item in licenseTypes:
        header.append(item)
        
    headerStr = ','.join(header)
    headerStr = "%s\n" % headerStr
    
    fileName = generateOutputFileName(arg_fileName)
    try:
        file = open(fileName, "w")
    except:
        killScript('Unable to open file "%s" for writing' % fileName)
        
    file.write(headerStr)
    
    for org in allOrgs:
        if not 'licenseState' in org:
            continue
        
        line = [
            org['name'],
            org['id'],
            org['licenseState']['expirationDate'],
            org['licenseState']['status'],
            org['licenseEditions']['appliance']            
        ]
        for device in licenseTypes:
            count = 0
            if device in org['licenseState']['licensedDeviceCounts']:
                count = org['licenseState']['licensedDeviceCounts'][device]
            line.append(str(count))
                
        lineStr = ','.join(line)
        lineStr = "%s\n" % lineStr
        
        file.write(lineStr)
    
    file.close()
    
    log('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])