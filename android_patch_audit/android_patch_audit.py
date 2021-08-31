readMe = """A Python 3 script to check the security patch date of Android devices managed by 
    Meraki Systems Manager and generate a report or apply tags to them to trigger enforcement actions.

Script syntax, Windows:
    python android_patch_audit.py [-c <config_file>]
 
Script syntax, Linux and Mac:
    python3 android_patch_audit.py [-c <config_file>]
    
Optional parameters:
    -c <config_file>    Filename or path for the configuration file needed to run this script.
                        If this parameter is omitted, default value is "config.yaml"
        
This script requires a configuration file in YAML format to run. See an example of such a file here:
https://github.com/meraki/automation-scripts/blob/master/android_patch_audit/config.yaml

Please refer to the comments in the example configuration file for explanations of the different options.
                              
Required Python 3 modules:
    requests
    pyyaml
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    pip install pyyaml
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""


import sys, getopt, time, datetime, json, yaml

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

DEFAULT_CONFIG_FILE_NAME    = "config.yaml"


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
    
def getOrganizationNetworks(apiKey, organizationId):
    endpoint = "/organizations/%s/networks" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response  
    
def getNetworkSmDevices(apiKey, networkId):
    endpoint = "/networks/%s/sm/devices?fields[]=androidSecurityPatchVersion" % networkId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
def modifyNetworkSmDevicesTags(apiKey, networkId, ids, tags, updateAction):
    endpoint = "/networks/%s/sm/devices/modifyTags" % networkId
    body = {
        "ids": ids,
        "tags": tags,
        "updateAction": updateAction
    }
    success, errors, headers, response = merakiRequest(apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
 
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
                       
        
def loadConfig(filename):
    try:
        file = open(filename, "r")
        config = yaml.safe_load(file)
        file.close()        
    except:
        killScript("Unable to load configuration file")
        
    return config
    
    
def checkPatchDate(maxAge, devicePatchDate):
    if devicePatchDate is None or devicePatchDate == '':
        return False
        
    patchDate       = datetime.datetime.strptime(devicePatchDate, "%Y-%m-%d")
    today           = datetime.datetime.strptime(datetime.datetime.today().isoformat()[:10], "%Y-%m-%d")
    observedAgeTd   = today - patchDate
    maxAgeTd        = datetime.timedelta(days=maxAge)
        
    if observedAgeTd > maxAgeTd:
        return False
    
    return True


def tagDevicesInBatches(apiKey, networkId, deviceIds, tag, action, maxBatchSize):    
    batchStart  = 0
    listLength  = len(deviceIds)
    
    while batchStart < listLength:
        currentBatch = []
        for i in range(batchStart, listLength):
            currentBatch.append(deviceIds[i])
            batchStart += 1
            if len(currentBatch) >= maxBatchSize:
                break
        
        if len(currentBatch) > 0:
            success, errors, response = modifyNetworkSmDevicesTags(apiKey, networkId, currentBatch, [tag], action)
            if not success:
                log("WARNING: Enforcement action failed for network with id %s" % networkId)
         
    
def scanCycle(config):
    apiKey              = config['apiKey']
    organizationName    = config['organizationName']
    enforceCompliant    = config['enforceCompliant']
    enforceViolating    = config['enforceViolating']    

    success, errors, allOrgs = getOrganizations(apiKey)    
    if allOrgs is None:
        log("Exiting scan cycle: Unable to fetch organizations")
        return None
        
    organizationId = None
    for org in allOrgs:
        if org['name'] == organizationName:
            organizationId = org['id']
            break            
    if organizationId is None:
        log("Exiting scan cycle: No organization with that name")   
        return None

    success, errors, allNets = getOrganizationNetworks(apiKey, organizationId)    
    if allOrgs is None:
        log("Exiting scan cycle: Unable to fetch networks")
        return None
    
    networks = []    
    for net in allNets:
        if "systemsManager" in net['productTypes']:
            networks.append(net)            
    log("Found %s Systems Manager networks" % len(networks))
    
    scanReport = {}
                
    for net in networks:
        success, errors, allDevices = getNetworkSmDevices(apiKey, net['id'])
        if allDevices is None:
            log('WARNING: Unable to fetch devices for net "%s"' % net['name'])
            continue
            
        devices = []               
        for dev in allDevices:
            if "android" in dev["osName"].lower():
                devices.append(dev)                
        log("Found %s Android devices" % len(devices))
            
        tagQueues = {
            "markCompliance": [],
            "markViolation": [],
            "removeCompliance": [],
            "removeViolation": []
        }
                    
        for dev in devices:
            deviceIsCompliant = checkPatchDate(config['maxPatchAge'], dev['androidSecurityPatchVersion'])
            if deviceIsCompliant:
                if enforceCompliant:
                    if not config['complianceTag'] in dev['tags']:
                        tagQueues['markCompliance'].append(dev['id'])
                    if enforceViolating and config['violationTag'] in dev['tags']:
                        tagQueues['removeViolation'].append(dev['id'])
            else:
                if config['enableReporting']:
                    if not net['id'] in scanReport:
                        scanReport[net['id']] = []
                    scanReport[net['id']].append({
                        "serial": dev['serialNumber'], 
                        "name": dev['name'], 
                        "osName": dev['osName'], 
                        "patchDate": dev['androidSecurityPatchVersion'], 
                        "location": dev['location']})
            
                if enforceViolating:
                    if not config['violationTag'] in dev['tags']:
                        tagQueues['markViolation'].append(dev['id'])
                    if enforceCompliant and config['complianceTag'] in dev['tags']:
                        tagQueues['removeCompliance'].append(dev['id'])
        
        if enforceCompliant:
            tagDevicesInBatches(apiKey, net['id'], tagQueues['markCompliance'], config['complianceTag'], 'add', config['batchSize'])
            tagDevicesInBatches(apiKey, net['id'], tagQueues['removeCompliance'], config['complianceTag'], 'remove', config['batchSize'])
        if enforceViolating:
            tagDevicesInBatches(apiKey, net['id'], tagQueues['markViolation'], config['violationTag'], 'add', config['batchSize'])
            tagDevicesInBatches(apiKey, net['id'], tagQueues['removeViolation'], config['violationTag'], 'remove', config['batchSize'])  

    if config['enableReporting'] and scanReport != {}:
        print("\n\nSummary report of violating devices")
        
        netCounter = 0
        devCounter = 0
    
        for netId in scanReport:
            netCounter += 1
            netName = None
            for net in networks:
                if net['id'] == netId:
                    netName = net['name']
        
            print('\nNetwork "%s":\n' % netName)
            print("%-20s%-20s%-16s%-14s%s" % ("Serial", "Name", "OS Name", "Patch date", "Location"))
            
            for dev in scanReport[netId]:
                devCounter += 1
                print("%-20s%-20s%-16s%-14s%s" % (dev["serial"], dev["name"], dev["osName"], dev["patchDate"], dev["location"]))
                
        netLabelEnd = ""
        if netCounter > 1:
            netLabelEnd = "s"
        devLabelEnd = ""
        if devCounter > 1:
            devLabelEnd = "s"
                
        print("\nTotal: %s device%s in %s network%s\n\n" % (devCounter, devLabelEnd, netCounter, netLabelEnd))                    
    
    return None
    
    
    
    
def main(argv):    
    arg_fileName = DEFAULT_CONFIG_FILE_NAME
    
    try:
        opts, args = getopt.getopt(argv, 'c:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-c':
            arg_fileName = str(arg)
            
    log('Using configuration file "%s"' % arg_fileName)
        
    rawConfig = loadConfig(arg_fileName)
    config = {}    
    
    try:
        config['apiKey']            = str(rawConfig['general']['apiKey'])
        config['organizationName']  = str(rawConfig['general']['organizationName'])
        config['batchSize']         = rawConfig['general']['processingBatchSize']
        config['maxPatchAge']       = rawConfig['policy']['maximumAndroidSecurityPatchAgeDays']
        config['enforceCompliant']  = rawConfig['enforcement']['tagCompliantDevices']['enabled']
        if config['enforceCompliant']:
            config['complianceTag'] = str(rawConfig['enforcement']['tagCompliantDevices']['tag'])
        config['enforceViolating']  = rawConfig['enforcement']['tagViolatingDevices']['enabled']
        if config['enforceViolating']:
            config['violationTag']  = str(rawConfig['enforcement']['tagViolatingDevices']['tag'])
        config['enableReporting']   = rawConfig['reporting']['enabled']
        enableScheduler             = rawConfig['general']['enableScheduler']
        runInterval                 = rawConfig['general']['runIntervalHours']
    except:
        killScript("Invalid config file format")
            
    loopFlag = True
    
    while(loopFlag):
        scanCycle(config)
        if enableScheduler != True:
            loopFlag = False
        else:
            log("Next scan in %s hours" % runInterval)
            time.sleep(runInterval * 3600)
    
    
if __name__ == '__main__':
    main(sys.argv[1:])