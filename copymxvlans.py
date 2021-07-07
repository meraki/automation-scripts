readMe = """This is a script to migrate the MX VLAN configuration of one organization to another

Script syntax, Windows:
    python copymxvlans.py -k <api_key> -o <org_name> [-n <network_name>] [-t <network_tag>]
        [-m export/importall/importnew] [-f <file>]
 
Script syntax, Linux and Mac:
    python3 copymxvlans.py -k <api_key> -o <org_name> [-n <network_name>] [-t <network_tag>]
        [-m export/importall/importnew] [-f <file>]
    
Mandatory parameters:
    -k <api_key>                    Your Meraki Dashboard API key
    -o <org_name>                   The name of the organization to run the operation on
    
Optional parameters:
    -n <network_name>               Only process network with specified name
    -t <network_tag>                Only process networks with specified tag
    -m export/importall/importnew   Mode of operation. Valid forms:
                                    -m export: Exports VLAN configuration to a YAML file
                                    -m importall: Imports all VLANs in file. Overwrites
                                        config in existing VLANs. Enables VLANs if needed
                                    -m importnew: Imports config for VLANs that do not
                                        exist yet in target org/net. Does not overwrite
                                        existing VLANs. Will not enable VLANs for
                                        networks that do not have the setting on
                                    If omitted, default is "-m export"
    -f <file>                       Specify output filename. If omitted, default is
                                        vlans_<org_name>_<timestamp>.yaml
                            
Example, export all MX VLAN config in org "Big Industries Inc" to file "output.yaml":
    python copymxvlans.py -k 1234 -o "Big Industries Inc" -f output.yaml
    
Example, import all MX VLAN config for network "Headquarters" to org "Holding Corp" from file "output.yaml":
    python copymxvlans.py -k 1234 -o "Holding Corp" -n "Headquarters" -m importall -f output.yaml
    
Required Python 3 modules:
    requests
    pyyaml
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    pip install pyyaml
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""


import sys, getopt, time, datetime, yaml, re

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

API_BASE_URL            = "https://api.meraki.com/api/v1"


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
    return success, errors, headers, response
    
    
def getOrganizationNetworks(apiKey, organizationId):
    endpoint = "/organizations/%s/networks" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getNetworkApplianceVlansSettings(apiKey, networkId):
    endpoint = "/networks/%s/appliance/vlans/settings" % networkId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getNetworkApplianceVlans(apiKey, networkId):
    endpoint = "/networks/%s/appliance/vlans" % networkId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def updateNetworkApplianceVlansSettings(apiKey, networkId, vlansEnabled):
    endpoint = "/networks/%s/appliance/vlans/settings" % networkId
    body = { "vlansEnabled": vlansEnabled }
    success, errors, headers, response = merakiRequest(apiKey, "PUT", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def createNetworkApplianceVlan(apiKey, networkId, vlanId, vlanName):
    endpoint = "/networks/%s/appliance/vlans" % networkId
    body = { "id": vlanId, "name": vlanName }
    success, errors, headers, response = merakiRequest(apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
  
def updateNetworkApplianceVlan(apiKey, networkId, vlanId, body):
    endpoint = "/networks/%s/appliance/vlans/%s" % (networkId, vlanId)
    success, errors, headers, response = merakiRequest(apiKey, "PUT", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
  
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
        
        
def generateFileName(fileArgument, orgName): 
    if fileArgument is None:
        timestampIso = datetime.datetime.now().isoformat()
        timestampFileNameFriendly = timestampIso.replace(":",".")
        orgNameFileNameFriendly = re.sub('[^0-9a-zA-Z]+', '_', orgName)
        name = "vlans_%s_%s.yaml" % (orgNameFileNameFriendly, timestampFileNameFriendly)
        return name
    else:
        return fileArgument   
        
def keyIsSafeToCopy(key, vlan):
    if key == "networkId":
        return False
    if key == "dhcpOptions":
        if len(vlan["dhcpOptions"]) == 0:
            return False
        for option in vlan["dhcpOptions"]:
            if option["code"] == '':
                return False
    if key == "fixedIpAssignments" and vlan["fixedIpAssignments"] == {}:
        return False
    if key == "reservedIpRanges" and len(vlan["reservedIpRanges"]) == 0:
        return False

    return True
        
def exportVlans(apiKey, networks, fileName):
    networksVlans = {}
    
    for net in networks:
        success, errors, headers, vlanSettings = getNetworkApplianceVlansSettings(apiKey, net["id"])
        if (not vlanSettings is None) and (vlanSettings["vlansEnabled"]):
            success, errors, headers, vlans = getNetworkApplianceVlans(apiKey, net["id"])
            if not vlans is None:
                cleanedVlansList = []
                for vlan in vlans:
                    cleanedVlanItem = {}
                    for key in vlan:
                        if keyIsSafeToCopy(key, vlan):
                            cleanedVlanItem[key] = vlan[key]
                    cleanedVlansList.append(cleanedVlanItem)
                networksVlans[net["name"]] = cleanedVlansList
            else:
                log('Skipping network "%s": Error fetching VLANs' % net["name"])
        else:
            log('Skipping network "%s": No VLANs to process' % net["name"])
    try:
        file = open(fileName, "w")
        yaml.dump(networksVlans, file)
        file.close()
    except:
        killScript("Unable to write file")
        
    log('File "%s" written' % fileName)
  

def findNetNameInList (name, networkList):
    for net in networkList:
        if net["name"] == name:
            return net
    return None
    
    
def checkIfVlanIsUnique(vlanId, existingVlans):
    for vlan in existingVlans:
        if vlan["id"] == vlanId:
            return False

    return True
    
    
def stripIdFromVlanData (vlanData):
    result = {}
    for key in vlanData:
        if key != "id":
            result[key] = vlanData[key]
    return result
    
   
def importVlans(apiKey, networks, fileName, overwriteExisting):

    if True:
        file = open(fileName, "r")
        networksVlans = yaml.safe_load(file)
        file.close()        
    else:
        killScript("Unable to open VLAN configuration file")
        
    for netName in networksVlans:
        net = findNetNameInList (netName, networks)    
        if not net is None:
            success, errors, headers, vlanSettings = getNetworkApplianceVlansSettings(apiKey, net["id"])
            
            if (not vlanSettings is None) and overwriteExisting and (not vlanSettings["vlansEnabled"]):
                success, errors, headers, vlanSettings = updateNetworkApplianceVlansSettings(apiKey, net["id"], True)
            
            if (not vlanSettings is None) and (vlanSettings["vlansEnabled"]):                
                success, errors, headers, existingVlans = getNetworkApplianceVlans(apiKey, net["id"])
                
                if not existingVlans is None:                    
                    for vlan in networksVlans[netName]:
                        unique = checkIfVlanIsUnique(vlan["id"], existingVlans)
                        if unique:
                            success, errors, headers, result = createNetworkApplianceVlan(apiKey, net["id"], vlan["id"], vlan["name"])
                        if overwriteExisting or not unique:
                            success, errors, headers, result = updateNetworkApplianceVlan(apiKey, net["id"], vlan["id"], stripIdFromVlanData(vlan))
                            
                                      
    
def main(argv):    
    arg_apiKey      = None
    arg_orgName     = None
    arg_netName     = None
    arg_netTag      = None
    arg_mode        = "export"
    arg_fileName    = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:n:t:m:f:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-o':
            arg_orgName     = str(arg)
        if opt == '-n':
            arg_netName     = str(arg)
        if opt == '-t':
            arg_netTag      = str(arg)
        if opt == '-m':
            arg_mode        = str(arg)
        if opt == '-f':
            arg_fileName    = str(arg)
            
    if arg_apiKey is None or arg_orgName is None:
        killScript()      

    if (not arg_netName is None) and (not arg_netTag is None):
        killScript("Network name and tag filters cannot be used at the same time")
        
    if arg_mode in ["export", "importall", "importnew"]:
        mode = arg_mode[:6]
        overwriteExisting = arg_mode.endswith("all")
        if mode == "import":
            if arg_fileName is None:
                killScript('Argument "-f <file_name>" is needed for mode "%s"' % arg_mode)
            log('"%s" mode selected (overwriteExisting: %s)' % (mode, overwriteExisting))
        else:
            log('"%s" mode selected' % mode)            
    else:
        killScript("Invalid operating mode")
        
    success, errors, headers, organizations = getOrganizations(arg_apiKey)
    
    if organizations is None:
        killScript("Unable to fetch organizations for that API key")
    
    organizationId      = None
    organizationName    = None
    
    for org in organizations:
        if org['name'] == arg_orgName:
            organizationId = org['id']
            organizationName = org['name']
            break
            
    if organizationId is None:
        killScript("No organization found with that name")
        
    fileName = generateFileName(arg_fileName, organizationName)
                                
    success, errors, headers, allNetworks = getOrganizationNetworks(arg_apiKey, organizationId)
    
    if allNetworks is None:
        killScript("Unable to fetch networks for that organization")
        
    networks = []
        
    for net in allNetworks:
        if "appliance" in net["productTypes"]:
            networkIsInScope = False
            if arg_netName is None and arg_netTag is None:
                networkIsInScope = True

            if not arg_netName is None and net["name"] == arg_netName:
                networkIsInScope = True
                
            if not arg_netTag is None and arg_netTag in net["tags"]:
                networkIsInScope = True
            
            if networkIsInScope:
                networks.append(net)
                
           
    if len(networks) == 0:
        killScript("No compatible networks found in organization")
        
    if mode == "import":
        importVlans(arg_apiKey, networks, fileName, overwriteExisting)
    else:
        exportVlans(arg_apiKey, networks, fileName)
    
    
    
if __name__ == '__main__':
    main(sys.argv[1:])