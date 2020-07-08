readMe = """This is script to create a copy of a template-based network that preserves as many of the
  network's settings as possible, while not relying on a configuration template. The initial focus of
  the script is converting MX appliance networks.
 
Syntax:
  removetemplate -k <key> -o <org name> -n <source net name>
  
Notes:
  This release supports the following features:
    General:
        Basic network settings
        Network admin privileges
        Network tags
        Group policy objects
    MX:
        VLANs and subnets
        VLAN group policies
        Static routes (affected by an API bug at time of writing. See comments in code)
        NAT
        L3 Firewall
        L7 Firewall
        Traffic shaping
        Content filtering
        AMP
        IPS
  The source for NAT/Port forwarding rules is the Config template. Local NAT overrides are ignored
  This script uses the following elements, which are beta at time of writing:
    * Dashboard API v1: https://developer.cisco.com/meraki/api-v1/
    * Dashboard API mega proxy (api-mp.meraki.com)
"""

import sys, getopt, time, json, ipaddress
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


def merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders=None, p_queryItems=None, p_requestBody=None, p_verbose=False, p_retry=0):
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
            print("Hit max request rate. Retrying %s after %s seconds" % (p_retry+1, r.headers["Retry-After"]))
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
                        responseBody.append(nextBody)
                else:
                    responseBody = None
    
    return success, errors, responseHeaders, responseBody
    
    
def getOrganizations(p_apiKey):
    endpoint = "/organizations"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getNetworks(p_apiKey, p_organizationId):
    endpoint = "/organizations/" + p_organizationId + "/networks"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getAdministrators(p_apiKey, p_organizationId):
    endpoint = "/organizations/" + p_organizationId + "/admins"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def updateAdministrator(p_apiKey, p_organizationId, p_adminId, p_settings):
    endpoint = "/organizations/" + p_organizationId + "/admins/" + p_adminId
    body = {}
    for item in p_settings:
        if item != "id":
            body[item] = p_settings[item]
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response  
    
    
def getVlanSettings(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/vlans/settings"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def updateVlanSettings(p_apiKey, p_networkId, p_vlansEnabled):
    #p_vlansEnabled: boolean
    endpoint = "/networks/" + p_networkId + "/appliance/vlans/settings"
    body = {"vlansEnabled":p_vlansEnabled}
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getVlans(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/vlans"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def updateVlan(p_apiKey, p_networkId, p_vlanId, p_vlanConfiguration):
    #p_vlanConfiguration: struct
    endpoint = "/networks/" + p_networkId + "/appliance/vlans/" + str(p_vlanId)
    if "id" in p_vlanConfiguration:
        del p_vlanConfiguration["id"]
    if "networkId" in p_vlanConfiguration:
        del p_vlanConfiguration["networkId"]        
    if "fixedIpAssignments" in p_vlanConfiguration:
        if p_vlanConfiguration["fixedIpAssignments"] == {}:
            del p_vlanConfiguration["fixedIpAssignments"]
    if "reservedIpRanges" in p_vlanConfiguration:
        if p_vlanConfiguration["reservedIpRanges"] == []:
            del p_vlanConfiguration["reservedIpRanges"]
    if (not p_vlanConfiguration["dhcpBootOptionsEnabled"]) and ("dhcpOptions" in p_vlanConfiguration):
        del p_vlanConfiguration["dhcpOptions"]    
    success = True
    errors  = None
    headers = None
    response= None
    if len(p_vlanConfiguration) > 0:        
        success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_vlanConfiguration, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def createVlan(p_apiKey, p_networkId, p_vlanConfiguration):
    #p_vlanConfiguration: struct
    endpoint    = "/networks/" + p_networkId + "/appliance/vlans"
    vlanId      = p_vlanConfiguration["id"]
    body = {
        "id"    : vlanId,
        "name"  : p_vlanConfiguration["name"],
        "subnet"  : p_vlanConfiguration["subnet"],
        "applianceIp"  : p_vlanConfiguration["applianceIp"], }
    success, errors, headers, response = merakiRequest(p_apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)
    
    del p_vlanConfiguration["id"]
    del p_vlanConfiguration["name"]
    del p_vlanConfiguration["subnet"]
    del p_vlanConfiguration["applianceIp"]
    
    if success:
        success, errors, headers, response = updateVlan(p_apiKey, p_networkId, vlanId, p_vlanConfiguration)    
    return success, errors, headers, response
    
    
def deleteVlan(p_apiKey, p_networkId, p_vlanId):
    endpoint    = "/networks/" + p_networkId + "/appliance/vlans/" + str(p_vlanId)
    success, errors, headers, response = merakiRequest(p_apiKey, "DELETE", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)
    
    return success, errors, headers, response
    
    
def getSingleLan(p_apiKey, p_networkId):
    #Returns MX LAN subnet configuration when VLANs are not enabled
    endpoint = "/networks/" + p_networkId + "/appliance/singleLan"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
        
        
def updateSingleLan(p_apiKey, p_networkId, p_lanConfiguration):
    #Updates MX LAN subnet configuration when VLANs are not enabled
    endpoint = "/networks/" + p_networkId + "/appliance/singleLan"
    body = {
        "subnet": p_lanConfiguration["subnet"],
        "applianceIp": p_lanConfiguration["applianceIp"]
    }
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)
    
    return success, errors, headers, response
    
    
def getMxL3FirewallRules(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/l3FirewallRules"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    

def matchDefaultL3FirewallRule(p_rule):
    defaultRule = {
        'comment': 'Default rule',
        'policy': 'allow',
        'protocol': 'Any',
        'srcPort': 'Any',
        'srcCidr': 'Any',
        'destPort': 'Any',
        'destCidr': 'Any',
        'syslogEnabled': False
    }
    
    for item in defaultRule:
        if not item in p_rule or p_rule[item] != defaultRule[item]:
            return False
    return True
    
    
def updateMxL3FirewallRules(p_apiKey, p_networkId, p_firewallRuleset):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/l3FirewallRules"

    if matchDefaultL3FirewallRule(p_firewallRuleset["rules"][-1]):
        del p_firewallRuleset["rules"][-1]
        
    success     = True
    errors      = None
    headers     = None
    response    = None
    
    if len(p_firewallRuleset["rules"]) > 0:        
        success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_firewallRuleset, p_verbose=FLAG_REQUEST_VERBOSE)

    return success, errors, headers, response
        
        
def getMxL7FirewallRules(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/l7FirewallRules"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxL7FirewallRules(p_apiKey, p_networkId, p_firewallRuleset):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/l7FirewallRules"

    success     = True
    errors      = None
    headers     = None
    response    = None
    
    if len(p_firewallRuleset["rules"]) > 0:    
        success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_firewallRuleset, p_verbose=FLAG_REQUEST_VERBOSE)
    return success, errors, headers, response
    
    
def getMxIpsSettings(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/security/intrusion"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxIpsSettings(p_apiKey, p_networkId, p_IpsSettings):
    endpoint = "/networks/" + p_networkId + "/appliance/security/intrusion"
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_IpsSettings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def getMxAmpSettings(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/security/malware"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxAmpSettings(p_apiKey, p_networkId, p_AmpSettings):
    endpoint = "/networks/" + p_networkId + "/appliance/security/malware"
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_AmpSettings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response    


def getMxContentFilteringSettings(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/contentFiltering"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxContentFilteringSettings(p_apiKey, p_networkId, p_settings):
    #NOTE: p_settings["blockedUrlCategories"] must be in the format returned by GET /networks/{netId}/appliance/contentFiltering
    endpoint = "/networks/" + p_networkId + "/appliance/contentFiltering"
    
    itemsToDelete = []
    for item in p_settings:
        if len(p_settings[item]) == 0:
            itemsToDelete.append(item)
    for item in itemsToDelete:
        del p_settings[item]
    
    #convert blockedUrlCategories records' format from dict to str
    if "blockedUrlCategories" in p_settings:
        categoryIds = []
        for item in p_settings["blockedUrlCategories"]:
            categoryIds.append(item["id"])
        p_settings["blockedUrlCategories"] = categoryIds
                
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_settings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response    
    
        
def createNetwork(p_apiKey, p_organizationId, p_networkName, p_productTypes, p_timeZone=None, p_tags=None, p_copyFromNetworkId=None):
    endpoint = "/organizations/" + p_organizationId + "/networks"
    body = {
        "name"          : p_networkName,
        "productTypes"  : p_productTypes
    }
    if not p_copyFromNetworkId is None:
        body["copyFromNetworkId"] = p_copyFromNetworkId
    if not p_timeZone is None:
        body["timeZone"] = p_timeZone
    if not p_tags is None:
        body["tags"] = p_tags        
    success, errors, headers, response = merakiRequest(p_apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getGroupPolicies(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/groupPolicies"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def createGroupPolicy(p_apiKey, p_networkId, p_policy):
    endpoint = "/networks/" + p_networkId + "/groupPolicies"
    body = {}
    for item in p_policy:
        if item != "groupPolicyId":
            body[item] = p_policy[item]
          
    success, errors, headers, response = merakiRequest(p_apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
         
    
def getNewPolicyIdForOldId(p_oldId, p_oldPolicies, p_newPolicies):
    name = None
    for policy in p_oldPolicies:
        if policy["groupPolicyId"] == p_oldId:
            name = policy["name"]
            break
    if not name is None:
        for policy in p_newPolicies:
            if policy["name"] == name:
                return policy["groupPolicyId"]
    return None
    
    
def getMxStaticRoutes(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/staticRoutes"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def createMxStaticRoute(p_apiKey, p_networkId, p_route):
    endpoint = "/networks/" + p_networkId + "/appliance/staticRoutes"
    body = {}
    for item in p_route:
        if item != "id":
            body[item] = p_route[item]
          
    success, errors, headers, response = merakiRequest(p_apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getMxTrafficShapingRules(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/trafficShaping/rules"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxTrafficShapingRules(p_apiKey, p_networkId, p_settings):
    endpoint = "/networks/" + p_networkId + "/appliance/trafficShaping/rules"                    
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_settings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response   
    
    
def getMxOneToOneNatRules(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/oneToOneNatRules"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxOneToOneNatRules(p_apiKey, p_networkId, p_settings):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/oneToOneNatRules"                    
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_settings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response  


def getMxOneToManyNatRules(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/oneToManyNatRules"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxOneToManyNatRules(p_apiKey, p_networkId, p_settings):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/oneToManyNatRules"                    
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_settings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response  
    
    
def getMxPortForwardingRules(p_apiKey, p_networkId):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/portForwardingRules"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response
    
    
def updateMxPortForwardingRules(p_apiKey, p_networkId, p_settings):
    endpoint = "/networks/" + p_networkId + "/appliance/firewall/portForwardingRules"                    
    success, errors, headers, response = merakiRequest(p_apiKey, "PUT", endpoint, p_requestBody=p_settings, p_verbose=FLAG_REQUEST_VERBOSE) 
    return success, errors, headers, response  
    
    
def getOrganizationIdWithName(p_apiKey, p_organizationName):
    success, errors, headers, response = getOrganizations(p_apiKey)
    if not response is None:
        for org in response:
            if org["name"] == p_organizationName:
                return org["id"]
        print("%-30s %s" %("Organization ID","Organization Name"))
        for org in response:
            print('%-30s "%s"' %(org["id"],org["name"]))
    return None
        
    
def printHelpAndExit():
    print(readMe)
    sys.exit(0)
    
    
def killScript():
    print("ERROR: Execution interrupted.")
    sys.exit(2)
    
    
def findUniqueNewNetName(p_sourceNetName, p_orgNetworks):
    newNameRoot = p_sourceNetName + " - NO TEMPLATE"
    newName = newNameRoot
    doLoop = True
    maxIterations = 100
    i = 2    
    while(doLoop):
        doLoop = False
        networkIsUnique = True
        for net in p_orgNetworks:
            if net["name"] == newName:
                networkIsUnique = False
                break
        if networkIsUnique:
            return newName
        else:
            newName = newNameRoot + " " + str(i)
        i += 1
        if i < maxIterations:
            doLoop = True
    return None
    

def main(argv):
    #set default values for command line arguments
    arg_apiKey          = None
    arg_orgName         = None
    arg_sourceNetName   = None
    
    try:
        opts, args = getopt.getopt(argv, 'hk:o:n:')
    except getopt.GetoptError:
        printHelpAndExit()
    
    for opt, arg in opts:
        if opt == '-h':
            printHelpAndExit()
        elif opt == '-k':
            arg_apiKey          = arg
        elif opt == '-o':
            arg_orgName         = arg
        elif opt == '-n':
            arg_sourceNetName   = arg  
        
    if arg_apiKey is None or arg_orgName is None or arg_sourceNetName is None:
        printHelpAndExit()
    
    orgId = getOrganizationIdWithName(arg_apiKey, arg_orgName)
    
    if orgId is None:
        print('ERROR: No organization found with name "%s"' % arg_orgName)
        killScript()
        
    #find network
    success, errors, headers, orgNetworks = getNetworks(arg_apiKey, orgId)
    
    if orgNetworks is None:
        print("ERROR: Unable to fetch networks' list")
        killScript()
    
    sourceNet = None
    for net in orgNetworks:
        if net["name"] == arg_sourceNetName:
            sourceNet = net
        
    if sourceNet is None:
        print('ERROR: No network found with name "%s"' % arg_sourceNetName)
        killScript()
        
    if not "appliance" in sourceNet["productTypes"]:
        print('ERROR: Source network needs to have security appliance configuration')
        killScript()
    
    newNetName = findUniqueNewNetName(arg_sourceNetName, orgNetworks)
    
    if newNetName is None:
        print('ERROR: Unable to create unique new network name')
        killScript()
        
    #create new network
    success, errors, headers, newNetwork = createNetwork(arg_apiKey, orgId, newNetName, sourceNet["productTypes"], 
        p_timeZone=sourceNet["timeZone"], p_tags=sourceNet["tags"])
        
    if newNetwork is None:
        print('ERROR: Unable to create new network with name', newNetName)
        killScript()    
        
    #- Copy Group policies
    success, errors, headers, sourceGroupPolicies = getGroupPolicies(arg_apiKey, sourceNet["id"])
        
    newGroupPolicies = []
    
    if not sourceGroupPolicies is None:
        for policy in sourceGroupPolicies:
            success, errors, headers, response = createGroupPolicy(arg_apiKey, newNetwork["id"], policy)
            if not response is None:
                newGroupPolicies.append(response)
        
    #- Copy VLANs and IP addressing
    success, errors, headers, response = getVlanSettings(arg_apiKey, sourceNet["id"])
    
    if not response is None:
        if response["vlansEnabled"]:
            success, errors, headers, response = updateVlanSettings(arg_apiKey, newNetwork["id"], True)
            
            if not response is None:
                if response["vlansEnabled"]:
                    success, errors, headers, sourceVlans = getVlans(arg_apiKey, sourceNet["id"])
                    
                    if not sourceVlans is None:
                        noConfigForVlanOne = True
                        for vlan in sourceVlans:
                            if "groupPolicyId" in vlan:
                                policyId = getNewPolicyIdForOldId(vlan["groupPolicyId"], sourceGroupPolicies, newGroupPolicies)
                                if not policyId is None:
                                    vlan["groupPolicyId"] = policyId
                                else:
                                    print("WARNING: Please check that VLAN group policies of new network are correct!")
                            if int(vlan["id"]) == 1:                       
                                updateVlan(arg_apiKey, newNetwork["id"], vlan["id"], vlan)
                                noConfigForVlanOne = False
                            else:
                                createVlan(arg_apiKey, newNetwork["id"], vlan)
                        if noConfigForVlanOne:
                            deleteVlan(arg_apiKey, newNetwork["id"], 1)
        else:
            #Source does not have VLANs enabled. Copy the single subnet parameters
            success, errors, headers, response = getSingleLan(arg_apiKey, sourceNet["id"])
            if not response is None:
                updateSingleLan(arg_apiKey, newNetwork["id"], response)                               
    else:
        print("WARNING: Skipping copying VLAN settings: Could not check if enabled")
        
    #- Copy L3 Firewall Rules
    success, errors, headers, sourceRules = getMxL3FirewallRules(arg_apiKey, sourceNet["id"])
    if not sourceRules is None:
        updateMxL3FirewallRules(arg_apiKey, newNetwork["id"], sourceRules)
        
    #- L7 Firewall Rules
    success, errors, headers, sourceRules = getMxL7FirewallRules(arg_apiKey, sourceNet["id"]) 
    if not sourceRules is None:
        if sourceRules["rules"] != []:
            updateMxL7FirewallRules(arg_apiKey, newNetwork["id"], sourceRules)
        
    #- Copy Threat Protection
    success, errors, headers, sourceRules = getMxIpsSettings(arg_apiKey, sourceNet["id"])
    if not sourceRules is None:
        updateMxIpsSettings(arg_apiKey, newNetwork["id"], sourceRules)
        
    success, errors, headers, sourceRules = getMxAmpSettings(arg_apiKey, sourceNet["id"])
    if not sourceRules is None:
        updateMxAmpSettings(arg_apiKey, newNetwork["id"], sourceRules)
    
    #- Content Filtering
    success, errors, headers, sourceRules = getMxContentFilteringSettings(arg_apiKey, sourceNet["id"])
    if not sourceRules is None:
        updateMxContentFilteringSettings(arg_apiKey, newNetwork["id"], sourceRules)
        
    #- Traffic Shaping
    success, errors, headers, sourceRules = getMxTrafficShapingRules(arg_apiKey, sourceNet["configTemplateId"])
    if not sourceRules is None:
        updateMxTrafficShapingRules(arg_apiKey, newNetwork["id"], sourceRules)
        
    #- Port forwarding NAT rules
    success, errors, headers, sourceRules = getMxPortForwardingRules(arg_apiKey, sourceNet["configTemplateId"])
    if not sourceRules is None and sourceRules != []:
        updateMxPortForwardingRules(arg_apiKey, newNetwork["id"], sourceRules)
        
    #- 1-to-1 NAT rules
    success, errors, headers, sourceRules = getMxOneToOneNatRules(arg_apiKey, sourceNet["configTemplateId"])
    if not sourceRules is None and sourceRules != []:
        updateMxOneToOneNatRules(arg_apiKey, newNetwork["id"], sourceRules)
        
    #- 1-to-many NAT rules
    success, errors, headers, sourceRules = getMxOneToManyNatRules(arg_apiKey, sourceNet["configTemplateId"])
    if not sourceRules is None and sourceRules != []:
        updateMxOneToManyNatRules(arg_apiKey, newNetwork["id"], sourceRules)
    
    #- Copy Admin accounts
    success, errors, headers, response = getAdministrators(arg_apiKey, orgId)
    for admin in response:
        if "networks" in admin:
            for net in admin["networks"]:
                if net["id"] == sourceNet["id"]:
                    privilege = {
                        "id"        : newNetwork["id"],
                        "access"    : net["access"]
                    }
                    admin["networks"].append(privilege)
                    updateAdministrator(arg_apiKey, orgId, admin["id"], admin)
    
    #- Copy Static Routes
    success, errors, headers, response = getMxStaticRoutes(arg_apiKey, sourceNet["id"])
    for route in response:
        gatewayIpResolvedCorrectly = False
        try:
            #At time of writing, the GET staticRoutes endpoint has a bug that can return an invalid gatewayIp
            #If this bug is detected, skip processing of invalid route and print a warning
            ipValidationCheck = ipaddress.ip_address(route["gatewayIp"])
            gatewayIpResolvedCorrectly = True
        except:
            print("WARNING: Skipping route: Invalid route gateway IP address")
        if gatewayIpResolvedCorrectly:
            createMxStaticRoute(arg_apiKey, newNetwork["id"], route)
        
    print('\nCreated network "%s"' % newNetName)
    
    print("End of script.")
    
if __name__ == '__main__':
    main(sys.argv[1:])