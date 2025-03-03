READ_ME = '''Exports line crossing event info across multiple organizations to CSV.

Syntax:
    python[3] daily_crossings.py [-k <api key>] [-o <org name or id>] [-d <date>] [-s <serial>] [-i <interval>]
    
Parameters:
    -k <api key>            Your dashboard API key. If omitted, the script will attempt to load one from
                            OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org name or id>     The NAME or the ID for your organization. If omitted, will scan all orgs
    -d <date>               The exact date to look up data for or number of days to go back.
                            Examples:
                                -d 2025-02-28       Returns data for 28 FEB 2025
                                -d 1                Returns data for yesterday
                            If omitted, will return data for the current day
    -s <serial>             Limit results to a camera with a speciufic serial number. If omitted, will return
                            data for all cameras in scope
    -i <interval>           Granularity of data in seconds. If omitted, data will be grouped into 1 hour chunks
                            (3600 seconds)
                                
All parameters are optional.
    
Example, export daily crossing info for yesterday, for all cameras with line crossing boundaries configured:
    python daily_crossings.py -k 1234 -d 1
    
Required python modules:
    requests
'''


# --- GENERATED CODE START ---


# Coded generated with: https://github.com/mpapazog/rogue_meraki_python_sdk
# Modified to properly support getOrganizationCameraDetectionsHistoryByBoundaryByInterval
    
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

def merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders=None, p_queryItems=None, p_queryString=None,
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
    if not p_queryString is None:
        if query == "":
            query = "?"
        query = query + p_queryString        
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
#     productTypes: Array. Filter devices by product type. Accepted values are appliance, camera, cellularGateway, secureConnect, sensor, switch, systemsManager, wireless, and wirelessController.
#     licenseExpirationDate: String. Filter devices by license expiration date, ISO 8601 format. To filter with a range of dates, use 'licenseExpirationDate[<option>]=?' in the request. Accepted options include lt, gt, lte, gte.

def getOrganizationInventoryDevices(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/inventory/devices"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# getOrganizationCameraBoundariesLinesByDevice
#
# Description: Returns all configured crossingline boundaries of cameras
# Endpoint: GET /organizations/{organizationId}/camera/boundaries/lines/byDevice
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-camera-boundaries-lines-by-device
#
# Query parameters:
#     serials: Array. A list of serial numbers. The returned cameras will be filtered to only include these serials.

def getOrganizationCameraBoundariesLinesByDevice(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/camera/boundaries/lines/byDevice"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# getOrganizationCameraDetectionsHistoryByBoundaryByInterval
#
# Description: Returns analytics data for timespans
# Endpoint: GET /organizations/{organizationId}/camera/detections/history/byBoundary/byInterval
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-camera-detections-history-by-boundary-by-interval
#
# Query parameters:
#     boundaryIds: Array. A list of boundary ids. The returned cameras will be filtered to only include these ids.
#     duration: Integer. The minimum time, in seconds, that the person or car remains in the area to be counted. Defaults to boundary configuration or 60.
#     perPage: Integer. The number of entries per page returned. Acceptable range is 1 - 1000. Defaults to 1000.
#     boundaryTypes: Array. The detection types. Defaults to 'person'.

def getOrganizationCameraDetectionsHistoryByBoundaryByInterval(apiKey, organizationId, query=None, queryStr=None):
    url = "/organizations/" + str(organizationId) + "/camera/detections/history/byBoundary/byInterval"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_queryString=queryStr, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# --- GENERATED CODE END ---  


import sys, getopt, os, datetime, re
from operator import itemgetter
from contextlib import redirect_stdout
API_KEY_ENV_VAR_NAME    = "MERAKI_DASHBOARD_API_KEY"


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
        
        
def calculateStartEndDateTimes(param_text):
    param_str       = str(param_text)
    integer_pattern = "^[0-9]*$"
    date_pattern    = "^[0-9][0-9][0-9][0-9]-[0-9][0-9]-[0-9][0-9]$"
    
    iso_pattern     = "%sT00:00:00Z"
    zero_time       = ""
    
    the_day         = None
    the_next_day    = None
    
    integer_matches = re.findall(integer_pattern, param_str)
    if len(integer_matches) == 1:
        delta           = int(integer_matches[0]) 
        the_day         = datetime.datetime.today() - datetime.timedelta(days=delta)
        the_next_day    = the_day + datetime.timedelta(days=1)
    else:
        date_matches    = re.findall(date_pattern, param_str)
        if len(date_matches) == 1:
            the_day         = datetime.datetime.fromisoformat(iso_pattern % param_text)
            the_next_day    = the_day + datetime.timedelta(days=1)
        
    if the_day is None or the_next_day is None:
        return None
        
    start_day_str   = str(the_day)[:10]
    end_day_str     = str(the_next_day)[:10]
    return({'start': iso_pattern % start_day_str, 'end': iso_pattern % end_day_str})
    

# --- MAIN ---


def main(argv):    
    # python[3] daily_crossings.py [-k <api key>] [-o <org name or id>] [-d <date>] [-s <serial>] [-i <interval>]
    
    arg_api_key     = None
    arg_org_name    = None
    arg_date        = "0"
    arg_serial      = None
    arg_interval    = "3600"
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:d:s:i:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_api_key     = str(arg)
        elif opt == '-o':
            arg_org_name    = str(arg)
        elif opt == '-d':
            arg_date        = str(arg)
        elif opt == '-s':
            arg_serial      = str(arg)
        elif opt == '-i':
            arg_interval    = str(arg)
        elif opt == '-h':
            killScript()
            
    api_key = getApiKey(arg_api_key)
    if api_key is None:
        killScript("No API key provided")
        
    dates = calculateStartEndDateTimes(arg_date)
    if dates is None:
        killScript("Invalid date parameter format")
    log('Got dates: %s' % dates)
    
    integer_pattern = "^[0-9]*$"
    integer_matches = re.findall(integer_pattern, arg_interval)
    if len(integer_matches) == 1:
        interval = int(integer_matches[0])
    else:
        killScript("Invalid interval parameter format")
        
    log("Fetching organizations...")    
        
    success, errors, all_orgs = getOrganizations(api_key)
    if all_orgs is None:
        killScript("Cannot fetch organizations")
        
    organizations = []
    for org in all_orgs:
        if arg_org_name is None or org['name'] == arg_org_name or org['id'] == arg_org_name:
            organizations.append(org)
            
    log("Fetching cameras...")
    
    for org in organizations:
        success, errors, inventory = getOrganizationInventoryDevices(api_key, org['id'])
        org['cameras'] = []
        if inventory is None:
            log('WARNING: Unable to fetch inventory for org "%s", ID: %s' % (org['name'], org['id']))
        else:
            for device in inventory:
                if device['model'].startswith('MV'):
                    org['cameras'].append(device)
        
    log("Fetching boundaries...")
    for org in organizations:
        org['boundaries'] = []
        for camera in org['cameras']:
            success, errors, boundaries = getOrganizationCameraBoundariesLinesByDevice(api_key, org['id'], query={'serials':[camera['serial']]})
            if boundaries is None:
                log('WARNING: Unable to fetch boundaries for camera "%s", ID: %s' % (camera['name'], camera['id']))
            else:
                for instance in boundaries:
                    for boundary in instance['boundaries']:
                        if boundary['type'] == 'line':
                            data = {'id': boundary['id'], 'name': boundary['name'], 'cameraSerial': camera['serial'], 'cameraName': camera['name']}
                            org['boundaries'].append(data)
     
    log("Fetching boundary crossings...")
    headers         = ['Organization name', 'Organization ID', 'Camera name', 'Camera serial', 'Boundary name', 'Boundary ID']
    headers_formed  = False
    results         = []
    query_str_template = "boundaryIds[]=%s&ranges[]interval=%s&ranges[]startTime=%s&ranges[]endTime=%s"
    for org in organizations:
        if 'boundaries' in org:
            for boundary in org['boundaries']:
                query_str = query_str_template % (boundary['id'], interval, dates['start'], dates['end'])
                success, errors, detections = getOrganizationCameraDetectionsHistoryByBoundaryByInterval(api_key, org['id'], queryStr=query_str)
                if not detections is None:
                    line = [org['name'], org['name'], boundary['cameraName'], boundary['cameraSerial'], boundary['name'], boundary['id']]
                    sorted_detections = sorted(detections[0]['results'], key=itemgetter('startTime'))
                    for item in sorted_detections:
                        line.append(str(item['in']))
                        line.append(str(item['out']))
                        if not headers_formed:
                            header_in = "%s-%s IN" % (item['startTime'][11:19], item['endTime'][11:19])
                            header_out = "%s-%s OUT" % (item['startTime'][11:19], item['endTime'][11:19])
                            headers.append(header_in)
                            headers.append(header_out)
                    headers_formed = True
                    results.append(line)
    
    log("Exporting results...")
    filename = "detections_%s.csv" % dates['start'][:10]
    with open(filename, 'w') as f:
        with redirect_stdout(f):
            print (','.join(headers))
            for line in results:
                print (','.join(line))
                
    log('File "%s" created' % filename)
        
if __name__ == '__main__':
    main(sys.argv[1:])
            
    
