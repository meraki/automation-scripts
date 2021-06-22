readMe = """Python 3 script that builds a Node.js SDK for the Meraki
 Dashboard API by reading the OpenAPI spec of an organization.

Script syntax, Windows:
    python node-sdk-builder.py -k <api_key> [-o <org_name>] [-f <output_file_name>]
 
Script syntax, Linux and Mac:
    python3 node-sdk-builder.py -k <api_key> [-o <org_name>] [-f <output_file_name>]
    
Mandatory parameters:
    -k <api_key>            Your Meraki Dashboard API key
    
Optional parameters:
    -o <org_name>           Specify the name of the organization to pull the OpenAPI
                            spec from. If omitted, the first available org will be 
                            selected
    -f <output_file_name>   Specify the name of the output file. If omitted, 
                            "Meraki_<timestamp>.js" will be used
                            
Example, build a Node.js SDK:
    python node-sdk-builder.py -k 1234
    
Required Python 3 modules:
    requests
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
"""


import sys, getopt, time, datetime, json

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

DOCS_BASE_URL           = ""

TEMPLATE_FILE_SDK_CORE  = "sdk_core.template"
TEMPLATE_FILE_ENDPOINT  = "endpoint.template"


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
    
    
def getOrganizations(p_apiKey):
    endpoint = "/organizations"
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response    
    
    
def getOrganizationOpenapiSpec(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/openapiSpec" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
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
        
        
def generateOutputFileName(argFile):
    if argFile is None:
        timestampIso = datetime.datetime.now().isoformat()
        timestampFileNameFriendly = timestampIso.replace(":",".")
        name = "Meraki_" + timestampFileNameFriendly + ".js"
        return name
    else:
        return argFile
               
        
def loadFile(filename):
    with open(filename, 'r') as file:
        data = file.read()
    return data
    
  
def dashifyOperationId(operationId):
    result = ""

    for char in operationId:
        if char.isupper():
            result += "-%s" % char.lower()
        else:
            result += char

    return result
    
        
def main(argv):    
    arg_apiKey      = None
    arg_orgName     = None
    arg_fileName    = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:f:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey      = str(arg)
        if opt == '-o':
            arg_orgName     = str(arg)
        if opt == '-f':
            arg_fileName    = str(arg)
            
    if arg_apiKey is None:
        killScript()        
    
    outputFileName      = generateOutputFileName(arg_fileName)
    coreTemplate        = loadFile(TEMPLATE_FILE_SDK_CORE)
    endpointTemplate    = loadFile(TEMPLATE_FILE_ENDPOINT)
    
    success, errors, headers, organizations = getOrganizations(arg_apiKey)
    
    if organizations is None:
        killScript("Unable to fetch organizations for that API key")
    
    if len(organizations) == 1:
        organizationId = organizations[0]['id']
    else:
        if arg_orgName is None:
            organizationId = organizations[0]['id']
            
        else:        
            organizationId      = None
            organizationName    = None
            
            for org in organizations:
                if org['name'] == arg_orgName:
                    organizationId = org['id']
                    organizationName = org['name']
                    break
                    
            if organizationId is None:
                killScript("No organization found with that name")
                                
    success, errors, headers, openApiSpec = getOrganizationOpenapiSpec(arg_apiKey, organizationId)
        
    outputAllEndpoints = ""
    
    for path in openApiSpec["paths"]:
        for method in openApiSpec["paths"][path]:   
            operationId = openApiSpec["paths"][path][method]["operationId"]
            operationIdDash = dashifyOperationId(operationId)
            description = openApiSpec["paths"][path][method]["description"].replace("\n", " ")
            pathVars = []
            query = []
            body = []
            
            if "parameters" in openApiSpec["paths"][path][method]:
                for param in openApiSpec["paths"][path][method]["parameters"]:
                    if param["in"] == "path":
                        pathVars.append({"name": param["name"]})
                    elif param["in"] == "query":
                        query.append( { "name": param["name"], "description": param["description"].replace("\n", " "), "type": param["type"] } )
                    elif param["in"] == "body":
                        for bodyItem in param["schema"]["properties"]:
                            body.append( { "name": bodyItem, 
                                "description": param["schema"]["properties"][bodyItem]["description"].replace("\n", " "), 
                                "type": param["schema"]["properties"][bodyItem]["type"] } )
                    
            
            outputEndpoint = endpointTemplate
            
            outputEndpoint = outputEndpoint.replace("/* DOCS TITLE */", "// %s: %s" %(operationId, description));          
            outputEndpoint = outputEndpoint.replace("/* DOCS ENDPOINT */", "\n    // %s %s" %(method.upper(), path));          
            outputEndpoint = outputEndpoint.replace("/* OFFICIAL DOCS LINK */", "\n\n    // Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!%s" % operationIdDash);          
            outputEndpoint = outputEndpoint.replace("/* ENDPOINT ID */", operationId);
            outputEndpoint = outputEndpoint.replace("/* METHOD */", '"%s"' % method);
            
            resourcePath = '"%s"' % path
                
            if len(pathVars) > 0:
                paramString = ""
                for p in pathVars:
                    paramString += ", %s" % p["name"]
                    resourcePath = resourcePath.replace( "{%s}" % p["name"], '" + %s + "' % p["name"])
                outputEndpoint = outputEndpoint.replace("/* RESOURCE PARAM */", paramString);
            else:
                outputEndpoint = outputEndpoint.replace("/* RESOURCE PARAM */", '');
                
            outputEndpoint = outputEndpoint.replace("/* RESOURCE PATH */", resourcePath);
                
            configStr   = ""
            queryDocs   = ""
            bodyDocs    = ""
            
            if len(query) > 0:            
                outputEndpoint = outputEndpoint.replace("/* QUERY PARAM */", ', query');
                configStr = ", { query: query }"
                queryDocs = "\n\n    // Query parameters:"
                for q in query:
                    queryDocs += "\n    //   %s: %s. %s" % (q["name"], q["type"].capitalize(), q["description"])
            else:
                outputEndpoint = outputEndpoint.replace("/* QUERY PARAM */", '');
                
            outputEndpoint = outputEndpoint.replace("/* DOCS QUERY */", queryDocs);
                
            if len(body) > 0:                
                outputEndpoint = outputEndpoint.replace("/* BODY PARAM */", ', body');
                bodyDocs = "\n\n    // Request body schema:"
                for b in body:
                    bodyDocs += "\n    //   %s: %s. %s" % (b["name"], b["type"].capitalize(), b["description"])
                if len(configStr) == 0:
                    configStr = ", { data: body }"
                else:
                    configStr = ", { query: query, data: body }"
            else:
                outputEndpoint = outputEndpoint.replace("/* BODY PARAM */", '');
                
            outputEndpoint = outputEndpoint.replace("/* DOCS BODY*/", bodyDocs);
            
            outputEndpoint = outputEndpoint.replace("/* CONFIG */", configStr);
            
            outputAllEndpoints += outputEndpoint;
                       
    outputTotal = coreTemplate
    
    outputTotal = outputTotal.replace("/* FILENAME HERE */", outputFileName);
    outputTotal = outputTotal.replace("/* ENDPOINTS HERE */", outputAllEndpoints);
    
    #print(outputTotal)   

    f = open(outputFileName, 'w')
    f.write(outputTotal)
    f.close()
        
    
if __name__ == '__main__':
    main(sys.argv[1:])
