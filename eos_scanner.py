READ_ME = '''Scans an organization for devices that have a published EoS/EoL date and prints a list of those devices.

Syntax:
    python[3] eos_scanner.py [-k <api key>] [-o <org name or id>] [-m <device model>] [-p screen/csv]
    
Parameters:
    -k <api key>            Your dashboard API key. If omitted, the script will attempt to load one from
                            OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org name or id>     The NAME or the ID for your organization. If omitted, will scan all orgs
    -m <device model>       Filter devices by model name. All devices with model name that starts with
                            the defined string will match, case insensitive
    -p screen/csv           Select where output will be printed. If omitted, default is "screen". Valid forms:
                                -p screen
                                -p csv
                                
All paramters are optional.
    
Example, print all EoS devices in org with name "My Org" to CSV:
    python eos_scanner.py -k 1234 -o "My Org" -p csv
    
Required python modules:
    requests
'''

import requests
import sys, getopt, os, datetime
import xml.etree.ElementTree as ET

API_KEY_ENV_VAR_NAME    = "MERAKI_DASHBOARD_API_KEY"
EOS_DOCS_URL            = "https://documentation.meraki.com/General_Administration/Other_Topics/Meraki_End-of-Life_(EOL)_Products_and_Dates"


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
#     networkIds: Array. Search for devices in inventory based on network ids. Use explicit 'null' value to get available devices only.
#     serials: Array. Search for devices in inventory based on serials.
#     models: Array. Search for devices in inventory based on model.
#     orderNumbers: Array. Search for devices in inventory based on order numbers.
#     tags: Array. Filter devices by tags. The filtering is case-sensitive. If tags are included, 'tagsFilterType' should also be included (see below).
#     tagsFilterType: String. To use with 'tags' parameter, to filter devices which contain ANY or ALL given tags. Accepted values are 'withAnyTags' or 'withAllTags', default is 'withAnyTags'.
#     productTypes: Array. Filter devices by product type. Accepted values are appliance, camera, cellularGateway, secureConnect, sensor, switch, systemsManager, and wireless.
#     licenseExpirationDate: String. Filter devices by license expiration date, ISO 8601 format. To filter with a range of dates, use 'licenseExpirationDate[<option>]=?' in the request. Accepted options include lt, gt, lte, gte.

def getOrganizationInventoryDevices(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/inventory/devices"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
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
    
    
# --- GENERATED CODE END ---


def fetch_eos_data():
    # This function scans the EoS data documentation page for the product info table and extracts data.
    # If the info page changes substantially, this part may need to be recoded
    # Returns None if any part of the operation crashes
    
    try:
        r = requests.get(EOS_DOCS_URL)
        rtext           = r.text
        start_position  = rtext.find("<table")
        end_position    = rtext.find("</table>")
        table_block     = rtext[start_position:end_position+8]
        
        eos_data = {}
        
        # Clean up invalid characters that cause issues with ET
        table_block     = table_block.replace("&nbsp;", "")
        table_block     = table_block.replace("&rsquo;", "'")

        root = ET.fromstring(table_block)

        for tbody in root.iter("tbody"):
            for tr in tbody:
                model_names = []
                for td in tr:
                    td_has_link = False
                    for a in td:
                        td_has_link = True
                        eos_data[a.text] = []
                        model_names.append(a.text)
                    if not td_has_link:
                        for model in model_names:
                            eos_data[model].append(td.text)
                        
    except:
        return None
        
    return eos_data
    
    
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
    arg_apiKey      = None
    arg_orgName     = None
    arg_model       = None
    arg_output      = "screen"
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:h:m:p:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        elif opt == '-o':
            arg_orgName     = str(arg)
        elif opt == '-m':
            arg_model       = str(arg)
        elif opt == '-p':
            arg_output      = str(arg)
        elif opt == '-h':
            killScript()
            
    api_key = getApiKey(arg_apiKey)
    if api_key is None:
        killScript("No API key provided")
        
    if not arg_output in ['screen', 'csv']:
        killScript('Paramater -p must be either "screen" or "csv"')
        
    eos_data = fetch_eos_data()
    if eos_data is None:
        killScript("Cannot fetch EoS data")
                
    success, errors, all_orgs = getOrganizations(api_key)
    if all_orgs is None:
        killScript("Cannot fetch organizations")
        
    organizations = []
    for org in all_orgs:
        if arg_orgName is None or org['name'] == arg_orgName or org['id'] == arg_orgName:
            organizations.append(org)
            
    results = []
    
    for org in organizations:
        log('Scanning org "%s" (%s)' % (org['name'], org['id']))
        success, errors, inventory = getOrganizationInventoryDevices(api_key, org['id'])
        fetched_networks    = False
        networks            = None
        if inventory is None:
            log('Warning: Unable to fetch inventory')
            continue
        for device in inventory:
            if device['model'] in eos_data and (arg_model is None or device['model'].lower().startswith(arg_model)):
                record = {'org': org, 'device': device, 'eos': eos_data[device['model']]}
                
                if 'networkId' in device and not device['networkId'] is None:
                    if not fetched_networks:
                        success, errors, networks = getOrganizationNetworks(api_key, org['id'])
                        fetched_networks = True
                    if networks is None:
                        log('Warning: Unable to fetch networks')
                        break
                    for net in networks:
                        if net['id'] == device['networkId']:
                            record['net'] = net
                            break
                else:
                    record['net'] = {'name':''}
            
                results.append(record)
    
    header = ["Organization", "Network", "Model", "Serial", "Device name", "End of Sales", "End of Life"]  
    
    if arg_output == "screen":    
        print('\n\n\n---\n\n\n')    
        format_str = "%-24s %-24s %-12s%-16s%-20s %-14s%s"  
        print(format_str % tuple(header))
    else:
        # Print to CSV
        timestamp       = str(datetime.datetime.now())[:19].replace(" ", "_").replace(":", ".")
        csv_format_str  = "%s\n"
        csv_file_name   = "eos_report_%s.csv" % timestamp
        
        with open(csv_file_name, "a") as csv_file:
            csv_file.write(csv_format_str % ','.join(header))
            
    for line in results:
        line_items  = [ str(line['org']['name'])[:24],
                        str(line['net']['name'])[:24],
                        line['device']['model'],
                        line['device']['serial'],
                        str(line['device']['name'])[:20],
                        line['eos'][1],
                        line['eos'][2]]
        if arg_output == "screen":
            print(format_str % tuple(line_items))
        else:
            with open(csv_file_name, "a") as csv_file:
                csv_file.write(csv_format_str % ','.join(line_items))                
            
    if arg_output == "csv":
        print()
        log('File "%s" written' % csv_file_name)
        print()
        
if __name__ == '__main__':
    main(sys.argv[1:])
            
    
