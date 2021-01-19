readMe = """This is a simple script to get the license info for Meraki organizations.

Syntax:
  python get_license_info.py -k <api_key> [-o <org_name>]
    
Mandatory parameters:
  -k <api_key>        The API key for the administrator running the script

Optional parameters:
  -o <org_name>       The name of the organization to display license info for.
                      If omitted, all organizations accessible will be listed.

Example:
  python get_license_info.py -k 1234 -o "Example Company Inc"
                        
Required Python 3 modules:
  requests
    
Install these modules by running:
  pip install requests
    
Notes:
  * In Windows, enclose organization names in double quotes, eg. "My Organization".
  * Depending on your operating system, the commands may be "python3" and "pip3"
    instead of "python" and "pip"
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

#change this to "https://api.meraki.com/api/v1" to disable mega proxy
API_BASE_URL            = "https://api-mp.meraki.com/api/v1"


def merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders=None, p_queryItems=None, 
        p_requestBody=None, p_verbose=False, p_retry=0):
    #returns success, errors, responseHeaders, responseBody
    
    if p_retry > API_MAX_RETRIES:
        if(p_verbose):
            print("ERROR: Reached max retries")
        return False, None, None, None

    bearerString = "Bearer " + p_apiKey
    headers = {"Authorization": bearerString}
    if not p_additionalHeaders is None:
        headers.update(p_additionalHeaders)
        
    query = ""
    if not p_queryItems is None:
        query = "?" + urlencode(p_queryItems)
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


def getLicenses(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/licenses/overview" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def findOrganizationIdForName(p_organizationList, p_organizationName):
    if not p_organizationList is None:
        for org in p_organizationList:
            if org["name"] == p_organizationName:
                return org["id"]
        print("%-30s %s" %("Organization ID","Organization Name"))
    return None
        

def killScript(p_printHelp=True):
    if(p_printHelp):
        print(readMe)
    sys.exit(2)
    

def main(argv):
    arg_apiKey  = None
    arg_orgName = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey = arg
        if opt == '-o':
            arg_orgName = arg
            
    if arg_apiKey is None:
        killScript()
    
    organizationList = []
    
    success, errors, headers, orgs = getOrganizations(arg_apiKey)
    
    if not arg_orgName is None:
        orgId = findOrganizationIdForName(orgs, arg_orgName)
        if not orgId is None:
            orgItem = {
                "id"    : orgId,
                "name"  :arg_orgName
            }
            organizationList.append(orgItem)
        else:
            print("ERROR: Organization name cannot be found")
            killScript(False)
    else:
        organizationList = orgs
        
    for org in organizationList:
        print('\n---\n')
        success, errors, headers, licenses = getLicenses(arg_apiKey, org["id"])
        if not licenses is None:        
            print('\n---\n\nLicense info for organization "%s" (ID: %s)\n' % (org["name"], org["id"]))
        
            if "status" in licenses:
                print("%-20s%s" % ("Status:", licenses["status"]))
                
            if "expirationDate" in licenses:
                print("%-20s%s" % ("Expiration date:", licenses["expirationDate"]))
                
            if "licensedDeviceCounts" in licenses:
                print("\nLicensed device counts:")
                for deviceType in licenses["licensedDeviceCounts"]:
                    print("%-20s%s" % (deviceType, licenses["licensedDeviceCounts"][deviceType]))
        else:
            print('ERROR: Unable to fetch license info for organization "%s"' % org["name"])
        

if __name__ == '__main__':
    main(sys.argv[1:])
