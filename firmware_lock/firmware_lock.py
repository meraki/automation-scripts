readMe = """A Python 3 script to lock firmware for devices in an organization to desired builds or release
trains. The script works by checking for scheduled firmware updates at defined intervals and
delaying any that do not meet the desired criteria by a week if there is less than one week remaining before
the update is scheduled to happen. This pushes unwanted firmware upgrades forward in time indefinitely.

This script requires a configuration file to run. By default, it will try to open file "config.yaml",
located in the same folder as the script itself. Copy "config.yaml.example" to "config.yaml", and edit this 
configuration file to match your environment before running this script.

Script syntax, Windows:
    python firmware_lock.py [-c <config_file_name>]

Script syntax, Linux and Mac:
    python3 firmware_lock.py [-c <config_file_name>]

Optional parameters:
    -c <config_file_name>       Filename of the cofiguration file to be used. If omitted, the default is
                                "config.yaml"

Example configuration file:
    https://github.com/meraki/automation-scripts/tree/master/firmware_lock

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
DEFAULT_INTERVAL_HOURS      = 24
DEFAULT_RUN_ONCE            = False

DEVICE_TYPE_MAPPINGS        = {
                                "MX": "appliance",
                                "MS": "switch",
                                "MR": "wireless",
                                "MV": "camera",
                                "MT": "sensor",
                                "MG": "cellularGateway"
                            }

PRODUCT_SHORTNAME_MAPPINGS  = {
                                "appliance"         : "MX",
                                "switch"            : "MS",
                                "wireless"          : "MR",
                                "camera"            : "MV",
                                "sensor"            : "MT",
                                "cellularGateway"   : "MG"
                            }



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

def getOrganizationConfigTemplates(apiKey, organizationId):
    endpoint = "/organizations/%s/configTemplates" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)
    return success, errors, response

def getNetworkFirmwareUpgrades(apiKey, networkId):
    endpoint = "/networks/%s/firmwareUpgrades" % networkId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)
    return success, errors, response

def updateNetworkFirmwareUpgrade(apiKey, networkId, requestBody):
    endpoint = "/networks/%s/firmwareUpgrades" % networkId
    success, errors, headers, response = merakiRequest(apiKey, "PUT", endpoint, p_requestBody=requestBody, p_verbose=FLAG_REQUEST_VERBOSE)
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


def loadConfig(filename):
    try:
        file = open(filename, "r")
        config = yaml.safe_load(file)
        file.close()
    except:
        killScript("Unable to load configuration file")
    return config


def checkIfDeviceTypesInScope(productTypes, rules):
    for product in productTypes:
        if product in rules:
            return True
    return False


def tzLocalOffset():
    currentDateTime = datetime.datetime.fromtimestamp(time.mktime(time.localtime()))
    utcDateTime = datetime.datetime.fromtimestamp(time.mktime(time.gmtime()))

    needsMinus = False
    if currentDateTime >= utcDateTime:
        offset = str(currentDateTime - utcDateTime)[:-3]
    else:
        needsMinus = True
        offset = str(utcDateTime - currentDateTime)[:-3]

    if len(offset) < 5:
        offset = "0%s" % offset

    if needsMinus:
        offset = "-%s" % offset
    else:
        offset = "+%s" % offset

    return offset


def currentDateTimeTzAware():
    isoString = ("%s%s" % (str(datetime.datetime.now())[:-7], tzLocalOffset())).replace(" ", "T")
    return dateTimeFromIsoString(isoString)


def dateTimeFromIsoString(isoString):
    return datetime.datetime.strptime(isoString, "%Y-%m-%dT%H:%M:%S%z")


def performScan(apiKey, organizations, enforcementRules):
    networks = []
    for org in organizations:
        success, errors, allNets = getOrganizationNetworks(apiKey, org['id'])
        if not allNets is None:
            for net in allNets:
                if checkIfDeviceTypesInScope(net['productTypes'], enforcementRules):
                    networks.append(net)
        success, errors, allTemplates = getOrganizationConfigTemplates(apiKey, org['id'])
        if not allTemplates is None:
            for template in allTemplates:
                if checkIfDeviceTypesInScope(template['productTypes'], enforcementRules):
                    networks.append(template)

    for net in networks:
        success, errors, firmwareInfo = getNetworkFirmwareUpgrades(apiKey, net['id'])
        if not success:
            log('WARNING: Unable to enforce net "%s"' % net['name'])
        else:
            if 'products' in firmwareInfo:
                for deviceType in firmwareInfo['products']:
                    if 'nextUpgrade' in firmwareInfo['products'][deviceType]:
                            nextUpgrade = firmwareInfo['products'][deviceType]['nextUpgrade']
                            if (deviceType in enforcementRules and
                                    'toVersion' in nextUpgrade and
                                    'firmware' in nextUpgrade['toVersion']):
                                flagPushUpdate = False
                                if 'train' in enforcementRules[deviceType]:
                                    if nextUpgrade['toVersion']['releaseType'] != enforcementRules[deviceType]['train']:
                                        flagPushUpdate = True
                                if 'version' in enforcementRules[deviceType]:
                                    enforcedVersion = "%s %s" % (PRODUCT_SHORTNAME_MAPPINGS[deviceType], enforcementRules[deviceType]['version'])
                                    if nextUpgrade['toVersion']['shortName'] != enforcedVersion:
                                        flagPushUpdate = True
                                if flagPushUpdate:
                                    currentDateTime = currentDateTimeTzAware()
                                    configuredDateTime = dateTimeFromIsoString(nextUpgrade['time'])
                                    oneWeek = datetime.timedelta(weeks=1)
                                    timeRemaining = configuredDateTime - currentDateTime
                                    if(timeRemaining<oneWeek):
                                        log('Net "%s": Delaying upgrade to version %s' % (net['name'],
                                            nextUpgrade['toVersion']['shortName']))
                                        newDateTime = configuredDateTime + oneWeek
                                        pushBody = {
                                            'products': {
                                                deviceType: {
                                                    'nextUpgrade': {
                                                        'time': newDateTime.isoformat()
                                                    }
                                                }
                                            }
                                        }
                                        updateNetworkFirmwareUpgrade(apiKey, net['id'], pushBody)
                                    else:
                                        log('Net "%s": Ignoring upgrade to version %s: Over 1 week left' % (net['name'],
                                            nextUpgrade['toVersion']['shortName']))


def main(argv):
    arg_configFile = DEFAULT_CONFIG_FILE_NAME

    try:
        opts, args = getopt.getopt(argv, 'c:h:')
    except getopt.GetoptError:
        killScript()

    for opt, arg in opts:
        if opt == '-c':
            arg_configFile = str(arg)
        if opt == '-h':
            killScript()

    log('Using configuration file "%s"' % arg_configFile)

    rawConfig = loadConfig(arg_configFile)

    flagApplyToAll      = False
    organizationName    = None
    runOnce             = DEFAULT_RUN_ONCE
    scanIntervalHours   = DEFAULT_INTERVAL_HOURS
    enforcementRules    = {}


    try:
        apiKey = rawConfig['general']['apiKey']
        if 'applyToAllOrganizations' in rawConfig['general']:
            flagApplyToAll = rawConfig['general']['applyToAllOrganizations']
        if 'organizationName' in rawConfig['general']:
            organizationName = rawConfig['general']['organizationName']
        if 'runOnce' in rawConfig['general']:
            runOnce = rawConfig['general']['runOnce']
        if 'scanIntervalHours' in rawConfig['general']:
            scanIntervalHours = rawConfig['general']['scanIntervalHours']
        if 'lockTrain' in rawConfig:
            for deviceType in rawConfig['lockTrain']:
                value = rawConfig['lockTrain'][deviceType]
                if deviceType in DEVICE_TYPE_MAPPINGS and not value is None:
                    enforcementRules[DEVICE_TYPE_MAPPINGS[deviceType]] = {'train': str(value)}
        if 'lockVersion' in rawConfig:
            for deviceType in rawConfig['lockVersion']:
                value = rawConfig['lockVersion'][deviceType]
                if deviceType in DEVICE_TYPE_MAPPINGS and not value is None:
                    # overwrites 'train' enforcement rules. This is intentional
                    enforcementRules[DEVICE_TYPE_MAPPINGS[deviceType]] = {'version': str(value)}
    except:
        killScript('Invalid config file "%s"' % arg_configFile)

    log("Using enforcement rules: %s" % enforcementRules)

    success, errors, allOrgs = getOrganizations(apiKey)
    if allOrgs is None:
        killScript("Unable to fetch organizations")

    organizations = []

    if flagApplyToAll:
        organizations = allOrgs
    else:
        for org in allOrgs:
            if org['name'] == organizationName:
                organizations.append(org)
                break

    if len(organizations) == 0:
        killScript("No matching organizations found")

    while(True):
        log("Starting next scan...")
        performScan(apiKey, organizations, enforcementRules)
        if not runOnce:
            log("Next scan in %s hours" % scanIntervalHours)
            time.sleep(scanIntervalHours * 3600)
        else:
            print("Exiting.")
            sys.exit()

if __name__ == '__main__':
    main(sys.argv[1:])