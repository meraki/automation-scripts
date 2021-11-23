readMe = """Python 3 script that lists all clients with IPv4 addresses within the specified range or subnet.

Script syntax, Windows:
    python clients_in_ip_range.py [-k <api_key>] -i <ip_range> [-o <org_name>]
 
Script syntax, Linux and Mac:
    python3 clients_in_ip_range.py [-k <api_key>] -i <ip_range> [-o <org_name>]
    
Mandatory parameters:
    -i <ip_range>           The IP range or subnet to match client IP addresses against
                            Valid forms:
                                <network_ip>/<netmask bits>
                                <start_ip>-<end_ip>
    
Optional parameters:
    -k <api_key>            Your Meraki Dashboard API key. If left blank, the script will look for an
                            OS environment variable named "MERAKI_DASHBOARD_API_KEY" and load the key
                            from there instead                            
    -o <org_name>           Specify the name of the organization to scan for matching clients.
                            If omitted, all organizations will be scanned
                            
Example, find all clients in organization "Big Industries Inc" belonging to subnet 10.0.0.0/8
    python clients_in_ip_range.py -k 1234 -o "Big Industries Inc" -i 10.0.0.0/8
    
Example, find all clients in all organizations with IP addresses between 10.10.10.1 and 10.20.20.20
    python clients_in_ip_range.py -k 1234 -o "Big Industries Inc" -i 10.10.10.1-10.20.20.20
    
Required Python 3 modules:
    requests
    
To install these Python 3 modules via pip you can use the following commands:

Windows:
    pip install requests
    
Linux/Mac:
    pip3 install requests
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""


import sys, getopt, time, datetime, ipaddress, os

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

API_KEY_ENV_VAR_NAME    = "MERAKI_DASHBOARD_API_KEY"


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
    
def getNetworkClients(apiKey, networkId, timespan=2678400):
    endpoint = "/networks/%s/clients?timespan=%s" % (networkId, timespan)
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
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
        
        
def parseIpSubnets(ipRangeString):
    result = []

    if ipRangeString.find("-") != -1:
        splitStr = ipRangeString.split("-")
        try:
            first = ipaddress.IPv4Address(splitStr[0])
            last = ipaddress.IPv4Address(splitStr[1])
            for subnet in ipaddress.summarize_address_range(first, last):
                result.append(subnet)
        except:
            result = None
    else:
        try:
            result.append(ipaddress.ip_network(ipRangeString))
        except:
            result = None
    return result
    
    
def expandSubnets(subnets):
    hosts = []
    for subnet in subnets:
        for host in subnet.hosts():
            hosts.append(host)
    return hosts
    
    
def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get(API_KEY_ENV_VAR_NAME, None) 
    
        
def main(argv):    
    arg_apiKey  = None
    arg_orgName = None
    arg_ipRange = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:i:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey  = str(arg)
        if opt == '-o':
            arg_orgName = str(arg)
        if opt == '-i':
            arg_ipRange = str(arg)
            
    apiKey = getApiKey(arg_apiKey)
            
    if apiKey is None or arg_ipRange is None:
        killScript()        
        
    log("Expanding subnets...")
    
    subnets = parseIpSubnets(arg_ipRange)    
    hosts = expandSubnets(subnets)
        
    if subnets is None:
        killScript("Invalid IP range/subnet")
        
    log("Fetching information from Meraki cloud...")
    
    success, errors, headers, allOrganizations = getOrganizations(apiKey)
    
    if allOrganizations is None:
        killScript("Unable to fetch organizations for that API key")
            
    orgs = []
    
    if arg_orgName is None:
        orgs = allOrganizations
        
    else:        
        organizationId      = None
        organizationName    = None
        
        for org in allOrganizations:
            if org['name'] == arg_orgName:
                orgs.append(org)
                break
                
        if len(orgs) == 0:
            killScript("No organization found with that name")
                                
    for org in orgs:
        org["networks"] = []
        success, errors, headers, orgNetworks = getOrganizationNetworks(apiKey, org["id"])
        if not orgNetworks is None:
            org["networks"] = orgNetworks
            for net in org["networks"]:
                net["clients"] = []
                success, errors, headers, netClients = getNetworkClients(apiKey, net["id"])
                if not netClients is None:
                    net["clients"] = netClients    

    log("Matching client IP addresses to subnets...")
    
    printOrgs = {}
    
    for org in orgs:
        matchingNetworks = []
        for net in org["networks"]:
            log('Processing network "%s"...' % net["name"])
            matchingClients = []
            for client in net["clients"]:
                if "ip" in client and (not client["ip"] is None):
                    if ipaddress.ip_address(client["ip"]) in hosts:
                        matchingClients.append(client)
            if len(matchingClients) > 0:
                matchingNetworks.append({"name": net["name"], "clients": matchingClients})
        
        if len(matchingNetworks) > 0:
            printOrgs[org["name"]] = matchingNetworks
        
    for org in printOrgs:
            print ('\n===\n\nOrganization %s:' % org)
            for net in printOrgs[org]:
                print ('\nNetwork %s:\n' % net["name"])
                print ('%-31s %-16s %-18s %-25s %s' % ("Description", "IP","MAC", "User", "Manufacturer"))
                for client in net["clients"]:
                    description = ""
                    if not client["description"] is None:
                        description = str(client["description"])
                        if len(description) > 30:
                            description = "%s..." % description[0:27]
                    user = ""
                    if not client["user"] is None:
                        user = str(client["user"])
                        if len(user) > 24:
                            user = "%s..." % user[0:21]
                            
                    manufacturer = ""
                    if not client["manufacturer"] is None:
                        manufacturer = str(client["manufacturer"])
                        if len(manufacturer) > 24:
                            manufacturer = "%s..." % manufacturer[0:21]
                        
                    print ('%-31s %-16s %-18s %-25s %s' % (description, client["ip"],client["mac"], user, manufacturer))
                
    
if __name__ == '__main__':
    main(sys.argv[1:])
