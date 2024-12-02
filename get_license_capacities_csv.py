READ_ME = '''Exports license capacity info across multiple Co-term or PDL organizations to CSV.

Syntax:
    python[3] get_license_capacities_csv.py [-k <api key>] [-o <org name or id>] [-m <licensing model>]
    
Parameters:
    -k <api key>            Your dashboard API key. If omitted, the script will attempt to load one from
                            OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org name or id>     The NAME or the ID for your organization. If omitted, will scan all orgs
    -m <licensing model>    Licensing model can be one of: "coterm", "pdl", "all". Default is "all" 
                                
All parameters are optional.
    
Example, export license capacity info for all organizations:
    python get_license_capacities_csv.py -k 1234
    
Required python modules:
    requests
'''

import requests
import sys, getopt, os, datetime

API_KEY_ENV_VAR_NAME    = "MERAKI_DASHBOARD_API_KEY"


# --- GENERATED CODE START ---


# The code to interact with the Meraki Dashboard API has been generated with this script: 
# https://github.com/mpapazog/rogue_meraki_python_sdk

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
#
# Query parameters:
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 9000. Default is 9000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.

def getOrganizations(apiKey, query=None):
    url = "/organizations"
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


# getOrganizationLicensingCotermLicenses
#
# Description: List the licenses in a coterm organization
# Endpoint: GET /organizations/{organizationId}/licensing/coterm/licenses
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-licensing-coterm-licenses
#
# Query parameters:
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 1000. Default is 1000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     invalidated: Boolean. Filter for licenses that are invalidated
#     expired: Boolean. Filter for licenses that are expired

def getOrganizationLicensingCotermLicenses(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/licensing/coterm/licenses"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# getOrganizationLicensesExpiration
#
# Description: Return the aggregated expiration information of an organization's licenses
# Endpoint: GET /organizations/{organizationId}/licenses/expiration
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-licenses-expiration

def getOrganizationLicensesExpiration(apiKey, organizationId):
    url = "/organizations/" + str(organizationId) + "/licenses/expiration"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# --- GENERATED CODE END ---
    
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
        print(READ_ME)
        sys.exit()
    else:
        log("ERROR: %s" % reason)
        sys.exit()
    

def getApiKey(argument):
    if not argument is None:
        return str(argument)
    apiKey = os.environ.get(API_KEY_ENV_VAR_NAME, None) 
    if apiKey is None:
        killScript()
    else:
        return apiKey
        
        
def main(argv):    
    arg_api_key     = None
    arg_org_name    = None
    arg_lic_model   = "all"
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:h:m:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_api_key     = str(arg)
        elif opt == '-o':
            arg_org_name    = str(arg)
        elif opt == '-m':
            arg_lic_model   = str(arg).lower()
        elif opt == '-h':
            killScript()
            
    api_key = getApiKey(arg_api_key)
    if api_key is None:
        killScript("No API key provided")
        
    if not arg_lic_model in ['coterm', 'pdl', 'all']:
        killScript('Paramater -m must be one of "coterm", "pdl", "all"')
                                
    success, errors, all_orgs = getOrganizations(api_key)
    if all_orgs is None:
        killScript("Cannot fetch organizations")
        
    organizations = []
    for org in all_orgs:
        if arg_org_name is None or org['name'] == arg_org_name or org['id'] == arg_org_name:
            organizations.append(org)
            
    orgs_coterm = []
    orgs_pdl    = []
    lic_labels  = []
    
    # Split co-term and PDL orgs as they need to be processed differently
    for org in organizations:
        if org['licensing']['model'] == "co-term" and arg_lic_model in ['coterm', 'all']:
            orgs_coterm.append(org)
        elif org['licensing']['model'] == "per-device" and arg_lic_model in ['pdl', 'all']:
            orgs_pdl.append(org)
            
    # Process co-term orgs
    for org in orgs_coterm:
        org['licenses'] = {}
        success, errors, org_licenses = getOrganizationLicensingCotermLicenses(api_key, org['id'])
        mx_tier = 'ENT'
        mx_edition_labels = {
            'SD-WAN'            : 'SDW',
            'Advanced Security' : 'SEC'
        }
        
        if not org_licenses is None:
            newest_mx_lic_claim = None
            for lic in org_licenses:
                if not ('invalidated' in lic and lic['invalidated'] == True):
                    claim_date = datetime.datetime.fromisoformat(lic['claimedAt'])
                    if newest_mx_lic_claim is None or claim_date > newest_mx_lic_claim:
                        newest_mx_lic_claim = claim_date
                        if 'editions' in lic:
                            for edition_record in lic['editions']:
                                if edition_record['productType'] == 'appliance' and edition_record['edition'] in mx_edition_labels:
                                    mx_tier = mx_edition_labels[edition_record['edition']]
        
        success, errors, lic_overview = getOrganizationLicensesOverview(api_key, org['id'])
        if not lic_overview is None and 'licensedDeviceCounts' in lic_overview:
            for device in lic_overview['licensedDeviceCounts']:
                label = device
                if device.startswith('MX'):
                    label = "%s-%s" % (label, mx_tier)
                if label == 'wireless':
                    label = 'MR-ENT'
                org['licenses'][label] = lic_overview['licensedDeviceCounts'][device]
                if not label in lic_labels:
                    lic_labels.append(label)
    
    # Process PDL orgs
    for org in orgs_pdl:
        org['licenses'] = {}
        success, errors, lic_expiration = getOrganizationLicensesExpiration(api_key, org['id'])
        if not lic_expiration is None and 'dates' in lic_expiration:
            for date_entry in lic_expiration['dates']:
                for lic_type_entry in date_entry['licensesExpiringThisDate']['licenseTypes']:
                    label = lic_type_entry['licenseType']
                    if label == 'ENT':
                        label = 'MR-ENT'
                        
                    if not label in org['licenses']:
                        org['licenses'][label] = lic_type_entry['count']
                    else:
                        org['licenses'][label] += lic_type_entry['count']
    
    
    # Format data for CSV export
    lic_labels.sort()
    
    header = ['Organization name', 'Organization id', 'Dashboard URL', 'Licensing model']
    for label in lic_labels:
        header.append(label)
    
    body = []
    for segment in [orgs_coterm, orgs_pdl]:
        for org in segment:
            if 'licenses' in org and org['licenses'] != {}:
                line = [org['name'], org['id'], org['url'], org['licensing']['model']]
                for label in lic_labels:
                    if label in org['licenses']:
                        line.append(str(org['licenses'][label]))
                    else:
                        line.append('')
                body.append(line)
            
    # Print to CSV
    timestamp       = str(datetime.datetime.now())[:19].replace(" ", "_").replace(":", ".")
    csv_format_str  = "%s\n"
    csv_file_name   = "license_output_%s.csv" % timestamp
    
    with open(csv_file_name, "a") as csv_file:
        csv_file.write(csv_format_str % ','.join(header))
        
    for line in body:
        with open(csv_file_name, "a") as csv_file:
            csv_file.write(csv_format_str % ','.join(line))  
    
    log('File "%s" written' % csv_file_name)
    
    
if __name__ == '__main__':
    main(sys.argv[1:])
            
    
