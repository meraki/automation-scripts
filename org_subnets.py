readMe = '''
This script prints a list of all subnets configured to MX security appliances as VLANs, static routes
or VPN advertisements.

Syntax, Windows:
    python org_subnets.py [-k <api_key>] [-o <org_name>]
    

Syntax, Linux and Mac:
    python3 org_subnets.py [-k <api_key>] [-o <org_name>]
    
Parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, the script will try to use one stored in
                        OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org_name>       The name of the organization to print subnet info for. This parameter can be 
                        omitted if your API key can only access one org. Use keyword "/all" instead of a name
                        to fetch information for all organizations accessible by your API key
                        
Example, print subnet info for organization with name Big Industries Inc:
    python org_subnets.py -k 1234 -o "Big Industries Inc"
    
'''

import sys, getopt, os, datetime, re

def printHelp():
    print(readMe)
    
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
    
# getNetworkApplianceVlans
#
# Description: List the VLANs for an MX network
# Endpoint: GET /networks/{networkId}/appliance/vlans
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-vlans

def getNetworkApplianceVlans(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/vlans"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceStaticRoutes
#
# Description: List the static routes for an MX or teleworker network
# Endpoint: GET /networks/{networkId}/appliance/staticRoutes
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-static-routes

def getNetworkApplianceStaticRoutes(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/staticRoutes"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceSingleLan
#
# Description: Return single LAN configuration
# Endpoint: GET /networks/{networkId}/appliance/singleLan
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-single-lan

def getNetworkApplianceSingleLan(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/singleLan"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceVpnAdvertisements
#
# Description: Return the site-to-site advertised routes(local networks). Only valid for MX networks in Passthrough mode.
# Endpoint: GET /networks/{networkId}/appliance/vpn/advertisements
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-vpn-advertisements

def getNetworkApplianceVpnAdvertisements(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/vpn/advertisements"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceSettings
#
# Description: Return the appliance settings for a network
# Endpoint: GET /networks/{networkId}/appliance/settings
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-settings

def getNetworkApplianceSettings(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/settings"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
def printLine(line):
    elements = {
        "subnet"    : 20,
        "orgName"   : 21,
        "netName"   : 24,
        "type"      : 8,
        "name"      : 20,
        "vlanId"    : 10,
        "nextHop"   : 16  
    }
    
    formatString    = ""
    tupleList       = []
    
    for label in elements:
        formatString += "%-" + str(elements[label]) + "s"
        if label in line:
            tupleList.append(str(line[label])[:elements[label]-1])
        else:
            tupleList.append("")
            
    print(formatString % tuple(tupleList))       
    
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
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        elif opt == '-o':
            arg_orgName     = str(arg)
        elif opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    
    if apiKey is None:
        killScript("No API key provided")
        
    success, errors, allOrgs = getOrganizations(apiKey)
    
    if allOrgs is None:
        killScript("Unable to fetch organizations for that API key")
    
    organizations       = []
    
    organizationId      = None
    organizationName    = ""
    
    if arg_orgName is None:
        if len(allOrgs) == 1:
            organizationId      = allOrgs[0]['id']
            organizationName    = allOrgs[0]['name']
        else:
            killScript("Organization name required for this API key")             
    else:
        for org in allOrgs:
            if arg_orgName == "/all":
                organizations.append(org)
            elif org["name"] == arg_orgName:
                organizations.append(org)
                break
                
    if len(organizations) == 0:
        killScript("No matching organizations")

    for org in organizations:
        org['networks'] = []
        success, errors, allNets = getOrganizationNetworks(apiKey, org['id'])
        
        if not allNets is None:
            for net in allNets:
                if 'appliance' in net['productTypes']:
                    org['networks'].append(net)
       
    for org in organizations:
        for net in org['networks']:
            net['singleLan']            = None
            net['vlans']                = []
            net['routes']               = []
            net['vpnAdvertisements']    = []
            
            print("Processing: %s > %s" % (org['name'], net["name"]))
                        
            success, errors, singleLan = getNetworkApplianceSingleLan(apiKey, net['id'])            
            if not singleLan is None:
                net['singleLan'] = singleLan
        
            success, errors, allVlans = getNetworkApplianceVlans(apiKey, net['id'])            
            if not allVlans is None:
                net['vlans'] = allVlans
                
            success, errors, allRoutes = getNetworkApplianceStaticRoutes(apiKey, net['id'])            
            if not allRoutes is None:
                net['routes'] = allRoutes
        
            success, errors, allVpnAdverts = getNetworkApplianceVpnAdvertisements(apiKey, net['id'])            
            if not allVpnAdverts is None:
                net['vpnAdvertisements'] = allVpnAdverts['routes']
                
    subnets = {}
                
    for org in organizations:
        for net in org['networks']:
            if not net['singleLan'] is None:
                s = net['singleLan']['subnet']
                if not s in subnets:
                    subnets[s] = []
                sInfo = {
                        'type'      : 'lan',
                        'orgId'     : org['id'],
                        'orgName'   : org['name'],
                        'netId'     : net['id'],
                        'netName'   : net['name']
                    }
                subnets[s].append(sInfo)
                
            for vlan in net['vlans']:
                s = vlan['subnet']
                if not s in subnets:
                    subnets[s] = []
                sInfo = {
                        'type'      : 'vlan',
                        'orgId'     : org['id'],
                        'orgName'   : org['name'],
                        'netId'     : net['id'],
                        'netName'   : net['name'],
                        'vlanId'    : vlan['id'],
                        'vlanName'  : vlan['name']
                    }
                subnets[s].append(sInfo)
            
            for route in net['routes']:
                s = route['subnet']
                if not s in subnets:
                    subnets[s] = []
                sInfo = {
                        'type'      : 'route',
                        'orgId'     : org['id'],
                        'orgName'   : org['name'],
                        'netId'     : net['id'],
                        'netName'   : net['name'],
                        'gatewayIp' : route['gatewayIp']
                    }
                subnets[s].append(sInfo)
                
            for vpnAdvert in net['vpnAdvertisements']:
                s = vpnAdvert['subnet']
                if not s in subnets:
                    subnets[s] = []
                sInfo = {
                        'type'              : 'vpnAdv',
                        'orgId'             : org['id'],
                        'orgName'           : org['name'],
                        'netId'             : net['id'],
                        'netName'           : net['name'],
                        'advertisementName' : vpnAdvert['name']
                    }
                subnets[s].append(sInfo)
    
    # https://stackoverflow.com/questions/55228797/how-to-sort-a-list-of-lists-with-ip-subnets-python
    rawSubnets      = []
    sortedSubnets   = []
    for subnet in subnets:
        rawSubnets.append(subnet)
    sortedSubnets = sorted(rawSubnets,key=lambda x : [int(m) for m in re.findall("\d+",x)])
    
    header = {
        "subnet"    : "Subnet",
        "orgName"   : "Organization",
        "netName"   : "Network",
        "type"      : "Type",
        "name"      : "VLAN/route name",
        "vlanId"    : "VLAN ID",
        "nextHop"   : "Next hop"        
    }
    
    print('\n---\n')
    printLine(header)
    
    for s in sortedSubnets:
        for instance in subnets[s]:
            line = {
                "subnet"    : s,
                "orgName"   : instance['orgName'],
                "netName"   : instance['netName'],
                "type"      : instance['type']   
            }
            if 'advertisementName' in instance:
                line['name']    = instance['advertisementName']
            if 'vlanName' in instance:
                line['name']    = instance['vlanName']
            if 'vlanId' in instance:
                line['vlanId']  = instance['vlanId']
            if 'gatewayIp' in instance:
                line['nextHop'] = instance['gatewayIp']
                
            printLine(line)

if __name__ == '__main__':
    main(sys.argv[1:])
