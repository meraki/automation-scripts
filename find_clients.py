read_me = """Python 3 script to find clients with a specified string in their name
  and print their network usage statistics.

Script syntax:
    python find_clients.py -k <api key> [ -o <org name> -n <net name>
        -c <client description> -t <timespan>]
        
Mandatory parameters:
    -k <api key>            : Your Meraki Dashboard API key
    
Optional parameters:
    -o <org name>           : Organization name query string
    -n <net name>           : Network name query string
    -c <client description> : Client description query string
    -t <timespan>           : Look back timespan in days. Default is 7
    
    Ommiting a query string will match all items. Query strings are not
    case sensitive.

Example:
    python find_clients.py -k 1234 -o "Big Industries" -c "iphone"

Required Python 3 modules:
    requests
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""

import sys, getopt, time, datetime

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
FLAG_REQUEST_VERBOSE    = False

#change this to "https://api.meraki.com/api/v1" to disable mega proxy
API_BASE_URL            = "https://api-mp.meraki.com/api/v1"


def merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders=None, p_queryItems=None, 
        p_requestBody=None, p_verbose=False, p_retry=0):
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
            print("INFO: Hit max request rate. Retrying %s after %s seconds" % (p_retry+1, r.headers["Retry-After"]))
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
                        responseBody = responseBody + nextBody
                else:
                    responseBody = None
    
    return success, errors, responseHeaders, responseBody
    
def getOrganizations(p_apiKey):
    endpoint = "/organizations"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
def getNetworks(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/networks" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
   
def getNetworkClients(p_apiKey, p_networkId, p_timespan):
    endpoint = "/networks/%s/clients" % p_networkId
    query = {"timespan": p_timespan}
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    

def killScript(reason=None):
    if reason is None:
        print(read_me)
    else:
        print("ERROR: %s" % reason)
    sys.exit(2)
    
    
def filterByKeyValue (array, key, value):
    queryStr = ""
    if not value is None:
        queryStr = str(value).lower()
    result = []
    if not array is None:
        for item in array:
            itemValue = ""
            if key in item:
                if not item[key] is None:
                    itemValue = str(item[key]).lower()
            position = itemValue.find(queryStr)
            if position > -1:
                result.append(item)
        
    return result


def main(argv):
    arg_apiKey          = None
    arg_orgNameQuery    = ""
    arg_netNameQuery    = ""
    arg_clientNameQuery = ""
    arg_timespanDays    = 7
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:n:c:t:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey = arg
        if opt == '-o':
            arg_orgNameQuery = arg
        if opt == '-n':
            arg_netNameQuery = arg
        if opt == '-c':
            arg_clientNameQuery = arg
        if opt == '-t':
            arg_timespanDays = arg
            
    if arg_apiKey is None:
        killScript()       
        
    try:
        timespan = int(arg_timespanDays) * 86400
    except:
        killScript("Timespan must be integer")
        
    maxTimespan = 2678400
    if timespan < 1:
        timespan = 1
    if timespan > maxTimespan:
        timespan = maxTimespan
    
    success, errors, headers, rawOrgs = getOrganizations(arg_apiKey)        
    organizations = filterByKeyValue(rawOrgs, "name", arg_orgNameQuery)
    
    for org in organizations:
        orgHeaderNotPrinted = True
        success, errors, headers, rawNets = getNetworks(arg_apiKey, org["id"])
        networks = filterByKeyValue(rawNets, "name", arg_netNameQuery)       
        
        for net in networks:
            netHeaderNotPrinted = True
            success, errors, headers, rawClients = getNetworkClients(arg_apiKey, net["id"], timespan)
            clients = filterByKeyValue(rawClients, "description", arg_clientNameQuery)
            if len(clients) > 0:
                for client in clients:
                    if (orgHeaderNotPrinted):
                        print('\n\nResults for organization "%s" (%s):' % (org["name"], org["id"]))
                        orgHeaderNotPrinted = False
                    if (netHeaderNotPrinted):
                        print ('\nNetwork "%s" (%s):' % (net["name"], net["id"]))
                        print('%-32s %-18s %-16s %-13s %s' % ("Description", "Mac", "IP", "Up KB", "Down KB"))
                        netHeaderNotPrinted = False
                        
                    description = "<none>"
                    if "description" in client:
                        if not client["description"] is None:
                            descStr = str(client["description"])
                            if len(descStr) > 32:
                                description = descStr[:29] + "..."
                            else: 
                                description = descStr
                        
                    
                    print('%-32s %-18s %-16s %-13s %s' % (
                        description, 
                        client["mac"],
                        client["ip"],
                        client["usage"]["recv"],
                        client["usage"]["sent"]))
    print("\nEnd or results")
    
if __name__ == '__main__':
    main(sys.argv[1:])