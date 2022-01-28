readMe = '''
This is a Python 3 script to migrate crypto map based site-to-site VPN configuration to a Meraki MX
security appliance. The VPN configuration will be ported as third-party VPN tunnels in the target 
Meraki Dashboard organization and associated with the chosen network tag. The script has been tested
to work with ASA firmware 9.8(4)20. The script only migrates enabled tunnels.

To use this script:
  * Enable site-to-site VPN on the target MX's and associate them with network tags if needed
  * On the source ASA, run a "show run-config" and save the output into a text file
  * Then run the script using the syntax below:

Windows:
    python asa_cryptomap_converter.py [-k <api_key>] [-o <org_name>] [-f <file_name>] [-t <tag>]
    
Linux and Mac:
    python3 asa_cryptomap_converter.py [-k <api_key>] [-o <org_name>] [-f <file_name>] [-t <tag>]
    
Optional arguments:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, the script will try to use one stored in
                        OS environment variable MERAKI_DASHBOARD_API_KEY
    -o <org_name>       The name of the organization to pull the OpenAPI spec from. This parameter can be 
                        omitted if your API key can only access one organization
    -f <file_name>      The name of the ASA configuration input file. If omitted, "asa.cfg" will be used
                        as default
    -t <tag>            The name of the network tag you want to make the converted tunnels available to. If
                        omitted, default availability is "All networks"
                        
Example, convert configuration stored in file "asa.cfg" into organization with name "Big Industries Inc" and
make it available to MXs in networks tagged "asa-vpn"
    python asa_cryptomap_converter.py -k 1234 -o "Big Industries Inc" -t asa-vpn
    
Required Python 3 modules:
    requests

To install these Python 3 modules via pip you can use the following commands:
    pip install requests

Depending on your operating system and Python environment, you may need to use commands 
"python3" and "pip3" instead of "python" and "pip".    
'''

import os, sys, getopt, time, datetime

import asa_config_parser_module as configParser

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

ASA_TO_MX_PROTOCOL_LABELS = {
    'encryption': {
        '3des'      : 'tripledes',
        'aes'       : 'aes128',
        'aes-192'   : 'aes192',
        'aes-256'   : 'aes256'
    },
    'integrity': {
        'md5'       : 'md5',
        'sha-1'     : 'sha1',
        'sha-256'   : 'sha256'
    },
    'keyExchangeGroups': [
        1, 2, 5, 14
    ]
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
    
    
def getOrganizations(apiKey):
    url = "/organizations"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
def getOrganizationApplianceVpnThirdPartyVPNPeers(apiKey, organizationId):
    url = "/organizations/" + str(organizationId) + "/appliance/vpn/thirdPartyVPNPeers"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# updateOrganizationApplianceVpnThirdPartyVPNPeers
#
# Description: Update the third party VPN peers for an organization
# Endpoint: PUT /organizations/{organizationId}/appliance/vpn/thirdPartyVPNPeers
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-organization-appliance-vpn-third-party-vpn-peers
#
# Request body schema:
#     peers: Array. The list of VPN peers    
    
def updateOrganizationApplianceVpnThirdPartyVPNPeers(apiKey, organizationId, body=None):
    url = "/organizations/" + str(organizationId) + "/appliance/vpn/thirdPartyVPNPeers"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
       
  
def loadFile(filename):
    try:
        with open(filename, 'r') as file:
            data = file.read()
        return data
    except:
        return None
  
def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get(API_KEY_ENV_VAR_NAME, None) 
        
def killScript(reason=None):
    if reason is None:
        print(readMe)
        sys.exit()
    else:
        log("ERROR: %s" % reason)
        sys.exit()
        
def log(text, filePath=None):
    logString = "%s -- %s" % (str(datetime.datetime.now())[:19], text)
    print(logString)
    if not filePath is None:
        try:
            with open(filePath, "a") as logFile:
                logFile.write("%s\n" % logString)
        except:
            log("ERROR: Unable to append to log file")
    
    
def asaRawConfigToDict(rawConfig):
    result = configParser.parse(rawConfig)
    return result
    

def createThirdPartyVpnLineForPeer(peerId):
    return None
    
    
def extractIkev1Parameters(labels, transformSetDict):
    return None
    
            
def main(argv):    
    arg_apiKey      = None
    arg_orgName     = None
    arg_fileName    = "asa.cfg"
    arg_tag         = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:f:t:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        elif opt == '-o':
            arg_orgName     = str(arg)
        elif opt == '-f':
            arg_fileName    = str(arg)
        elif opt == '-t':
            arg_tag         = str(arg)
        elif opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    if apiKey is None:
        killScript()
        
    rawConfig = loadFile(arg_fileName)
    if rawConfig is None:
        killScript('Unable to read source file "%s"' % arg_fileName)
        
    parsedConfig            = asaRawConfigToDict(rawConfig)
    
    cryptoMaps              = {}
    if 'cryptoMaps' in parsedConfig['vpn']:
        cryptoMaps          = parsedConfig['vpn']['cryptoMaps']
        
    cryptoDynamicMaps       = {}
    if 'cryptoDynamic-maps' in parsedConfig['vpn']:
        cryptoDynamicMaps   = parsedConfig['vpn']['cryptoDynamic-maps']
            
    ikev1TransformSets      = parsedConfig['vpn']['ikev1']['transformSets']
    ikev2Proposals          = parsedConfig['vpn']['ikev2']['proposals']
    tunnelGroups            = parsedConfig['vpn']['tunnel-groups']
    acls                    = parsedConfig['acls']
    networkObjects          = parsedConfig['networkObjects']
    networkObjectGroups     = parsedConfig['networkObjectGroups']
    
    defaultTunnelLifetime   = 28800
    if 'defaultTunnelLifetimeSeconds' in parsedConfig['vpn']:
        defaultTunnelLifetime = parsedConfig['vpn']['defaultTunnelLifetimeSeconds']
    
    success, errors, allOrgs = getOrganizations(apiKey)
    
    if allOrgs is None:
        killScript("Unable to fetch organizations for that API key")
    
    organizationId      = None
    organizationName    = ""
    
    if arg_orgName is None:
        if len(allOrgs) == 1:
            organizationId      = allOrgs[0]['id']
            organizationName    = allOrgs[0]['name']
        else:
            killScript('Parameter "-o <org_name>" required for this API key')             
    else:
        for org in allOrgs:
            if org["name"] == arg_orgName:
                organizationId      = org['id']
                organizationName    = org['name']
                break
    if organizationId is None:
        killScript("No matching organizations")
        
    log('Using organization %s "%s"' % (organizationId, organizationName))
    
    success, errors, oldVpnConfig = getOrganizationApplianceVpnThirdPartyVPNPeers(apiKey, organizationId)
    
    newPeers = []
        
    for cmap in cryptoMaps:
        if not cryptoMaps[cmap]['interface'] is None:
            isakmpSettings = {
                'ikev1': [],
                'ikev2': []
            }
            if 'ipsec-isakmp' in cryptoMaps[cmap]:
                if 'type' in cryptoMaps[cmap]['ipsec-isakmp']:
                    if cryptoMaps[cmap]['ipsec-isakmp']['type'] == 'dynamic':
                        label = cryptoMaps[cmap]['ipsec-isakmp']['value']
                        if label in cryptoDynamicMaps:
                            if 'ikev1' in cryptoDynamicMaps[label]:
                                for tset in cryptoDynamicMaps[label]['ikev1']['transform-set']:
                                    if tset in ikev1TransformSets:
                                        isakmpSettings['ikev1'].append(ikev1TransformSets[tset])
                            if 'ikev2' in cryptoDynamicMaps[label]:
                                for tset in cryptoDynamicMaps[label]['ikev2']['ipsec-proposal']:
                                    if tset in ikev2Proposals:
                                        isakmpSettings['ikev2'].append(ikev2Proposals[tset])
            
            for line in cryptoMaps[cmap]['rules']:
                if 'peer' in cryptoMaps[cmap]['rules'][line]:
                    peer            = cryptoMaps[cmap]['rules'][line]['peer']
                    name            = "Crypto map %s" % peer
                    lanToLan        = False
                    version         = None
                    psk             = None
                    phase1          = None
                    phase2          = {
                                        'encryption': [],
                                        'integrity' : []
                                    }
                    dhGroup         = 14
                    pfsGroup        = None
                    lifetime        = defaultTunnelLifetime
                    privateSubnets  = []
                    if 'lifetime' in cryptoMaps[cmap]['rules'][line]:
                        lifetime    = cryptoMaps[cmap]['rules'][line]['lifetime']
                    if 'ikev1' in cryptoMaps[cmap]['rules'][line]:
                        version     = 'ikev1'
                        for tset in cryptoMaps[cmap]['rules'][line]['ikev1']['transform-set']:
                            if tset in ikev1TransformSets:
                                unpacked = ikev1TransformSets[tset]
                                if not unpacked['encryption'] in phase2['encryption']:
                                    if unpacked['encryption'] in ASA_TO_MX_PROTOCOL_LABELS['encryption']:
                                        phase2['encryption'].append(unpacked['encryption'])
                                    else:
                                        log('WARNING: Peer %s: Removing incompatible Phase 2 encryption algorithm %s' % (peer, unpacked['encryption'].upper()))
                                if not unpacked['integrity'] in phase2['integrity']:
                                    if unpacked['integrity'] in ASA_TO_MX_PROTOCOL_LABELS['integrity']:
                                        phase2['integrity'].append(unpacked['integrity'])
                                    else:
                                        log('WARNING: Peer %s: Removing incompatible Phase 2 integrity algorithm %s' % (peer, unpacked['integrity'].upper()))
                    if 'ikev2' in cryptoMaps[cmap]['rules'][line]:
                        version     = 'ikev2'
                        proposal    = cryptoMaps[cmap]['rules'][line]['ikev2']['ipsec-proposal']
                        if proposal in ikev2Proposals:
                            unpacked = ikev2Proposals[proposal]
                            if not unpacked['encryption'] in phase2['encryption']:
                                phase2['encryption'].append(unpacked['encryption'])
                            if not unpacked['integrity'] in phase2['integrity']:
                                phase2['integrity'].append(unpacked['integrity'])
                                
                    if 'matchAddress' in cryptoMaps[cmap]['rules'][line]:
                        aclName = cryptoMaps[cmap]['rules'][line]['matchAddress']
                        if aclName in acls:
                            for rule in acls[aclName]['rules']:
                                if rule['action'] == 'permit':
                                    objectsToProcess = []
                                    if rule['destination']['type'] == 'object':
                                        objectsToProcess.append(rule['destination']['value'])
                                    elif rule['destination']['type'] == 'objectGroup':
                                        objectGroupName = rule['destination']['value']
                                        if objectGroupName in networkObjectGroups:
                                            for groupMember in networkObjectGroups[objectGroupName]['items']:
                                                if groupMember['type'] == 'object':
                                                    objectsToProcess.append(groupMember['value'])
                                    for objectName in objectsToProcess:
                                        if objectName in networkObjects:
                                            for subnet in networkObjects[objectName]['items']:
                                                privateSubnets.append(str(subnet))
                                        
                                    
                        
                    if isakmpSettings[version] != []:
                        phase1      = isakmpSettings[version][0]
                        
                    if 'pfsGroup' in cryptoMaps[cmap]['rules'][line]:
                        pfsGroup = cryptoMaps[cmap]['rules'][line]['pfsGroup']
                        
                    if peer in tunnelGroups:
                        if tunnelGroups[peer]['type'] == 'ipsec-l2l':
                            if version == 'ikev1' and 'pre-shared-key' in tunnelGroups[peer]['ipsec-attributes']['ikev1']:
                                psk = tunnelGroups[peer]['ipsec-attributes']['ikev1']['pre-shared-key']
                            if version == 'ikev2' and tunnelGroups[peer]['ipsec-attributes']['ikev2']['remote-authentication']['type'] == 'pre-shared-key':
                                psk = tunnelGroups[peer]['ipsec-attributes']['ikev2']['remote-authentication']['value']
                    
                    flag_tunnelIsCompatible = True
                    
                    if psk is None:
                        log('WARNING: Skipping tunnel to peer %s: No pre-shared-key' % peer)
                        flag_tunnelIsCompatible = False
                        
                    if phase1 is None:
                        log('WARNING: Skipping tunnel to peer %s: No Phase 1 configuration' % peer)
                        flag_tunnelIsCompatible = False
                        
                    if not phase1['encryption'] in ASA_TO_MX_PROTOCOL_LABELS['encryption']:
                        log('WARNING: Skipping tunnel to peer %s: Phase 1 encryption %s not supported' % (peer, phase1['encryption'].upper()))
                        flag_tunnelIsCompatible = False
                            
                    if not phase1['integrity'] in ASA_TO_MX_PROTOCOL_LABELS['integrity']:
                        log('WARNING: Skipping tunnel to peer %s: Phase 1 integrity %s not supported' % (peer, phase1['integrity'].upper()))
                        flag_tunnelIsCompatible = False
                        
                    if len(phase2['encryption']) == 0:
                        log('WARNING: Skipping tunnel to peer %s: No supported Phase 2 encryption algorithms' % peer)
                        flag_tunnelIsCompatible = False
                        
                    if len(phase2['integrity']) == 0:
                        log('WARNING: Skipping tunnel to peer %s: No supported Phase 2 integrity algorithms' % peer)
                        flag_tunnelIsCompatible = False
                        
                    if len(privateSubnets) == 0:
                        log('WARNING: Skipping tunnel to peer %s: No destination private subnets')
                        flag_tunnelIsCompatible = False
                        
                    if flag_tunnelIsCompatible:                        
                        record = {
                            'name'                      : name,
                            'publicIp'                  : peer,
                            'privateSubnets'            : privateSubnets,
                            'secret'                    : psk,
                            'ikeVersion'                : int(version[4]),
                            'ipsecPolicies'             : {
                                'ikeCipherAlgo'         : [ASA_TO_MX_PROTOCOL_LABELS['encryption'][phase1['encryption']]],
                                'ikeAuthAlgo'           : [ASA_TO_MX_PROTOCOL_LABELS['integrity'][phase1['integrity']]], 
                                'ikePrfAlgo'            : ['default'], 
                                'ikeDiffieHellmanGroup' : ['group%s' % dhGroup], 
                                'ikeLifetime'           : lifetime, 
                                'childCipherAlgo'       : [], 
                                'childAuthAlgo'         : [],
                                'childLifetime'         : lifetime,
                                'childPfsGroup'         : ['disabled']
                            }
                        }                        
                        if not pfsGroup is None:
                            record['ipsecPolicies']['childPfsGroup'] = ['group%s' % dhGroup];                            
                        if not arg_tag is None:
                            record['networkTags'] = [arg_tag]
                        for algo in phase2['encryption']:
                            record['ipsecPolicies']['childCipherAlgo'].append(ASA_TO_MX_PROTOCOL_LABELS['encryption'][algo])
                        for algo in phase2['integrity']:
                            record['ipsecPolicies']['childAuthAlgo'].append(ASA_TO_MX_PROTOCOL_LABELS['integrity'][algo])
                            
                        newPeers.append(record)
    if len(newPeers) > 0:
        allVpnPeers = oldVpnConfig['peers'] + newPeers
        
        success, errors, response = updateOrganizationApplianceVpnThirdPartyVPNPeers(apiKey, organizationId, body={'peers':allVpnPeers})
        if success:
            log("Configutation uploaded successfully")
        else:
            killScript("Configuration upload failed")
            
    print("End of script.")
            
if __name__ == '__main__':
    main(sys.argv[1:])