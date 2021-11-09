readMe = """A Python 3 script to automatically reboot devices with a matching device tag on a weekly schedule.
The default tag matched is "auto-reboot". Tag devices in the Meraki dashboard with this device tag to
enable automatic reboots.

Script syntax, Windows:
    python auto_reboot.py [-k <api_key>] [-o <org_name>] [-d <day_of_week>] [-t <time>] [-g <device_tag>]
 
Script syntax, Linux and Mac:
    python3 auto_reboot.py [-k <api_key>] [-o <org_name>] [-d <day_of_week>] [-t <time>] [-g <device_tag>]
        
Optional parameters: 
    -k <api_key>        Your Meraki Dashboard API key. If omitted, the script will try to use one stored in
                        OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org_name>       The name of the organization to perform the reboots on. Use keyword "/all" instead of
                        an organization name to perform the operation for all organizations accessible by
                        your API key. This parameter can be omitted if your API key can only access one org
    -d <day_of_week>    Day of the week to perform the operation. Valid options: Monday, Tuesday, Wednesday,
                        Thursday, Friday, Saturday, Sunday. If omitted, default is Sunday
    -t <time>           Time to perform the operation. 24h format is recommended. If omitted, default is "00:00".
                        Note that time is relative to system time of the computer that runs this script
    -g <device_tag>     Devices that have the specified tag as a device tag will be rebooted. If omitted, 
                        default is "auto-reboot"
                   
Example, reboot all devices with tag "access-point" in organization Big Industries Inc every Sunday at 00:00:
    python auto_reboot.py -k 1234 -o "Big Industries Inc" -g access-point
                   
Required Python 3 modules:
    requests
    schedule
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    pip install schedule
    
Depending on your operating system and Python environment, you may need to use commands 
"python3" and "pip3" instead of "python" and "pip".
"""

import os, sys, getopt, time, datetime, json, schedule

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
            else:
                r = session.post(
                    url,
                    headers =   headers,
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
        retryInterval = 2
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
    endpoint = "/organizations"
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response 
    
def getOrganizationInventoryDevices(apiKey, organizationId):
    endpoint = "/organizations/%s/inventoryDevices" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response 
    
def rebootDevice(apiKey, serial):
    endpoint = "/devices/%s/reboot" % serial
    success, errors, headers, response = merakiRequest(apiKey, "POST", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response 
    
    
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
        

JOB_ARGUMENTS = {"apiKey": None, "organizations": [], "tag": None}

def rebootDevices():
    log("Rebooting devices...")
    apiKey          = JOB_ARGUMENTS['apiKey']
    organizations   = JOB_ARGUMENTS['organizations']
    tag             = JOB_ARGUMENTS['tag']
    
    for org in organizations:
        success, errors, inventory = getOrganizationInventoryDevices(apiKey, org['id'])
        if not inventory is None:
            for device in inventory:
                if (not device['networkId'] is None) and tag in device['tags']:
                    rebootDevice(apiKey, device['serial'])
                    
    log("Process complete. Waiting for next cycle...")
    
    
def getApiKey(argument):
    if not argument is None:
        return str(argument)
    apiKey = os.environ.get(API_KEY_ENV_VAR_NAME, None) 
    if apiKey is None:
        killScript()
    else:
        return apiKey
    
def scheduleDayObject(day):
    mappings = {
        'monday'    : schedule.every().monday,
        'tuesday'   : schedule.every().tuesday,
        'wednesday' : schedule.every().wednesday,
        'thursday'  : schedule.every().thursday,
        'friday'    : schedule.every().friday,
        'saturday'  : schedule.every().saturday,
        'sunday'    : schedule.every().sunday
    }
    
    lowerDay = str(day).lower()
    
    if lowerDay in mappings:
        return mappings[lowerDay]
    return None
        
    
def main(argv):
    arg_apiKey  = None
    arg_orgName = None
    arg_day     = "Sunday"
    arg_time    = "00:00"
    arg_tag     = "auto-reboot"
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:d:t:g:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey  = str(arg)
        if opt == '-o':
            arg_orgName = str(arg)
        if opt == '-d':
            arg_day     = str(arg)
        if opt == '-t':
            arg_time    = str(arg)
        if opt == '-g':
            arg_tag     = str(arg)
        if opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    
    success, errors, allOrgs = getOrganizations(apiKey)
    if allOrgs is None:
        killScript("Unable to fetch organizations")
        
    organizations = []
    if arg_orgName is None:
        if len(organizations) == 1:
            organizations = allOrgs
        else:
            killScript("Organization name required for this API key")              
    elif arg_orgName == "/all":
        organizations = allOrgs
    else:
        for org in allOrgs:
            if org["name"] == arg_orgName:
                organizations.append(org)
                break
    if len(organizations) == 0:
        killScript("No matching organizations")
        
    log("Reboot schedule configuration:\n------------\nDay:    %s\nTime:   %s\nTag:    %s\nOrganizations:" %(
            arg_day.capitalize(), arg_time, arg_tag))
    for org in organizations:
        print("%s (%s)" % (org['name'], org['id']))
    print("------------")
    
    dayObject = scheduleDayObject(arg_day)
    if dayObject is None:
        killScript("Invalid day-of-the-week argument")
    JOB_ARGUMENTS['apiKey'] = apiKey
    JOB_ARGUMENTS['organizations'] = organizations
    JOB_ARGUMENTS['tag'] = arg_tag
    dayObject.at(arg_time).do(rebootDevices)
    
    log("Starting scheduler...")
    while True:
        schedule.run_pending()
        time.sleep(1)    

if __name__ == '__main__':
    main(sys.argv[1:])
