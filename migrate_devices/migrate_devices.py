readMe = '''
Migrates devices from one organization to another. The script works in 3 stages:
1. Run the script in export mode to compile device information into a local file
2. Run the script in unclaim mode to remove devices from their source organization
3. Run the script in import mode to claim devices into the destination organization
    as listed in the file exported during the first step
    
As a safety measure, you need to specify a netowrk tag to be used as a filter for 
exporting and unclaiming.

Note that there may be a gap of several minutes between when devices are unclaimed from one
organization and when they are claimable into another. Please plan maintenance breaks
accordingly.

The export function creates a file containing the following information about devices in scope:
    Serial number
    Name
    Latitude
    Longitude
    Street address
   
Network configuration is NOT migrated. Before running this script, make sure your destination
organization has networks with the exact same names as the ones the devices will be removed
from in the source organization. To move network configuration at scale, use a script such
as this one first:
https://github.com/meraki/automation-scripts/tree/master/migrate_networks

Syntax, Windows:
    python migrate_devices.py [-k <api_key>] -o <org_name> -m <mode> [-t <tag>] [-f <file>]
    
Syntax, Linux and Mac:
    python3 migrate_devices.py [-k <api_key>] -o <org_name> -m <mode> [-t <tag>] [-f <file>]
    
Mandatory parameters:
    -o <org_name>       The name of the organization you want to interact with
    -m <mode>           Mode of operation for the script. Valid forms:
                            -m export           Exports device data to file
                            -m unclaim          Removes devices from org
                            -m import           Imports device data from file
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, one will be loaded from
                        environment variable MERAKI_DASHBOARD_API_KEY
    -t <tag>            Network tag to be matched for exporting and unclaiming. This parameter
                        is MANDATORY when exporting or unclaiming, but will be IGNORED during
                        import
    -f <file>           Name of the file to be used for export/import. This parameter is 
                        MANDATORY when importing and OPTIONAL when exporting, defaulting to
                        devices_<timestamp>.json if omitted. It will be IGNORED when running
                        the scrpt in unclaim mode
              
Example:
    1. Export all devices in networks tagged "franchise" into a file using the default
        filename format, from organization "Big Industries Inc":
    python migrate_devices.py -k 1234 -o "Big Industries Inc" -m export -t franchise
    
    2. Unclaim all devices exported during the previous step:
    python migrate_devices.py -k 1234 -o "Big Industries Inc" -m unclaim -t franchise
    
    3. Claim all exported devices into organization "Big Franchise", assuming timestamp was
        2022-22-21_11.42.00:
    python migrate_devices.py -k 1234 -o "Big Franchise" -m import -f devices_2022-22-21_11.42.00.json
    
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

# removeNetworkDevices
#
# Description: Remove a single device
# Endpoint: POST /networks/{networkId}/devices/remove
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!remove-network-devices
#
# Request body schema:
#     serial: String. The serial of a device

def removeNetworkDevices(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/devices/remove"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# releaseFromOrganizationInventory
#
# Description: Release a list of claimed devices from an organization.
# Endpoint: POST /organizations/{organizationId}/inventory/release
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!release-from-organization-inventory
#
# Request body schema:
#     serials: Array. Serials of the devices that should be released

def releaseFromOrganizationInventory(apiKey, organizationId, body=None):
    url = "/organizations/" + str(organizationId) + "/inventory/release"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# claimNetworkDevices
#
# Description: Claim devices into a network. (Note: for recently claimed devices, it may take a few minutes for API requsts against that device to succeed)
# Endpoint: POST /networks/{networkId}/devices/claim
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!claim-network-devices
#
# Request body schema:
#     serials: Array. A list of serials of devices to claim

def claimNetworkDevices(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/devices/claim"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# getNetworkDevices
#
# Description: List the devices in a network
# Endpoint: GET /networks/{networkId}/devices
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-devices

def getNetworkDevices(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/devices"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# updateDevice
#
# Description: Update the attributes of a device
# Endpoint: PUT /devices/{serial}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-device
#
# Request body schema:
#     name: String. The name of a device
#     tags: Array. The list of tags of a device
#     lat: Number. The latitude of a device
#     lng: Number. The longitude of a device
#     address: String. The address of a device
#     notes: String. The notes for the device. String. Limited to 255 characters.
#     moveMapMarker: Boolean. Whether or not to set the latitude and longitude of a device based on the new address. Only applies when lat and lng are not specified.
#     switchProfileId: String. The ID of a switch profile to bind to the device (for available switch profiles, see the 'Switch Profiles' endpoint). Use null to unbind the switch device from the current profile. For a device to be bindable to a switch profile, it must (1) be a switch, and (2) belong to a network that is bound to a configuration template.
#     floorPlanId: String. The floor plan to associate to this device. null disassociates the device from the floorplan.
#     elevation: Number. The elevation of this device in meters
#     elevationUncertainty: Integer. The uncertainty of this device's elevation in meters (+/-).

def updateDevice(apiKey, serial, body=None):
    url = "/devices/" + str(serial)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
#### END #### AUTO-GENERATED CODE TO INTERACT WITH MERAKI DASHBOARD ####

import sys, getopt, os, datetime, json

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
        return "devices_%s.json" % timestamp
    return userInput
    
def getNetworkIdByName(networkList, name):
    for net in networkList:
        if net['name'] == name:
            return net['id']
    return None


def exportDevices(apiKey, organizationId, tag, fileName):
    success, errors, allNetworks = getOrganizationNetworks(apiKey, organizationId)
    if allNetworks is None:
        killScript('Unable to fetch networks')
                
    filteredNetworkIds          = []
    filteredNetworkNames        = []
    filteredNetNameIdMapping    = {}
    for net in allNetworks:
        if tag in net['tags']:
            filteredNetworkIds.append(net['id'])
            filteredNetworkNames.append(net['name'])
            filteredNetNameIdMapping[net['name']] = net['id']
            
    filteredNetworkNames.sort()
    
    networks = []
    
    for netName in filteredNetworkNames:
        netId   = filteredNetNameIdMapping[netName]
        success, errors, netDevices = getNetworkDevices(apiKey, netId)
        if netDevices is None:
            log('WARNING: Unable to fetch devices for network "%s"' % netName)
            continue
        if len(netDevices) == 0:
            log('Skipping network "%s": Contains no devices' % netName)
            continue            
            
        netRecord  = {
            'name'      : netName,
            'devices'   : []
        }
        for device in netDevices:
            deviceRecord = {'serial': device['serial']}
            if 'lat' in device:
                deviceRecord['lat'] = device['lat']
            if 'lng' in device:
                deviceRecord['lng'] = device['lng']
            if 'address' in device:
                deviceRecord['address'] = device['address']
            if 'name' in device:
                deviceRecord['name'] = device['name']
            netRecord['devices'].append(deviceRecord)
        networks.append(netRecord)
        
    try:
        f = open(fileName, 'w')
        json.dump(networks, f, indent=4)
        f.close()
    except:
        killScript('Unable to write to file "%s"' % fileName)
        
    log('File "%s" written' % fileName)
        

def unclaimDevices(apiKey, organizationData, networkTag):
    log('Organization: %s (%s)' % (organizationData['name'], organizationData['id']))
    log('Network tag: %s' % networkTag)
    print('\nWARNING: THIS OPERATION IS NOT REVERSIBLE\nMAKE SURE YOU HAVE EXPORTED YOUR CONFIGURATION BEFORE CONTINUING\n')
    print('UNCLAIMING WILL START IN 30 SECONDS\nQUIT THIS SCRIPT NOW TO CANCEL\n')
    time.sleep(30)
    
    log("Creating device configuration backup...")
    exportDevices(apiKey, organizationData['id'], networkTag, generateOutputFileName(None))
    
    success, errors, allNetworks = getOrganizationNetworks(apiKey, organizationData['id'])
    if allNetworks is None:
        killScript('Unable to fetch networks')
        
    for net in allNetworks:
        if networkTag in net['tags']:
            log('Unclaiming devices from network "%s"' % net['name'])
            success, errors, netDevices = getNetworkDevices(apiKey, net['id'])
            if netDevices is None:
                log('WARNING: Unable to fetch devices for network "%s"' % net['name'])
                continue
            
            for device in netDevices:
                success, errors, response = removeNetworkDevices(apiKey, net['id'], body={'serial': device['serial']})
                if not success:
                    log('WARNING: Unable to remove device %s from network' % device['serial'])
                    continue
                    
                success, errors, response = releaseFromOrganizationInventory(apiKey, organizationData['id'], body={'serials': [device['serial']]})
                if not success:
                    log('WARNING: Unable to unclaim device %s' % device['serial'])
                    
    log('Released devices may take several minutes to be available for claiming in a different organization. This is normal')
    

def importDevices(apiKey, organizationId, filename):
    try:
        f = open(filename, 'r')
        networkData = json.load(f)
        f.close()
    except:
        killScript('Unable to read file "%s"' % filename)
        
    success, errors, orgNetworks = getOrganizationNetworks(apiKey, organizationId)
    if orgNetworks is None:
        killScript('Unable to fetch networks')
            
    for net in networkData:
        netId = getNetworkIdByName(orgNetworks, net['name'])
        if netId is None:
            log('WARNING: Organization does not contain network with name "%s"' % net['name'])
            continue            
        
        for device in net['devices']:
            success, errors, response = claimNetworkDevices(apiKey, netId, body={'serials': [device['serial']]})
            if not success:
                log('WARNING: Unable to claim device %s' % device['serial'])
                continue
                
            payload = {}
            if 'name' in device:
                payload['name']     = device['name']
            if 'address' in device:
                payload['address']  = device['address']
            if 'lat' in device:
                payload['lat']      = device['lat']
            if 'lng' in device:
                payload['lng']      = device['lng']
                
            if payload != {}:
                updateDevice(apiKey, device['serial'], body=payload)
        

def main(argv):  
    # migrate_devices.py [-k <api_key>] -o <org_name> -m <mode> [-t <tag>] [-f <file>]
    arg_apiKey      = None
    arg_orgName     = None
    arg_mode        = None
    arg_tag         = None
    arg_fileName    = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:m:t:f:h')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-o':
            arg_orgName     = str(arg)
        if opt == '-m':
            arg_mode        = str(arg)
        if opt == '-t':
            arg_tag         = str(arg)
        if opt == '-f':
            arg_fileName    = str(arg)
        if opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    if apiKey is None:
        log("ERROR: API key not found")
        killScript()
        
    if arg_orgName is None:
        log("ERROR: No organization name provided")
        killScript()
        
    if not arg_mode in ['export', 'unclaim', 'import']:
        killScript('Parameter -m <mode> must be one of export, unclaim, import')
        
    if arg_mode == 'import' and arg_fileName == None:
        killScript('Import mode requires parameter -f <file_name>')
        
    if arg_mode in ['export', 'unclaim'] and arg_tag is None:
        killScript('Modes export, unclaim require parameter -t <network_tag>')
        
    success, errors, organizations = getOrganizations(apiKey)
    if organizations == None:
        killScript('Unable to fetch organizations')
        
    matchedOrg = None
    for org in organizations:
        if org['name'] == arg_orgName:
            matchedOrg = org
            break
            
    if matchedOrg is None:
        killScript('No organizations with that name')
                
    if arg_mode == 'export':
        log('Exporting devices from organization "%s"...' % org['name'])
        exportDevices(apiKey, org['id'], arg_tag, generateOutputFileName(arg_fileName))
        
    elif arg_mode == 'unclaim':
        log('Unclaiming devices from organization "%s"...' % org['name'])
        unclaimDevices(apiKey, org, arg_tag)
        
    elif arg_mode == 'import':
        log('Importing devices into organization "%s"...' % org['name'])
        importDevices(apiKey, org['id'], arg_fileName)
        
    log('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])