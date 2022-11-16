readMe = '''
Copies network configuration from one organization to another. Both organizations must be accessible
by the same API key. Requires Python 3 and a YAML configtaion file.

Only the following configuration elements will be copied:
    Network name
    Network device types
    MX VLANs
    MR SSIDs
    MR L3 Firewall rules
    Alert settings

Syntax, Windows:
    python migrate_networks.py [-k <api_key>] [-c <config_file>] 
    
Syntax, Linux and Mac:
    python3 migrate_networks.py [-k <api_key>] [-c <config_file>]
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, one will be loaded from
                        environment variable MERAKI_DASHBOARD_API_KEY
    -c <config_file>    Path to the configuration file to use. Default is "./config.yaml"         
              
Example:
    Copy all networks from organization "Big Industries Inc" to organization "Parent company"
    according to configuration file "config.yaml":
    python migrate_networks.py -k 1234
    
An example configuration file can be found here:
    https://github.com/meraki/automation-scripts/blob/master/migrate_networks/config.yaml
    
Edit the confguration file using a text editor. It uses YAML syntax:
    https://yaml.org/

Required packages:
    requests
    pyyaml
    
To install required packages enter the following commands:

Windows:
    pip install requests
    pip install pyyaml
    
Linux and Mac:
    pip3 install requests
    pip3 install pyyaml
'''

### Code to interact with Meraki Dashboard API generated using this script:
### https://github.com/mpapazog/rogue_meraki_python_sdk

import time, ipaddress

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
    
# createOrganizationNetwork
#
# Description: Create a network
# Endpoint: POST /organizations/{organizationId}/networks
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!create-organization-network
#
# Request body schema:
#     name: String. The name of the new network
#     productTypes: Array. The product type(s) of the new network. If more than one type is included, the network will be a combined network.
#     tags: Array. A list of tags to be applied to the network
#     timeZone: String. The timezone of the network. For a list of allowed timezones, please see the 'TZ' column in the table in <a target='_blank' href='https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'>this article.</a>
#     copyFromNetworkId: String. The ID of the network to copy configuration from. Other provided parameters will override the copied configuration, except type which must match this network's type exactly.
#     notes: String. Add any notes or additional information about this network here.

def createOrganizationNetwork(apiKey, organizationId, body=None):
    url = "/organizations/" + str(organizationId) + "/networks"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceVlansSettings
#
# Description: Returns the enabled status of VLANs for the network
# Endpoint: GET /networks/{networkId}/appliance/vlans/settings
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-vlans-settings

def getNetworkApplianceVlansSettings(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/vlans/settings"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
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
    
# updateNetworkApplianceVlansSettings
#
# Description: Enable/Disable VLANs for the given network
# Endpoint: PUT /networks/{networkId}/appliance/vlans/settings
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-vlans-settings
#
# Request body schema:
#     vlansEnabled: Boolean. Boolean indicating whether to enable (true) or disable (false) VLANs for the network

def updateNetworkApplianceVlansSettings(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/vlans/settings"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# createNetworkApplianceVlan
#
# Description: Add a VLAN
# Endpoint: POST /networks/{networkId}/appliance/vlans
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!create-network-appliance-vlan
#
# Request body schema:
#     id: String. The VLAN ID of the new VLAN (must be between 1 and 4094)
#     name: String. The name of the new VLAN
#     subnet: String. The subnet of the VLAN
#     applianceIp: String. The local IP of the appliance on the VLAN
#     groupPolicyId: String. The id of the desired group policy to apply to the VLAN
#     templateVlanType: String. Type of subnetting of the VLAN. Applicable only for template network.
#     cidr: String. CIDR of the pool of subnets. Applicable only for template network. Each network bound to the template will automatically pick a subnet from this pool to build its own VLAN.
#     mask: Integer. Mask used for the subnet of all bound to the template networks. Applicable only for template network.
#     ip6: Object. IPv6 configuration on the VLAN
#     mandatoryDhcp: Object. Mandatory DHCP will enforce that clients connecting to this VLAN must use the IP address assigned by the DHCP server. Clients who use a static IP address won't be able to associate. Only available on firmware versions 17.0 and above

def createNetworkApplianceVlan(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/vlans"
    success, errors, headers, response = merakiRequest(apiKey, "post", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# deleteNetworkApplianceVlan
#
# Description: Delete a VLAN from a network
# Endpoint: DELETE /networks/{networkId}/appliance/vlans/{vlanId}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!delete-network-appliance-vlan

def deleteNetworkApplianceVlan(apiKey, networkId, vlanId):
    url = "/networks/" + str(networkId) + "/appliance/vlans/" + str(vlanId)
    success, errors, headers, response = merakiRequest(apiKey, "delete", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# updateNetworkApplianceVlan
#
# Description: Update a VLAN
# Endpoint: PUT /networks/{networkId}/appliance/vlans/{vlanId}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-vlan
#
# Request body schema:
#     name: String. The name of the VLAN
#     subnet: String. The subnet of the VLAN
#     applianceIp: String. The local IP of the appliance on the VLAN
#     groupPolicyId: String. The id of the desired group policy to apply to the VLAN
#     vpnNatSubnet: String. The translated VPN subnet if VPN and VPN subnet translation are enabled on the VLAN
#     dhcpHandling: String. The appliance's handling of DHCP requests on this VLAN. One of: 'Run a DHCP server', 'Relay DHCP to another server' or 'Do not respond to DHCP requests'
#     dhcpRelayServerIps: Array. The IPs of the DHCP servers that DHCP requests should be relayed to
#     dhcpLeaseTime: String. The term of DHCP leases if the appliance is running a DHCP server on this VLAN. One of: '30 minutes', '1 hour', '4 hours', '12 hours', '1 day' or '1 week'
#     dhcpBootOptionsEnabled: Boolean. Use DHCP boot options specified in other properties
#     dhcpBootNextServer: String. DHCP boot option to direct boot clients to the server to load the boot file from
#     dhcpBootFilename: String. DHCP boot option for boot filename
#     fixedIpAssignments: Object. The DHCP fixed IP assignments on the VLAN. This should be an object that contains mappings from MAC addresses to objects that themselves each contain "ip" and "name" string fields. See the sample request/response for more details.
#     reservedIpRanges: Array. The DHCP reserved IP ranges on the VLAN
#     dnsNameservers: String. The DNS nameservers used for DHCP responses, either "upstream_dns", "google_dns", "opendns", or a newline seperated string of IP addresses or domain names
#     dhcpOptions: Array. The list of DHCP options that will be included in DHCP responses. Each object in the list should have "code", "type", and "value" properties.
#     templateVlanType: String. Type of subnetting of the VLAN. Applicable only for template network.
#     cidr: String. CIDR of the pool of subnets. Applicable only for template network. Each network bound to the template will automatically pick a subnet from this pool to build its own VLAN.
#     mask: Integer. Mask used for the subnet of all bound to the template networks. Applicable only for template network.
#     ip6: Object. IPv6 configuration on the VLAN
#     mandatoryDhcp: Object. Mandatory DHCP will enforce that clients connecting to this VLAN must use the IP address assigned by the DHCP server. Clients who use a static IP address won't be able to associate. Only available on firmware versions 17.0 and above

def updateNetworkApplianceVlan(apiKey, networkId, vlanId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/vlans/" + str(vlanId)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
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


# updateNetworkApplianceSingleLan
#
# Description: Update single LAN configuration
# Endpoint: PUT /networks/{networkId}/appliance/singleLan
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-single-lan
#
# Request body schema:
#     subnet: String. The subnet of the single LAN configuration
#     applianceIp: String. The appliance IP address of the single LAN
#     ip6: Object. IPv6 configuration on the VLAN
#     mandatoryDhcp: Object. Mandatory DHCP will enforce that clients connecting to this LAN must use the IP address assigned by the DHCP server. Clients who use a static IP address won't be able to associate. Only available on firmware versions 17.0 and above

def updateNetworkApplianceSingleLan(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/singleLan"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkWirelessSsids
#
# Description: List the MR SSIDs in a network
# Endpoint: GET /networks/{networkId}/wireless/ssids
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-wireless-ssids

def getNetworkWirelessSsids(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/wireless/ssids"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# updateNetworkWirelessSsid
#
# Description: Update the attributes of an MR SSID
# Endpoint: PUT /networks/{networkId}/wireless/ssids/{number}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-wireless-ssid
#
# Request body schema:
#     name: String. The name of the SSID
#     enabled: Boolean. Whether or not the SSID is enabled
#     authMode: String. The association control method for the SSID ('open', 'open-enhanced', 'psk', 'open-with-radius', '8021x-meraki', '8021x-radius', '8021x-google', '8021x-localradius', 'ipsk-with-radius' or 'ipsk-without-radius')
#     enterpriseAdminAccess: String. Whether or not an SSID is accessible by 'enterprise' administrators ('access disabled' or 'access enabled')
#     encryptionMode: String. The psk encryption mode for the SSID ('wep' or 'wpa'). This param is only valid if the authMode is 'psk'
#     psk: String. The passkey for the SSID. This param is only valid if the authMode is 'psk'
#     wpaEncryptionMode: String. The types of WPA encryption. ('WPA1 only', 'WPA1 and WPA2', 'WPA2 only', 'WPA3 Transition Mode' or 'WPA3 only')
#     dot11w: Object. The current setting for Protected Management Frames (802.11w).
#     dot11r: Object. The current setting for 802.11r
#     splashPage: String. The type of splash page for the SSID ('None', 'Click-through splash page', 'Billing', 'Password-protected with Meraki RADIUS', 'Password-protected with custom RADIUS', 'Password-protected with Active Directory', 'Password-protected with LDAP', 'SMS authentication', 'Systems Manager Sentry', 'Facebook Wi-Fi', 'Google OAuth', 'Sponsored guest', 'Cisco ISE' or 'Google Apps domain'). This attribute is not supported for template children.
#     splashGuestSponsorDomains: Array. Array of valid sponsor email domains for sponsored guest splash type.
#     oauth: Object. The OAuth settings of this SSID. Only valid if splashPage is 'Google OAuth'.
#     localRadius: Object. The current setting for Local Authentication, a built-in RADIUS server on the access point. Only valid if authMode is '8021x-localradius'.
#     ldap: Object. The current setting for LDAP. Only valid if splashPage is 'Password-protected with LDAP'.
#     activeDirectory: Object. The current setting for Active Directory. Only valid if splashPage is 'Password-protected with Active Directory'
#     radiusServers: Array. The RADIUS 802.1X servers to be used for authentication. This param is only valid if the authMode is 'open-with-radius', '8021x-radius' or 'ipsk-with-radius'
#     radiusProxyEnabled: Boolean. If true, Meraki devices will proxy RADIUS messages through the Meraki cloud to the configured RADIUS auth and accounting servers.
#     radiusTestingEnabled: Boolean. If true, Meraki devices will periodically send Access-Request messages to configured RADIUS servers using identity 'meraki_8021x_test' to ensure that the RADIUS servers are reachable.
#     radiusCalledStationId: String. The template of the called station identifier to be used for RADIUS (ex. $NODE_MAC$:$VAP_NUM$).
#     radiusAuthenticationNasId: String. The template of the NAS identifier to be used for RADIUS authentication (ex. $NODE_MAC$:$VAP_NUM$).
#     radiusServerTimeout: Integer. The amount of time for which a RADIUS client waits for a reply from the RADIUS server (must be between 1-10 seconds).
#     radiusServerAttemptsLimit: Integer. The maximum number of transmit attempts after which a RADIUS server is failed over (must be between 1-5).
#     radiusFallbackEnabled: Boolean. Whether or not higher priority RADIUS servers should be retried after 60 seconds.
#     radiusDataCarrierDetect: Object. RADIUS data-carrier detection settings.
#     radiusCoaEnabled: Boolean. If true, Meraki devices will act as a RADIUS Dynamic Authorization Server and will respond to RADIUS Change-of-Authorization and Disconnect messages sent by the RADIUS server.
#     radiusFailoverPolicy: String. This policy determines how authentication requests should be handled in the event that all of the configured RADIUS servers are unreachable ('Deny access' or 'Allow access')
#     radiusLoadBalancingPolicy: String. This policy determines which RADIUS server will be contacted first in an authentication attempt and the ordering of any necessary retry attempts ('Strict priority order' or 'Round robin')
#     radiusAccountingEnabled: Boolean. Whether or not RADIUS accounting is enabled. This param is only valid if the authMode is 'open-with-radius', '8021x-radius' or 'ipsk-with-radius'
#     radiusAccountingServers: Array. The RADIUS accounting 802.1X servers to be used for authentication. This param is only valid if the authMode is 'open-with-radius', '8021x-radius' or 'ipsk-with-radius' and radiusAccountingEnabled is 'true'
#     radiusAccountingInterimInterval: Integer. The interval (in seconds) in which accounting information is updated and sent to the RADIUS accounting server.
#     radiusAttributeForGroupPolicies: String. Specify the RADIUS attribute used to look up group policies ('Filter-Id', 'Reply-Message', 'Airespace-ACL-Name' or 'Aruba-User-Role'). Access points must receive this attribute in the RADIUS Access-Accept message
#     ipAssignmentMode: String. The client IP assignment mode ('NAT mode', 'Bridge mode', 'Layer 3 roaming', 'Ethernet over GRE', 'Layer 3 roaming with a concentrator' or 'VPN')
#     useVlanTagging: Boolean. Whether or not traffic should be directed to use specific VLANs. This param is only valid if the ipAssignmentMode is 'Bridge mode' or 'Layer 3 roaming'
#     concentratorNetworkId: String. The concentrator to use when the ipAssignmentMode is 'Layer 3 roaming with a concentrator' or 'VPN'.
#     secondaryConcentratorNetworkId: String. The secondary concentrator to use when the ipAssignmentMode is 'VPN'. If configured, the APs will switch to using this concentrator if the primary concentrator is unreachable. This param is optional. ('disabled' represents no secondary concentrator.)
#     disassociateClientsOnVpnFailover: Boolean. Disassociate clients when 'VPN' concentrator failover occurs in order to trigger clients to re-associate and generate new DHCP requests. This param is only valid if ipAssignmentMode is 'VPN'.
#     vlanId: Integer. The VLAN ID used for VLAN tagging. This param is only valid when the ipAssignmentMode is 'Layer 3 roaming with a concentrator' or 'VPN'
#     defaultVlanId: Integer. The default VLAN ID used for 'all other APs'. This param is only valid when the ipAssignmentMode is 'Bridge mode' or 'Layer 3 roaming'
#     apTagsAndVlanIds: Array. The list of tags and VLAN IDs used for VLAN tagging. This param is only valid when the ipAssignmentMode is 'Bridge mode' or 'Layer 3 roaming'
#     walledGardenEnabled: Boolean. Allow access to a configurable list of IP ranges, which users may access prior to sign-on.
#     walledGardenRanges: Array. Specify your walled garden by entering an array of addresses, ranges using CIDR notation, domain names, and domain wildcards (e.g. '192.168.1.1/24', '192.168.37.10/32', 'www.yahoo.com', '*.google.com']). Meraki's splash page is automatically included in your walled garden.
#     gre: Object. Ethernet over GRE settings
#     radiusOverride: Boolean. If true, the RADIUS response can override VLAN tag. This is not valid when ipAssignmentMode is 'NAT mode'.
#     radiusGuestVlanEnabled: Boolean. Whether or not RADIUS Guest VLAN is enabled. This param is only valid if the authMode is 'open-with-radius' and addressing mode is not set to 'isolated' or 'nat' mode
#     radiusGuestVlanId: Integer. VLAN ID of the RADIUS Guest VLAN. This param is only valid if the authMode is 'open-with-radius' and addressing mode is not set to 'isolated' or 'nat' mode
#     minBitrate: Number. The minimum bitrate in Mbps of this SSID in the default indoor RF profile. ('1', '2', '5.5', '6', '9', '11', '12', '18', '24', '36', '48' or '54')
#     bandSelection: String. The client-serving radio frequencies of this SSID in the default indoor RF profile. ('Dual band operation', '5 GHz band only' or 'Dual band operation with Band Steering')
#     perClientBandwidthLimitUp: Integer. The upload bandwidth limit in Kbps. (0 represents no limit.)
#     perClientBandwidthLimitDown: Integer. The download bandwidth limit in Kbps. (0 represents no limit.)
#     perSsidBandwidthLimitUp: Integer. The total upload bandwidth limit in Kbps. (0 represents no limit.)
#     perSsidBandwidthLimitDown: Integer. The total download bandwidth limit in Kbps. (0 represents no limit.)
#     lanIsolationEnabled: Boolean. Boolean indicating whether Layer 2 LAN isolation should be enabled or disabled. Only configurable when ipAssignmentMode is 'Bridge mode'.
#     visible: Boolean. Boolean indicating whether APs should advertise or hide this SSID. APs will only broadcast this SSID if set to true
#     availableOnAllAps: Boolean. Boolean indicating whether all APs should broadcast the SSID or if it should be restricted to APs matching any availability tags. Can only be false if the SSID has availability tags.
#     availabilityTags: Array. Accepts a list of tags for this SSID. If availableOnAllAps is false, then the SSID will only be broadcast by APs with tags matching any of the tags in this list.
#     adaptivePolicyGroupId: String. Adaptive policy group ID this SSID is assigned to.
#     mandatoryDhcpEnabled: Boolean. If true, Mandatory DHCP will enforce that clients connecting to this SSID must use the IP address assigned by the DHCP server. Clients who use a static IP address won't be able to associate.
#     adultContentFilteringEnabled: Boolean. Boolean indicating whether or not adult content will be blocked
#     dnsRewrite: Object. DNS servers rewrite settings
#     wifiPersonalNetworkEnabled: Boolean. Boolean indicating whether or not Wi-Fi Personal Network is enabled for this SSID. This param is only valid if the authMode is 'ipsk-without-radius' and the ipAssignmentMode is 'Bridge mode'
#     speedBurst: Object. The SpeedBurst setting for this SSID'

def updateNetworkWirelessSsid(apiKey, networkId, number, body=None):
    url = "/networks/" + str(networkId) + "/wireless/ssids/" + str(number)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkWirelessSsidFirewallL3FirewallRules
#
# Description: Return the L3 firewall rules for an SSID on an MR network
# Endpoint: GET /networks/{networkId}/wireless/ssids/{number}/firewall/l3FirewallRules
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-wireless-ssid-firewall-l3-firewall-rules

def getNetworkWirelessSsidFirewallL3FirewallRules(apiKey, networkId, number):
    url = "/networks/" + str(networkId) + "/wireless/ssids/" + str(number) + "/firewall/l3FirewallRules"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response


# updateNetworkWirelessSsidFirewallL3FirewallRules
#
# Description: Update the L3 firewall rules of an SSID on an MR network
# Endpoint: PUT /networks/{networkId}/wireless/ssids/{number}/firewall/l3FirewallRules
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-wireless-ssid-firewall-l3-firewall-rules
#
# Request body schema:
#     rules: Array. An ordered array of the firewall rules for this SSID (not including the local LAN access rule or the default rule)
#     allowLanAccess: Boolean. Allow wireless client access to local LAN (boolean value - true allows access and false denies access) (optional)

def updateNetworkWirelessSsidFirewallL3FirewallRules(apiKey, networkId, number, body=None):
    url = "/networks/" + str(networkId) + "/wireless/ssids/" + str(number) + "/firewall/l3FirewallRules"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# updateNetwork
#
# Description: Update a network
# Endpoint: PUT /networks/{networkId}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network
#
# Request body schema:
#     name: String. The name of the network
#     timeZone: String. The timezone of the network. For a list of allowed timezones, please see the 'TZ' column in the table in <a target='_blank' href='https://en.wikipedia.org/wiki/List_of_tz_database_time_zones'>this article.</a>
#     tags: Array. A list of tags to be applied to the network
#     enrollmentString: String. A unique identifier which can be used for device enrollment or easy access through the Meraki SM Registration page or the Self Service Portal. Please note that changing this field may cause existing bookmarks to break.
#     notes: String. Add any notes or additional information about this network here.

def updateNetwork(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# getNetworkAlertsSettings
#
# Description: Return the alert configuration for this network
# Endpoint: GET /networks/{networkId}/alerts/settings
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-alerts-settings

def getNetworkAlertsSettings(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/alerts/settings"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response


# updateNetworkAlertsSettings
#
# Description: Update the alert configuration for this network
# Endpoint: PUT /networks/{networkId}/alerts/settings
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-alerts-settings
#
# Request body schema:
#     defaultDestinations: Object. The network-wide destinations for all alerts on the network.
#     alerts: Array. Alert-specific configuration for each type. Only alerts that pertain to the network can be updated.

def updateNetworkAlertsSettings(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/alerts/settings"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
# getNetworkFirmwareUpgrades
#
# Description: Get firmware upgrade information for a network
# Endpoint: GET /networks/{networkId}/firmwareUpgrades
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-firmware-upgrades

def getNetworkFirmwareUpgrades(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/firmwareUpgrades"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
    
### END Generated code

import sys, getopt, os, datetime, yaml

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
    
def loadConfig(filename):
    try:
        file = open(filename, "r")
        config = yaml.safe_load(file)
        file.close()        
    except:
        return None        
    return config
    
def targetListListHasAnySourceListTag(targetList, sourceList):
    for tag in sourceList:
        if tag in targetList:
            return True
    return False
    
def getNetworkIdByName(networkList, name):
    for net in networkList:
        if net['name'] == name:
            return net['id']
    return None
    
def getNetworkNameById(networkList, netId):
    for net in networkList:
        if net['id'] == netId:
            return net['name']
    return None
    
def vlansListContainsId(vlansList, vlanId):
    for vlan in vlansList:
        if vlan['id'] == vlanId:
            return True
    return False
    
def checkVlanFeaturesWithFirmwareRequirements(sourceConfig, targetNetId, apiKey):
    featureRequiredVersions = {
        'mandatoryDhcp' : [17, 0],
        'ipv6'          : [17, 5]
    }
    result = []
    
    hasFeatureWithRequirements = False
    for vlan in sourceConfig:
        for key in vlan:
            if key in featureRequiredVersions:
                hasFeatureWithRequirements = True
                break
        if hasFeatureWithRequirements:
            break
        
    if hasFeatureWithRequirements:
        success, errors, targetNetFirmware = getNetworkFirmwareUpgrades(apiKey, targetNetId)
        if targetNetFirmware is None:
            return None
        try:
            mxFwVersion = targetNetFirmware['products']['appliance']['currentVersion']['firmware']
            parts       = mxFwVersion.split('-')
            major       = int(parts[1])
            minor       = int(parts[2])
        except:
            return True
            
        for feature in featureRequiredVersions:
            if major < featureRequiredVersions[feature][0]:
                if not feature in result:
                    result.append(feature)
            elif minor < featureRequiredVersions[feature][1]:
                if not feature in result:
                    result.append(feature)   
    return result
    
def networkContainsForbiddenTags(config, networkId, networksList):
    if not config['networkFilters']['excludeTargetNetworksByTag']:
        return False
    for net in networksList:
        if net['id'] == networkId:
            for tag in net['tags']:
                if tag in config['networkFilters']['targetNetworkTagsList']:
                    return True
    return False
    
def main(argv):  
    arg_apiKey      = None
    arg_configFile  = "config.yaml"
    
    try:
        opts, args = getopt.getopt(argv, 'k:c:h:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-c':
            arg_configFile  = str(arg)
        if opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    if apiKey is None:
        log("ERROR: API key not found")
        killScript()
            
    log('Using configuration file "%s"' % arg_configFile)
    config = loadConfig(arg_configFile)
    if config is None:
        killScript("Unable to load config file")
        
    try:
        sourceOrgName = config['organizationNames']['source']
        targetOrgName = config['organizationNames']['destination']
    except:
        killScript("Unable to load source/destination org names from config file")
        
    sourceOrgId = None
    targetOrgId = None
    
    success, errors, allOrgs = getOrganizations(apiKey)
    if allOrgs is None:
        killScript("Unable to fetch organizations' list")
        
    for org in allOrgs:
        if org['name'] == sourceOrgName:
            sourceOrgId = org['id']
        if org['name'] == targetOrgName:
            targetOrgId = org['id']
            
    if sourceOrgId is None:
        killScript('No organization with name "%s"' % sourceOrgName)
    if targetOrgId is None:
        killScript('No organization with name "%s"' % targetOrgName)
        
    log("Source organization id %s" % sourceOrgId)
    log("Destination organization id %s" % targetOrgId)
    
    success, errors, sourceOrgNetworks = getOrganizationNetworks(apiKey, sourceOrgId)
    if sourceOrgNetworks is None:
        killScript("Unable to fetch source org networks")
        
    success, errors, targetOrgNetworks = getOrganizationNetworks(apiKey, targetOrgId)
    if targetOrgNetworks is None:
        killScript("Unable to fetch destination org networks")
        
    filteredSourceNetworks = []
    for net in sourceOrgNetworks:
         if (not config['networkFilters']['filterSourceNetworksByTag']) or (targetListListHasAnySourceListTag(net['tags'], config['networkFilters']['sourceNetworkTagsList'])):
            filteredSourceNetworks.append(net)              
           
    if config['enabledTasks']['createNetworks']:
        log("Creating networks...")    
        flag_targetOrgNetworksUpdated = False
        for net in filteredSourceNetworks:
            if not getNetworkIdByName(targetOrgNetworks, net['name']) is None:
                log('Skipping network "%s": Net with that name already exists' % net['name'])
                continue
                
            networkData = {
                'name'          : net['name'],
                'productTypes'  : net['productTypes'],
                'tags'          : net['tags'],
                'timeZone'      : net['timeZone']
            }
            createOrganizationNetwork(apiKey, targetOrgId, body=networkData)
            flag_targetOrgNetworksUpdated = True
            if config['enabledTasks']['createNetworks'] and flag_targetOrgNetworksUpdated:
                success, errors, targetOrgNetworks = getOrganizationNetworks(apiKey, targetOrgId)
                if targetOrgNetworks is None:
                    killScript("Unable to refresh destination org networks")
    
    if config['enabledTasks']['refreshTimeZones']:
        log("Refreshing time zone settings...")        
        for net in filteredSourceNetworks:
            targetNetId = getNetworkIdByName(targetOrgNetworks, net['name'])
            if targetNetId is None:
                log('WARNING: Destination org contains no net "%s"' % net['name'])
                continue
                
            if networkContainsForbiddenTags(config, targetNetId, targetOrgNetworks):
                log('Skipping net "%s": Exclusion tag in destination' % net['name'])
                continue
                
            payload = {'timeZone': net['timeZone']}
            success, errors, tzResponse = updateNetwork(apiKey, targetNetId, body=payload)
                
    if config['enabledTasks']['copyMxVlans']:
        log("Copying MX VLANs...")                
        for net in filteredSourceNetworks:
            if not 'appliance' in net['productTypes']:
                log('Skipping net "%s": Contains no appliance config' % net['name'])
                continue
                
            targetNetId = getNetworkIdByName(targetOrgNetworks, net['name'])
            if targetNetId is None:
                log('WARNING: Destination org contains no net "%s"' % net['name'])
                continue
                
            if networkContainsForbiddenTags(config, targetNetId, targetOrgNetworks):
                log('Skipping net "%s": Exclusion tag in destination' % net['name'])
                continue
                
            success, errors, vlanSettings = getNetworkApplianceVlansSettings(apiKey, net['id'])
            if vlanSettings is None:
                log('WARNING: Unable to fetch VLAN settings for net "%s"' % net['name'])
                continue
                            
            if vlanSettings['vlansEnabled']:
                success, errors, sourceVlans = getNetworkApplianceVlans(apiKey, net['id'])
                if sourceVlans is None:
                    log('WARNING: Unable to fetch VLANs for net "%s"' % net['name'])
                    continue
                                
                keysToDrop = checkVlanFeaturesWithFirmwareRequirements(sourceVlans, targetNetId, apiKey)  
                    
                success, errors, targetNetVlanSettings = getNetworkApplianceVlansSettings(apiKey, targetNetId)
                if targetNetVlanSettings is None:
                    log('WARNING: Unable to fetch destination VLAN settings for net "%s"' % net['name'])
                    continue
                                    
                if not targetNetVlanSettings['vlansEnabled']:
                    requestBody = {'vlansEnabled': True}
                    success, errors, response = updateNetworkApplianceVlansSettings(apiKey, targetNetId, body=requestBody)
                    if not success:
                        log('WARNING: Unable to update VLAN settings for net "%s"' % net['name'])
                        continue
                
                success, errors, targetNetVlans = getNetworkApplianceVlans(apiKey, targetNetId)
                if targetNetVlans is None:
                    log('WARNING: Unable to get destination VLANs for net "%s"' % net['name'])
                    continue
                    
                #Flag VLANs that can cause IP address conflicts and assign temp subnets
                flaggedVlanIds = []
                for sv in sourceVlans:
                    for tv in targetNetVlans:
                        if sv['id'] != tv['id']:
                            sourceSubnet = ipaddress.IPv4Network(sv['subnet'])
                            targetSubnet = ipaddress.IPv4Network(tv['subnet'])                            
                            if sourceSubnet.overlaps(targetSubnet):
                                flaggedVlanIds.append(tv['id'])                                
                offset = 0
                for vlanId in flaggedVlanIds:
                    subnet = '%s%s/30' % (config['configModifications']['ipConflictVlanTempSubnetPrefix'], str(offset * 2))
                    mxIp   = '%s%s' % (config['configModifications']['ipConflictVlanTempSubnetPrefix'], str(offset * 2 + 1))                  
                    offset += 1                    
                    dummyConfig = {
                        "subnet"                : subnet,
                        "applianceIp"           : mxIp,
                        "fixedIpAssignments"    : {},
                        "reservedIpRanges"      : [],
                        "dnsNameservers"        : "upstream_dns",
                        "dhcpHandling"          : "Run a DHCP server",
                        "dhcpLeaseTime"         : "1 day",
                        "dhcpBootOptionsEnabled": False,
                        "dhcpOptions"           : []
                    }
                    updateNetworkApplianceVlan(apiKey, targetNetId, vlanId, body=dummyConfig)
                    
                    
                for vlan in sourceVlans:
                    cleanVlan = {}
                    
                    for item in vlan:
                        if not item in keysToDrop:
                            cleanVlan[item] = vlan[item]
                    if vlansListContainsId(targetNetVlans, vlan['id']):
                        cleanVlanWithoutId = {}
                        for item in cleanVlan:
                            if item != 'id':
                                cleanVlanWithoutId[item] = cleanVlan[item]
                        updateNetworkApplianceVlan(apiKey, targetNetId, vlan['id'], body=cleanVlanWithoutId)
                    else:
                        createNetworkApplianceVlan(apiKey, targetNetId, body=cleanVlan)
                        
                for vlan in targetNetVlans:
                    if not vlansListContainsId(sourceVlans, vlan['id']):
                        deleteNetworkApplianceVlan(apiKey, targetNetId, vlan['id'])
            else: 
                # VLANs not enabled in source net. need to copy single-LAN config
                success, errors, sourceSingleLan = getNetworkApplianceSingleLan(apiKey, net['id'])
                if sourceSingleLan is None:
                    log('WARNING: Unable to get single LAN config for net "%s"' % net['name'])
                    continue
                    
                keysToDrop = checkVlanFeaturesWithFirmwareRequirements([sourceSingleLan], targetNetId, apiKey)
                    
                cleanLanConfig = {}
                for item in sourceSingleLan:
                    if not item in keysToDrop:
                        cleanLanConfig[item] = sourceSingleLan[item]
                    
                updateNetworkApplianceSingleLan(apiKey, targetNetId, body=cleanLanConfig)
                
             
    if config['enabledTasks']['copyMrSsids']:
        log("Copying MR SSIDs...")          
        for net in filteredSourceNetworks:
            if not 'wireless' in net['productTypes']:
                log('Skipping net "%s": Contains no wireless config' % net['name'])
                continue
            
            success, errors, sourceSsids = getNetworkWirelessSsids(apiKey, net['id'])
            if sourceSsids is None:
                log('WARNING: Unable to fetch SSIDs for net "%s"' % net['name'])
                continue
                
            targetNetId = getNetworkIdByName(targetOrgNetworks, net['name'])
            if targetNetId is None:
                log('WARNING: Destination org contains no net "%s"' % net['name']) 
                continue
                
            if networkContainsForbiddenTags(config, targetNetId, targetOrgNetworks):
                log('Skipping net "%s": Exclusion tag in destination' % net['name'])
                continue
                
            for ssid in sourceSsids:
                ssidData = {}
                for item in ssid:
                    if item != 'number':
                        ssidData[item] = ssid[item]
                if 'concentratorNetworkId' in ssid and type(ssid['concentratorNetworkId']) == str:
                    concentratorName        = getNetworkNameById(sourceOrgNetworks, ssid['concentratorNetworkId'])
                    targetConcentratorId    = getNetworkIdByName(targetOrgNetworks, concentratorName)
                    if targetConcentratorId is None:
                        log('WARNING: WLAN concentrator "%s" not found in destination' % concentratorName) 
                        continue
                    ssidData['concentratorNetworkId'] = targetConcentratorId
                if 'encryptionMode' in ssid and ssid['encryptionMode'] == 'wpa-eap':
                    ssidData['encryptionMode'] = 'wpa'
                if 'radiusFailoverPolicy' in ssidData and ssidData['radiusFailoverPolicy'] is None:
                    ssidData['radiusFailoverPolicy'] = 'Deny access'
                if 'radiusLoadBalancingPolicy' in ssidData and ssidData['radiusLoadBalancingPolicy'] is None:
                    ssidData['radiusLoadBalancingPolicy'] = 'Strict priority order'
                    
                if 'radiusServers' in ssidData and config['configModifications']['overwriteSsidRadiusSecret']['enabled']:
                    for server in ssidData['radiusServers']:
                        server['secret'] = config['configModifications']['overwriteSsidRadiusSecret']['newRadiusSecret']
                                            
                success, errors, response = updateNetworkWirelessSsid(apiKey, targetNetId, ssid['number'], body=ssidData)
                if not success:
                    log('WARNING: Failed to configure SSID #%s for net "%s"' % (ssid['number'], net['name']))
        
    if config['enabledTasks']['copyMrFirewallRules']:
        log("Copying MR Firewall rules...")   
        for net in filteredSourceNetworks:
            if not 'wireless' in net['productTypes']:
                log('Skipping net "%s": Contains no wireless config' % net['name'])
                continue
                
            targetNetId = getNetworkIdByName(targetOrgNetworks, net['name'])
            if targetNetId is None:
                log('WARNING: Destination org contains no net "%s"' % net['name']) 
                continue
                
            if networkContainsForbiddenTags(config, targetNetId, targetOrgNetworks):
                log('Skipping net "%s": Exclusion tag in destination' % net['name'])
                continue
                
            for i in range(0, 15):
                success, errors, sourceRules = getNetworkWirelessSsidFirewallL3FirewallRules(apiKey, net['id'], i)                
                if sourceRules is None:
                    log('WARNING: Unable to fetch rules for net "%s", SSID #%s' % (net['name'], i))
                    continue
                    
                allowLanAccess = True
                
                rulesWithoutDefaultAllow = sourceRules['rules'][:-1]
                lastRule = rulesWithoutDefaultAllow[len(rulesWithoutDefaultAllow)-1]
                if lastRule['destCidr'] == 'Local LAN':
                    rulesWithoutDefaultAllow = rulesWithoutDefaultAllow[:-1]
                    allowLanAccess = (lastRule['policy'] == 'allow')
                    
                rulesBody = {
                    'rules'             : rulesWithoutDefaultAllow,
                    'allowLanAccess'    : allowLanAccess
                }
                
                success, errors, rtResponse = updateNetworkWirelessSsidFirewallL3FirewallRules(apiKey, targetNetId, i, body=rulesBody)              
                if not success:
                    log('WARNING: Unable to modify rules for net "%s", SSID #%s' % (net['name'], i))
                        
    if config['enabledTasks']['copyAlerts']:
        log("Copying alerts...") 
        for net in filteredSourceNetworks:
            success, errors, sourceAlerts = getNetworkAlertsSettings(apiKey, net['id'])
            if sourceAlerts is None:
                log('WARNING: Unable to fetch alerts for net "%s"' % net['name']) 
                continue
        
            targetNetId = getNetworkIdByName(targetOrgNetworks, net['name'])
            if targetNetId is None:
                log('WARNING: Destination org contains no net "%s"' % net['name']) 
                continue
                
            if networkContainsForbiddenTags(config, targetNetId, targetOrgNetworks):
                log('Skipping net "%s": Exclusion tag in destination' % net['name'])
                continue
                
            updateNetworkAlertsSettings(apiKey, targetNetId, body=sourceAlerts)
                
                
if __name__ == '__main__':
    main(sys.argv[1:])