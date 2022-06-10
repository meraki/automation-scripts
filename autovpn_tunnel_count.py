readMe = '''
This script calculates how many tunnels the current Auto VPN topology is consuming in each appliance.
The intention is to help with assessing scaling and hardware upgrade planning.

Syntax, Windows:
    python autovpn_tunnel_count.py [-k <api_key>] [-o <org_name>] [-n <net_name>]

Syntax, Linux and Mac:
    python3 autovpn_tunnel_count.py [-k <api_key>] [-o <org_name>] [-n <net_name>]
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, the script will try to use one stored in
                        OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org_name>       The name of the organization to calculate tunnels for. This parameter can be 
                        omitted if your API key can only access one org. Use keyword "/all" instead of a name
                        to fetch information for all organizations accessible by your API key
    -n <net_name>    Only display results for network with specified name. If omitted, all networks will
                        be displayed                        
                        
Example, calculate tunnel counts for organization with name Big Industries Inc:
    python autovpn_tunnel_count.py -k 1234 -o "Big Industries Inc"
    
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
    
# getNetworkApplianceVpnSiteToSiteVpn
#
# Description: Return the site-to-site VPN settings of a network. Only valid for MX networks.
# Endpoint: GET /networks/{networkId}/appliance/vpn/siteToSiteVpn
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-vpn-site-to-site-vpn

def getNetworkApplianceVpnSiteToSiteVpn(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/vpn/siteToSiteVpn"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getOrganizationUplinksStatuses
#
# Description: List the uplink status of every Meraki MX, MG and Z series devices in the organization
# Endpoint: GET /organizations/{organizationId}/uplinks/statuses
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-uplinks-statuses
#
# Query parameters:
#     perPage: Integer. The number of entries per page returned. Acceptable range is 3 - 1000. Default is 1000.
#     startingAfter: String. A token used by the server to indicate the start of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     endingBefore: String. A token used by the server to indicate the end of the page. Often this is a timestamp or an ID but it is not limited to those. This parameter should not be defined by client applications. The link for the first, last, prev, or next page in the HTTP Link header should define it.
#     networkIds: Array. A list of network IDs. The returned devices will be filtered to only include these networks.
#     serials: Array. A list of serial numbers. The returned devices will be filtered to only include these serials.
#     iccids: Array. A list of ICCIDs. The returned devices will be filtered to only include these ICCIDs.

def getOrganizationUplinksStatuses(apiKey, organizationId, query=None):
    url = "/organizations/" + str(organizationId) + "/uplinks/statuses"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
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
    
def getApiKey(argument):
    if not argument is None:
        return str(argument)
    apiKey = os.environ.get(API_KEY_ENV_VAR_NAME, None) 
    if apiKey is None:
        killScript()
    else:
        return apiKey
        
def printLine(line):
    elements = {
        "name"      : 48,
        "mode"      : 12,
        "count"     : 20  
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
    
        
def main(argv):    
    arg_apiKey      = None
    arg_orgName     = None
    arg_netName     = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:s:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        elif opt == '-o':
            arg_orgName     = str(arg)
        elif opt == '-n':
            arg_netName     = str(arg)
        elif opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    
    if apiKey is None:
        killScript("No API key provided")
        
    success, errors, allOrgs = getOrganizations(apiKey)
    
    if allOrgs is None:
        killScript("Unable to fetch organizations for that API key")
    
    organizations       = []
    
    if arg_orgName is None:
        if len(allOrgs) == 1:
            organizations.append(allOrgs[0])
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
        success, errors, applianceNets = getOrganizationNetworks(apiKey, org["id"], query={"productTypes":['appliance']})
        if applianceNets is None:
            log('ERROR: Unable to fetch networks for org "%s"' % org['name'])
            continue
        if len(applianceNets) == 0:
            log('INFO: Skipping org "%s": No appliance networks' % org['name'])
            continue
            
        networkUplinkCounts = {}
            
        success, errors, rawUplinkStatuses = getOrganizationUplinksStatuses(apiKey, org["id"])
        if applianceNets is None:
            log('ERROR: Unable to fetch appliance uplink statuses for org "%s"' % org['name'])
            continue
        for device in rawUplinkStatuses:
            model = device['model'].lower()
            uplinkCount = 0
            if model.startswith('mx') or model.startswith('vmx') or model.startswith('z'):
                for uplink in device['uplinks']:
                    if uplink['status'] == "active":
                        uplinkCount += 1
            
            if not (device['networkId'] in networkUplinkCounts) or networkUplinkCounts[device['networkId']] < uplinkCount:
                networkUplinkCounts[device['networkId']] = uplinkCount
                          
        fetchingVpnSettingsFailed   = False
        networkTunnelCounts         = {}
        
        for net in applianceNets:
            success, errors, vpnSettings = getNetworkApplianceVpnSiteToSiteVpn(apiKey, net['id'])
            if vpnSettings is None:
                log('ERROR: Unable to fetch VPN settings for net "%s"' % net['name'])
                fetchingVpnSettingsFailed = True
                continue            
            net['vpnMode'] = vpnSettings['mode']
            if vpnSettings['mode'] == "spoke":
                for hub in vpnSettings['hubs']:
                    pairTunnels = 0
                    if net['id'] in networkUplinkCounts and hub['hubId'] in networkUplinkCounts:
                        pairTunnels = networkUplinkCounts[net['id']] * networkUplinkCounts[hub['hubId']]
                    if pairTunnels > 0:
                        if not net['id'] in networkTunnelCounts:
                            networkTunnelCounts[net['id']] = {'mode': 'spoke', 'count': 0}
                        networkTunnelCounts[net['id']]['count'] += pairTunnels
                        if not hub['hubId'] in networkTunnelCounts:
                            networkTunnelCounts[hub['hubId']] = {'mode': 'hub', 'count': 0}
                        networkTunnelCounts[hub['hubId']]['count'] += pairTunnels
            elif vpnSettings['mode'] == "hub":
                for peer in networkTunnelCounts:
                    if networkTunnelCounts[peer]['mode'] == "hub":
                        pairTunnels = 0
                        if (net['id'] != peer) and (net['id'] in networkUplinkCounts) and (peer in networkUplinkCounts):
                            pairTunnels = networkUplinkCounts[net['id']] * networkUplinkCounts[peer]
                        if pairTunnels > 0:
                            if not net['id'] in networkTunnelCounts:
                                networkTunnelCounts[net['id']] = {'mode': 'spoke', 'count': 0}
                            networkTunnelCounts[net['id']]['count'] += pairTunnels                        
                            networkTunnelCounts[peer]['count']      += pairTunnels
                
        if fetchingVpnSettingsFailed:
            continue
            
        print('\n--- Tunnel counts for organization "%s" ---\n' % org['name'])
        printLine({"name": "Network name", "mode": "Mode", "count": "Tunnel count"})
        for net in applianceNets:
            if net['id'] in networkTunnelCounts:
                printLine({
                        'name'  : net['name'], 
                        'mode'  : networkTunnelCounts[net['id']]['mode'],
                        'count' : networkTunnelCounts[net['id']]['count']
                    })
            

if __name__ == '__main__':
    main(sys.argv[1:])
