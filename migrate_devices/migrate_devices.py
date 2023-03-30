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
    Management interface
    MX ports
    MX SSIDs
    Site-to-site VPN
    Switch ports
   
Network configuration is NOT migrated. Before running this script, make sure your destination
organization has networks with the exact same names as the ones the devices will be removed
from in the source organization. To move network configuration at scale, use a script such
as this one first:
https://github.com/meraki/automation-scripts/tree/master/migrate_networks

Syntax, Windows:
    python migrate_devices.py [-k <api_key>] -o <org_name> -m <mode> [-t <tag>] [-f <file>]
        [-d <device_filter>] [-v <vpn_mode>]
    
Syntax, Linux and Mac:
    python3 migrate_devices.py [-k <api_key>] -o <org_name> -m <mode> [-t <tag>] [-f <file>]
        [-d <device_filter>] [-v <vpn_mode>]
    
Mandatory parameters:
    -o <org_name>       The name of the organization you want to interact with
    -m <mode>           Mode of operation for the script. Valid forms:
                            -m export           Exports device data to file
                            -m unclaim          Removes devices from org
                            -m import           Imports device data from file
                            -m refresh          Does not claim devices, only refreshes config
    
Optional parameters:
    -k <api_key>        Your Meraki Dashboard API key. If omitted, one will be loaded from
                        environment variable MERAKI_DASHBOARD_API_KEY
    -t <tag>            Network tag to be matched for exporting and unclaiming. This parameter
                        is MANDATORY when exporting or unclaiming, but will be IGNORED during
                        import
    -f <file>           Name of the file to be used for export/import/refresh. This parameter is 
                        MANDATORY when importing or refreshing and OPTIONAL when exporting,
                        defaulting to devices_<timestamp>.json if omitted. It will be IGNORED
                        when running the script in unclaim mode
    -d <device_filter>  Only process devices with model names starting with given string, case
                        insensitive
    -v <vpn_mode>       Whether to also process VPN settings. Valid forms:
                            -v none             Do not process VPN configuration (default)
                            -v site             Only process site-to-site VPN configuration
                        * The below forms are experimental and may not work with all configurations
                            -v client           Only process Anyconnect/L2TP client VPN config
                            -v both             Process both client and site-to-site config
              
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

# getNetworkAppliancePorts
#
# Description: List per-port VLAN settings for all ports of a MX.
# Endpoint: GET /networks/{networkId}/appliance/ports
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-ports

def getNetworkAppliancePorts(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/ports"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# updateNetworkAppliancePort
#
# Description: Update the per-port VLAN settings for a single MX port.
# Endpoint: PUT /networks/{networkId}/appliance/ports/{portId}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-port
#
# Request body schema:
#     enabled: Boolean. The status of the port
#     dropUntaggedTraffic: Boolean. Trunk port can Drop all Untagged traffic. When true, no VLAN is required. Access ports cannot have dropUntaggedTraffic set to true.
#     type: String. The type of the port: 'access' or 'trunk'.
#     vlan: Integer. Native VLAN when the port is in Trunk mode. Access VLAN when the port is in Access mode.
#     allowedVlans: String. Comma-delimited list of the VLAN ID's allowed on the port, or 'all' to permit all VLAN's on the port.
#     accessPolicy: String. The name of the policy. Only applicable to Access ports. Valid values are: 'open', '8021x-radius', 'mac-radius', 'hybris-radius' for MX64 or Z3 or any MX supporting the per port authentication feature. Otherwise, 'open' is the only valid value and 'open' is the default value if the field is missing.
#     peerSgtCapable: Boolean. Whether or not SGT is enabled for traffic on this port. This can only be set to true for Trunk ports.

def updateNetworkAppliancePort(apiKey, networkId, portId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/ports/" + str(portId)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceSsids
#
# Description: List the MX SSIDs in a network
# Endpoint: GET /networks/{networkId}/appliance/ssids
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-ssids

def getNetworkApplianceSsids(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/ssids"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# updateNetworkApplianceSsid
#
# Description: Update the attributes of an MX SSID
# Endpoint: PUT /networks/{networkId}/appliance/ssids/{number}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-ssid
#
# Request body schema:
#     name: String. The name of the SSID.
#     enabled: Boolean. Whether or not the SSID is enabled.
#     defaultVlanId: Integer. The VLAN ID of the VLAN associated to this SSID. This parameter is only valid if the network is in routed mode.
#     authMode: String. The association control method for the SSID ('open', 'psk', '8021x-meraki' or '8021x-radius').
#     psk: String. The passkey for the SSID. This param is only valid if the authMode is 'psk'.
#     radiusServers: Array. The RADIUS 802.1x servers to be used for authentication. This param is only valid if the authMode is '8021x-radius'.
#     encryptionMode: String. The psk encryption mode for the SSID ('wep' or 'wpa'). This param is only valid if the authMode is 'psk'.
#     wpaEncryptionMode: String. The types of WPA encryption. ('WPA1 and WPA2', 'WPA2 only', 'WPA3 Transition Mode' or 'WPA3 only'). This param is only valid if (1) the authMode is 'psk' & the encryptionMode is 'wpa' OR (2) the authMode is '8021x-meraki' OR (3) the authMode is '8021x-radius'
#     visible: Boolean. Boolean indicating whether the MX should advertise or hide this SSID.
#     dhcpEnforcedDeauthentication: Object. DHCP Enforced Deauthentication enables the disassociation of wireless clients in addition to Mandatory DHCP. This param is only valid on firmware versions >= MX 17.0 where the associated LAN has Mandatory DHCP Enabled 
#     dot11w: Object. The current setting for Protected Management Frames (802.11w).

def updateNetworkApplianceSsid(apiKey, networkId, number, body=None):
    url = "/networks/" + str(networkId) + "/appliance/ssids/" + str(number)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getDeviceSwitchPorts
#
# Description: List the switch ports for a switch
# Endpoint: GET /devices/{serial}/switch/ports
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-device-switch-ports

def getDeviceSwitchPorts(apiKey, serial):
    url = "/devices/" + str(serial) + "/switch/ports"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# updateDeviceSwitchPort
#
# Description: Update a switch port
# Endpoint: PUT /devices/{serial}/switch/ports/{portId}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-device-switch-port
#
# Request body schema:
#     name: String. The name of the switch port.
#     tags: Array. The list of tags of the switch port.
#     enabled: Boolean. The status of the switch port.
#     poeEnabled: Boolean. The PoE status of the switch port.
#     type: String. The type of the switch port ('trunk' or 'access').
#     vlan: Integer. The VLAN of the switch port. A null value will clear the value set for trunk ports.
#     voiceVlan: Integer. The voice VLAN of the switch port. Only applicable to access ports.
#     allowedVlans: String. The VLANs allowed on the switch port. Only applicable to trunk ports.
#     isolationEnabled: Boolean. The isolation status of the switch port.
#     rstpEnabled: Boolean. The rapid spanning tree protocol status.
#     stpGuard: String. The state of the STP guard ('disabled', 'root guard', 'bpdu guard' or 'loop guard').
#     linkNegotiation: String. The link speed for the switch port.
#     portScheduleId: String. The ID of the port schedule. A value of null will clear the port schedule.
#     udld: String. The action to take when Unidirectional Link is detected (Alert only, Enforce). Default configuration is Alert only.
#     accessPolicyType: String. The type of the access policy of the switch port. Only applicable to access ports. Can be one of 'Open', 'Custom access policy', 'MAC allow list' or 'Sticky MAC allow list'.
#     accessPolicyNumber: Integer. The number of a custom access policy to configure on the switch port. Only applicable when 'accessPolicyType' is 'Custom access policy'.
#     macAllowList: Array. Only devices with MAC addresses specified in this list will have access to this port. Up to 20 MAC addresses can be defined. Only applicable when 'accessPolicyType' is 'MAC allow list'.
#     stickyMacAllowList: Array. The initial list of MAC addresses for sticky Mac allow list. Only applicable when 'accessPolicyType' is 'Sticky MAC allow list'.
#     stickyMacAllowListLimit: Integer. The maximum number of MAC addresses for sticky MAC allow list. Only applicable when 'accessPolicyType' is 'Sticky MAC allow list'.
#     stormControlEnabled: Boolean. The storm control status of the switch port.
#     adaptivePolicyGroupId: String. The adaptive policy group ID that will be used to tag traffic through this switch port. This ID must pre-exist during the configuration, else needs to be created using adaptivePolicy/groups API. Cannot be applied to a port on a switch bound to profile.
#     peerSgtCapable: Boolean. If true, Peer SGT is enabled for traffic through this switch port. Applicable to trunk port only, not access port. Cannot be applied to a port on a switch bound to profile.
#     flexibleStackingEnabled: Boolean. For supported switches (e.g. MS420/MS425), whether or not the port has flexible stacking enabled.
#     daiTrusted: Boolean. If true, ARP packets for this port will be considered trusted, and Dynamic ARP Inspection will allow the traffic.
#     profile: Object. Profile attributes

def updateDeviceSwitchPort(apiKey, serial, portId, body=None):
    url = "/devices/" + str(serial) + "/switch/ports/" + str(portId)
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getDeviceManagementInterface
#
# Description: Return the management interface settings for a device
# Endpoint: GET /devices/{serial}/managementInterface
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-device-management-interface

def getDeviceManagementInterface(apiKey, serial):
    url = "/devices/" + str(serial) + "/managementInterface"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# updateDeviceManagementInterface
#
# Description: Update the management interface settings for a device
# Endpoint: PUT /devices/{serial}/managementInterface
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-device-management-interface
#
# Request body schema:
#     wan1: Object. WAN 1 settings
#     wan2: Object. WAN 2 settings (only for MX devices)

def updateDeviceManagementInterface(apiKey, serial, body=None):
    url = "/devices/" + str(serial) + "/managementInterface"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetwork
#
# Description: Return a network
# Endpoint: GET /networks/{networkId}
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network

def getNetwork(apiKey, networkId):
    url = "/networks/" + str(networkId)
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceClientVpnAnyconnectVpn
#
# Description: Return the AnyConnect VPN settings of a network.
# Endpoint: GET /networks/{networkId}/appliance/clientVpn/anyconnectVpn
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-client-vpn-anyconnect-vpn

def getNetworkApplianceClientVpnAnyconnectVpn(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/clientVpn/anyconnectVpn"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# updateNetworkApplianceClientVpnAnyconnectVpn
#
# Description: Update the AnyConnect VPN settings of a network.
# Endpoint: PUT /networks/{networkId}/appliance/clientVpn/anyconnectVpn
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-client-vpn-anyconnect-vpn
#
# Request body schema:
#     enabled: Boolean. Whether or not AnyConnect VPN is enabled.
#     subnet: String. Subnet in CIDR format for clients connected to the AnyConnect Client VPN
#     ipv6: Object. List of IPv6 configurations
#     domainName: String. The domain name that will be appended to clients' DNS queries that omit the domain field.
#     sslPort: Integer. Port on the MX where AnyConnect will establish a SSL connection on. If this is not set, the default is 443.
#     banner: String. Welcome message shown to clients after they successfully connect to the AnyConnect VPN.
#     authType: String. Type of authentication for clients. It can take 3 different values: 'radius', 'meraki', 'active_directory'
#     radiusServers: Array. List of RADIUS servers used for authentication. Only configurable if authType is set to 'radius'
#     activeDirectoryServers: Array. List of active directory servers used for authentication. Only configurable if authType is set to 'active_directory'
#     dnsMode: String. Mode of the DNS nameserver. It can take 3 different values: 'google_dns', 'opendns', 'custom'
#     dnsCustomNameservers: Array. List of custom DNS nameservers. This param is only valid if the dnsMode is set to 'custom'.
#     splitTunnelMode: String. Specify if the split tunnel destinations should be included in or excluded from the VPN tunnel. It can take 3 different values: 'Disabled', 'Include', 'Exclude'
#     splitTunnelDestinations: Array. Specify the list of destinations in CIDR format that should be included or excluded from the VPN tunnel.

def updateNetworkApplianceClientVpnAnyconnectVpn(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/clientVpn/anyconnectVpn"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# getNetworkApplianceClientVpnIpsec
#
# Description: Return the IPsec VPN settings of a network. Only valid for MX networks.
# Endpoint: GET /networks/{networkId}/appliance/clientVpn/ipsec
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-client-vpn-ipsec

def getNetworkApplianceClientVpnIpsec(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/clientVpn/ipsec"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# updateNetworkApplianceClientVpnIpsec
#
# Description: Update the IPsec VPN settings of a network. Only valid for MX networks.
# Endpoint: PUT /networks/{networkId}/appliance/clientVpn/ipsec
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-client-vpn-ipsec
#
# Request body schema:
#     enabled: Boolean. Enables / disables the IPsec VPN.
#     sharedSecret: String. Shared secret required for end-users to establish connection.
#     ipv4: Object. IPv4 settings

def updateNetworkApplianceClientVpnIpsec(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/clientVpn/ipsec"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
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

# updateNetworkApplianceVpnSiteToSiteVpn
#
# Description: Update the site-to-site VPN settings of a network. Only valid for MX networks in NAT mode.
# Endpoint: PUT /networks/{networkId}/appliance/vpn/siteToSiteVpn
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-vpn-site-to-site-vpn
#
# Request body schema:
#     mode: String. The site-to-site VPN mode. Can be one of 'none', 'spoke' or 'hub'
#     hubs: Array. The list of VPN hubs, in order of preference. In spoke mode, at least 1 hub is required.
#     subnets: Array. The list of subnets and their VPN presence.
#     peerSgtCapable: Boolean. Whether or not Peer SGT is enabled for traffic to this VPN peer.

def updateNetworkApplianceVpnSiteToSiteVpn(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/vpn/siteToSiteVpn"
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

NET_MAPPINGS = {}

def mapSourceNetworksToTargetNetworks(apiKey, config, targetOrgId):
    global NET_MAPPINGS
    
    checkedOrgs = []
    
    success, errors, targetNetworks = getOrganizationNetworks(apiKey, targetOrgId)
    if not success:
        killScript("Unable to fetch target networks' list")
            
    for network in config:
        if not network['orgId'] in checkedOrgs:
            success, errors, sourceNetworks = getOrganizationNetworks(apiKey, network['orgId'])
            if not success:
                killScript("Unable to fetch target networks' list")
            for sourceNet in sourceNetworks:
                if not sourceNet['id'] in NET_MAPPINGS:
                    targetNetId = getNetworkIdByName(targetNetworks, sourceNet['name'])
                    if not targetNetId is None:
                        NET_MAPPINGS[sourceNet['id']] = targetNetId
            checkedOrgs.append(network['orgId'])

def exportDevices(apiKey, organizationId, tag, deviceFilter, vpnMode, fileName):
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
            'id'        : netId,
            'orgId'     : organizationId,
            'devices'   : []
        }
        for device in netDevices:
            if device['model'].lower().startswith(deviceFilter.lower()):
                deviceRecord = {
                    'serial'        : device['serial'],
                    'model'         : device['model']
                }
                if 'lat' in device:
                    deviceRecord['lat'] = device['lat']
                if 'lng' in device:
                    deviceRecord['lng'] = device['lng']
                if 'address' in device:
                    deviceRecord['address'] = device['address']
                if 'name' in device:
                    deviceRecord['name'] = device['name']
                if 'notes' in device:
                    deviceRecord['notes'] = device['notes']
                    
                success, errors, response = getDeviceManagementInterface(apiKey, device['serial'])
                if not response is None:
                    deviceRecord['managementInterface'] = response
                    
                if device['model'].startswith('MX') or device['model'].startswith('Z'):
                    success, errors, response = getNetworkAppliancePorts(apiKey, netId)
                    if not response is None:
                        deviceRecord['appliancePorts'] = response
                    success, errors, response = getNetworkApplianceSsids(apiKey, netId)
                    if not response is None:
                        deviceRecord['applianceSsids'] = response
                    if vpnMode in ['client', 'both']:
                        success, errors, response = getNetworkApplianceClientVpnAnyconnectVpn(apiKey, netId)
                        if not response is None:
                            deviceRecord['vpnClientAnyconnect'] = response
                        success, errors, response = getNetworkApplianceClientVpnIpsec(apiKey, netId)
                        if not response is None:
                            deviceRecord['vpnClientIpsec'] = response
                    if vpnMode in ['site', 'both']:
                        success, errors, response = getNetworkApplianceVpnSiteToSiteVpn(apiKey, netId)
                        if not response is None:
                            deviceRecord['vpnSiteToSite'] = response
                elif device['model'].startswith('MS'):
                    success, errors, response = getDeviceSwitchPorts(apiKey, device['serial'])
                    if not response is None:
                        allCleanPorts = []
                        for port in response:
                            singleCleanPort = {}
                            for attr in port:
                                if attr != 'linkNegotiationCapabilities':
                                    singleCleanPort[attr] = port[attr]
                            allCleanPorts.append(singleCleanPort)
                        deviceRecord['switchPorts'] = allCleanPorts
                netRecord['devices'].append(deviceRecord)
        networks.append(netRecord)
        
    try:
        f = open(fileName, 'w')
        json.dump(networks, f, indent=4)
        f.close()
    except:
        killScript('Unable to write to file "%s"' % fileName)
        
    log('File "%s" written' % fileName)
        

def unclaimDevices(apiKey, organizationData, networkTag, deviceFilter):
    log('Organization: %s (%s)' % (organizationData['name'], organizationData['id']))
    log('Network tag: %s' % networkTag)
    if deviceFilter != "":
        log('Device model filter: %s' % deviceFilter)
    print('\nWARNING: THIS OPERATION IS NOT REVERSIBLE\nMAKE SURE YOU HAVE EXPORTED YOUR CONFIGURATION BEFORE CONTINUING\n')
    print('UNCLAIMING WILL START IN 30 SECONDS\nQUIT THIS SCRIPT NOW TO CANCEL\n')
    time.sleep(30)
    
    log("Creating device configuration backup...")
    exportDevices(apiKey, organizationData['id'], networkTag, deviceFilter, 'both', generateOutputFileName(None))
    
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
                if device['model'].lower().startswith(deviceFilter.lower()):
                    success, errors, response = removeNetworkDevices(apiKey, net['id'], body={'serial': device['serial']})
                    if not success:
                        log('WARNING: Unable to remove device %s from network' % device['serial'])
                        continue
                        
                    success, errors, response = releaseFromOrganizationInventory(apiKey, organizationData['id'], body={'serials': [device['serial']]})
                    if not success:
                        log('WARNING: Unable to unclaim device %s' % device['serial'])
                    
    log('Released devices may take several minutes to be available for claiming in a different organization. This is normal')
    

def importDevices(apiKey, organizationId, tag, deviceFilter, vpnMode, filename, refreshConfigOnly=False):
    try:
        f = open(filename, 'r')
        networkData = json.load(f)
        f.close()
    except:
        killScript('Unable to read file "%s"' % filename)
        
    mapSourceNetworksToTargetNetworks(apiKey, networkData, organizationId)
        
    success, errors, orgNetworks = getOrganizationNetworks(apiKey, organizationId)
    if orgNetworks is None:
        killScript('Unable to fetch networks')
            
    for net in networkData:
        netId = getNetworkIdByName(orgNetworks, net['name'])
        if netId is None:
            log('WARNING: Organization does not contain network with name "%s"' % net['name'])
            continue            
        
        for device in net['devices']:
            if device['model'].lower().startswith(deviceFilter.lower()):
                
                if not refreshConfigOnly:
                    success, errors, response = claimNetworkDevices(apiKey, netId, body={'serials': [device['serial']]})
                    if not success:
                        log('WARNING: Unable to claim device %s' % device['serial'])
                        continue
                    
                payload = {}
                if 'name' in device:
                    payload['name']             = device['name']
                if 'address' in device:
                    payload['address']          = device['address']
                if 'lat' in device:
                    payload['lat']              = device['lat']
                    payload['moveMapMarker']    = True
                if 'lng' in device:
                    payload['lng']              = device['lng']
                    payload['moveMapMarker']    = True
                if 'notes' in device:
                    payload['notes']            = device['notes']
                if payload != {}:
                    success, errors, response   = updateDevice(apiKey, device['serial'], body=payload)
                    
                if 'managementInterface' in device:
                    # updateDeviceManagementInterface(apiKey, serial, body=None)
                    success, errors, response = updateDeviceManagementInterface(apiKey, device['serial'], body=device['managementInterface'])
                    
                if 'appliancePorts' in device:
                    # updateNetworkAppliancePort(apiKey, networkId, portId, body=None)
                    for port in device['appliancePorts']:
                        portPayload = {}
                        for attr in port:
                            if attr != 'number':
                                portPayload[attr] = port[attr]
                        success, errors, response = updateNetworkAppliancePort(apiKey, netId, port['number'], body=portPayload)
                if 'applianceSsids' in device:
                    # updateNetworkApplianceSsid(apiKey, networkId, number, body=None)
                    for ssid in device['applianceSsids']:
                        ssidPayload = {}
                        for attr in ssid:
                            if attr != 'number':
                                ssidPayload[attr] = ssid[attr]
                        success, errors, response = updateNetworkApplianceSsid(apiKey, netId, ssid['number'], body=ssidPayload)
                if vpnMode in ['client', 'both']:
                    if 'vpnClientAnyconnect' in device:
                        if device['vpnClientAnyconnect']['enabled']:
                            acPayload = {}
                            for prop in device['vpnClientAnyconnect']:
                                if prop != 'hostname':
                                    acPayload[prop] = device['vpnClientAnyconnect'][prop]
                            success, errors, response = updateNetworkApplianceClientVpnAnyconnectVpn(apiKey, netId, body=acPayload)
                    if 'vpnClientIpsec' in device:
                        if device['vpnClientIpsec']['enabled']:
                            ipsecPayload = {}
                            for prop in device['vpnClientIpsec']:
                                if prop != 'hostname':
                                    ipsecPayload[prop] = device['vpnClientIpsec'][prop]
                            success, errors, response = updateNetworkApplianceClientVpnIpsec(apiKey, netId, body=ipsecPayload)                    
                if vpnMode in ['site', 'both']:
                    if 'vpnSiteToSite' in device:
                        if device['vpnSiteToSite']['mode'] == 'hub':
                            success, errors, response = updateNetworkApplianceVpnSiteToSiteVpn(apiKey, netId, body=device['vpnSiteToSite'])
                        elif device['vpnSiteToSite']['mode'] == 'spoke':
                            cleanSiteToSite = {}
                            for prop in device['vpnSiteToSite']:
                                if prop != 'hubs':
                                    cleanSiteToSite[prop] = device['vpnSiteToSite'][prop]
                                else:
                                    cleanHubs = []
                                    for hub in device['vpnSiteToSite']['hubs']:
                                        cHub = {}
                                        for attr in hub:
                                            if attr != 'hubId':
                                                cHub[attr] = hub[attr]
                                            else:
                                                if hub[attr] in NET_MAPPINGS:
                                                    cHub[attr] = NET_MAPPINGS[hub[attr]]
                                        cleanHubs.append(cHub)
                                    cleanSiteToSite['hubs'] = cleanHubs
                            success, errors, response = updateNetworkApplianceVpnSiteToSiteVpn(apiKey, netId, body=cleanSiteToSite)
                        
                if 'switchPorts' in device:
                    # updateDeviceSwitchPort(apiKey, serial, portId, body=None)
                    for port in device['switchPorts']:
                        portPayload = {}
                        for attr in port:
                            if attr != 'portId':
                                portPayload[attr] = port[attr]
                        success, errors, response = updateDeviceSwitchPort(apiKey, device['serial'], port['portId'], body=portPayload)  
        
def main(argv):  
    # migrate_devices.py [-k <api_key>] -o <org_name> -m <mode> [-t <tag>] [-f <file>]
    arg_apiKey          = None
    arg_orgName         = None
    arg_mode            = None
    arg_tag             = None
    arg_fileName        = None
    arg_deviceFilter    = ""
    arg_vpn             = "none"
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:m:t:d:f:v:h')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey          = str(arg)
        if opt == '-o':
            arg_orgName         = str(arg)
        if opt == '-m':
            arg_mode            = str(arg)
        if opt == '-t':
            arg_tag             = str(arg)
        if opt == '-d':
            arg_deviceFilter    = str(arg)
        if opt == '-f':
            arg_fileName        = str(arg)
        if opt == '-v':
            arg_vpn             = str(arg)
        if opt == '-h':
            killScript()
            
    apiKey = getApiKey(arg_apiKey)
    if apiKey is None:
        log("ERROR: API key not found")
        killScript()
        
    if arg_orgName is None:
        log("ERROR: No organization name provided")
        killScript()
        
    if not arg_mode in ['export', 'unclaim', 'import', 'refresh']:
        killScript('Parameter -m <mode> must be one of export, unclaim, import, refresh')
        
    if arg_mode in ['import', 'refresh'] and arg_fileName == None:
        killScript('Import and refresh modes require parameter -f <file_name>')
        
    if arg_mode in ['export', 'unclaim'] and arg_tag is None:
        killScript('Modes export, unclaim require parameter -t <network_tag>')
         
    vpnMode = arg_vpn.lower()
    if not vpnMode in ['none', 'client', 'site', 'both']:
        killScript('Invalid parameter "-v %s"' % arg_vpn)
        
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
        exportDevices(apiKey, org['id'], arg_tag, arg_deviceFilter, vpnMode, generateOutputFileName(arg_fileName))
        
    elif arg_mode == 'unclaim':
        log('Unclaiming devices from organization "%s"...' % org['name'])
        unclaimDevices(apiKey, org, arg_tag, arg_deviceFilter)
        
    elif arg_mode == 'import':
        log('Importing devices into organization "%s"...' % org['name'])
        importDevices(apiKey, org['id'], arg_tag, arg_deviceFilter, vpnMode, arg_fileName)
        
    elif arg_mode == 'refresh':
        log('Refreshing device config for organization "%s"...' % org['name'])
        importDevices(apiKey, org['id'], arg_tag, arg_deviceFilter, vpnMode, arg_fileName, True)
        
    log('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])