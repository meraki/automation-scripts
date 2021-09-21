readMe = """A Python 3 script to create a Postman collection for the Meraki Dashboard API v1. The collection
is created by fetching the OpenAPI 2.0 specification of a Meraki dashboard organization.
Items will created for all endpoints available to that organization, including possible alpha/beta ones.

Script syntax, Windows:
    python postman_collection_generator.py -k <api_key> [-o <org_name>]
 
Script syntax, Linux and Mac:
    python3 postman_collection_generator.py -k <api_key> [-o <org_name>]
    
Mandatory parameters:
    -k <api_key>    Your Meraki Dashboard API key
    
Optional parameters: 
    -o <org_name>   The name of the organization to fetch the OpenAPI 2.0 spec from. If omitted, the script
                    will use the first one accessible by the specified API key
                   
Example, use organization with name "Big Industries Inc" to generate a Postman collection:
    python postman_collection_generator.py -k 1234 -o "Big Industries Inc"

Output:
    The output of the script is a file with name format "Meraki_Dashboard_API_v1_-_<timestamp>.json".
    It can be imported into Postman by using the import file function of the Postman UI.
                   
Required Python 3 modules:
    requests
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    
Depending on your operating system and Python environment, you may need to use commands 
"python3" and "pip3" instead of "python" and "pip".
"""


import sys, getopt, time, datetime, json, re

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

#Set to True or False to enable/disable console logging of sent API requests
FLAG_REQUEST_VERBOSE        = True

API_BASE_URL                = "https://api.meraki.com/api/v1"

DEFAULT_CONFIG_FILE_NAME    = "config.yaml"

KEYWORDS = ["DHCP", "SNMP", "SM", "IdPs", "SSIDs", "SAML", "VPN", "VPP", "APNS", "MQTT", "LAN", "CDP", "LLDP",
    "OpenAPI", "HTTP", "API", "RF", "VLAN", "STP", "QoS", "MTU", "DSCP", "CoS", "PII"]


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
    return success, errors, response    
    
def getOrganizationOpenapiSpec(apiKey, organizationId):
    endpoint = "/organizations/%s/openapiSpec" % organizationId
    success, errors, headers, response = merakiRequest(apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
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
                       
           
def camelCaseSplit(identifier):
    # https://stackoverflow.com/questions/29916065/how-to-do-camelcase-split-in-python
    matches = re.finditer('.+?(?:(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])|$)', identifier)
    return [m.group(0) for m in matches]
    
def fixKeywordCapitalization(word): 
    for key in KEYWORDS:
        if word == key.lower():
            return key
    return word.capitalize()
    
def findCategoryForMethod(methodObject):
    try:        
        outstr = ""
        
        splitTagZero = camelCaseSplit(methodObject["tags"][0])
        for word in splitTagZero:
            fixedWord = fixKeywordCapitalization(word.lower())
            if len(outstr) != 0:
                outstr += " "
            outstr += fixedWord
                        
        if len(methodObject["tags"]) >= 3:
            splitTagTwo = camelCaseSplit(methodObject["tags"][2])
            for word in splitTagTwo:
                fixedWord = fixKeywordCapitalization(word.lower())
                outstr += " %s" % fixedWord
          
        return outstr
        
    except:
        return "Unclassified"
    
    
def createCategoryObject(array, label):
    for item in array:
        if item["name"] == label:
            return item
            
    return {"name": label, "item": []} 
    
    
def cleanDescription(string):
    returnString = ""
    
    splitString = string.split("<")    
    processed = splitString[0]
    if processed[len(processed)-1] == ".":
        processed = processed[:-1]

    words = processed.split(" ")
    filteredWords = []
    
    for word in words:
        if not word.lower() in ["a", "the", "an"]:
            filteredWords.append(word)
            
    lastWordIndex = len(filteredWords)
    flagTruncated = False
    if lastWordIndex > 10:
        flagTruncated = True
        lastWordIndex = 10
        
    truncatedList = []    
    for i in range(0, lastWordIndex):
        truncatedList.append(filteredWords[i])        
            
    processed = " ".join(truncatedList)
    
    if flagTruncated:
        processed += "..."
    
    return processed
   

def findVariablesInPath(path):
    return re.findall(r'\{[a-zA-Z]*\}', path)    
   
    
def convertPathToPostmanFormat(path, variables):
    if len(variables) == 0:
        return path
    
    result = ""
    rest = path
    previousEnd = 0
    for var in variables:
        chunks = rest.split(var)
        result += chunks[0]
        result += ":%s" % var[1:-1]
        rest = rest[len(chunks[0])+len(var):]        
    result += rest
    
    return result
    
    
def extractObjectFromBodyParameter(bodyParam):
    result = {}
    
    properties = bodyParam["properties"]
    for item in properties:
        if properties[item]["type"] == "object":
            result[item] = extractObjectFromBodyParameter(properties[item])
        elif properties[item]["type"] == "array":
            result[item] = extractArrayFromBodyParameter(properties[item])
        else:
            result[item] = "<%s>" % properties[item]["type"]
    return result
    
    
def extractArrayFromBodyParameter(bodyParam):
    result = []    
    item = bodyParam["items"]
    if item["type"] == "object":
        result.append(extractObjectFromBodyParameter(item))
    elif item["type"] == "array":
        result.append(extractArrayFromBodyParameter(item))
    else:
        result.append("<%s>" % item["type"])
    return result
    
    
def createEndpoint(path, methodLabel, methodObject):
    returnObject = {
        "name": cleanDescription(methodObject["summary"]),
        "protocolProfileBehavior": {
            "followAuthorizationHeader": True
        },
        "request": {
            "method": methodLabel.upper(),
            "header": [
                {
                    "key": "X-Cisco-Meraki-API-Key",
                    "value": ""
                },
                {
                    "key": "Content-Type",
                    "value": "application/json"
                }
            ],
            "url": {
                "raw": "",
                "host": [ "{{baseUrl}}" ],
                "path": [],
            },
        },
        "response": [],
        "description": ""
    }
    
    variables = findVariablesInPath(path)
    for var in variables:
        variableRecord = {
            "key":          var[1:-1],
            "value":        "{%s}" % var,
            "description":  "Required"
        }
        if not "variable" in returnObject["request"]["url"]:
            returnObject["request"]["url"]["variable"] = []
        returnObject["request"]["url"]["variable"].append(variableRecord)
        
    pathInPostmanFormat = convertPathToPostmanFormat(path, variables)
    returnObject["request"]["url"]["raw"] = "{{baseUrl}}%s" % pathInPostmanFormat
    
    splitPath = pathInPostmanFormat.split("/")
    for node in splitPath:
        if node != "":
            returnObject["request"]["url"]["path"].append(node)   

    if "parameters" in methodObject:
        for var in methodObject["parameters"]:
            if var["in"] == "query":
                queryRecord = {
                    "key"           : var["name"],
                    "value"         : "{{%s}}" % var["name"]
                }
                queryItemDescription = ""            
                if "required" in var and var["required"]:
                    queryItemDescription = "REQUIRED. "
                    queryRecord["disabled"] = False
                else:
                    queryRecord["disabled"] = True
                queryItemDescription += "Type: %s. " % var["type"]
                queryItemDescription += var["description"]
                queryRecord["description"] = queryItemDescription
                
                if not "query" in returnObject["request"]["url"]:
                    returnObject["request"]["url"]["query"] = []
                returnObject["request"]["url"]["query"].append(queryRecord)
    
    requestBody = { "mode": "raw", "raw": ""}
    bodyRaw = {}
    if "parameters" in methodObject:
        for var in methodObject["parameters"]:
            if var["in"] == "body":
                bodyItems = var["schema"]["properties"]
                for item in bodyItems:
                    if bodyItems[item]["type"] == "array":
                        bodyRaw[item] = extractArrayFromBodyParameter(bodyItems[item])
                    elif bodyItems[item]["type"] == "object":
                        bodyRaw[item] = extractObjectFromBodyParameter(bodyItems[item])
                    else:
                        bodyRaw[item] = "<%s>" % bodyItems[item]["type"]
                    
    if bodyRaw != {}:
        requestBody["raw"] = json.dumps(bodyRaw, indent=4)
                    
    if len(requestBody["raw"]) > 0:
        returnObject["request"]["body"] = requestBody                    
    
    return returnObject
    
    
def mergeCategoryObject(array, categoryObject):
    returnObject = array
    for record in returnObject:
        if record["name"] == categoryObject["name"]:
            record["item"] = categoryObject["item"]
            return returnObject
    returnObject.append(categoryObject)
    return returnObject
    
    
def findArrayIndexForKey(name, key, array):
    for i in range(0, len(array)):
        if array[i][key] >= name:
            return i
    return None
        
    
    
def sortOutputItemCategories(array):
    result = []
    
    for item in array:
        index = findArrayIndexForKey(item["name"], "name", result)
        if index is None:
            result.append(item)
        else:
            before = result[:index]
            after = result[index:]
            result = before + [item] + after
    
    return result
    
    
def keyIsDuplicate(key, array):
    for item in array:
        if item["key"] == key:
            return True
    return False
    
    
def extractVariableList(itemList):
    raw = []
    
    for category in itemList:
        for endpoint in category["item"]:
            url = endpoint["request"]["url"]
            if "variable" in url:
                for var in url["variable"]:
                    if not keyIsDuplicate(var["key"], raw):
                        raw.append({"key": var["key"], "value": ""})
                
    result = []          
    for item in raw:
        index = findArrayIndexForKey(item["key"], "key", result)
        if index is None:
            result.append(item)
        else:
            before = result[:index]
            after = result[index:]
            result = before + [item] + after
                
    return result
   
   
def main(argv):    
    arg_apiKey  = None
    arg_orgName = None
    
    try:
        opts, args = getopt.getopt(argv, 'k:o:')
    except getopt.GetoptError:
        killScript()
        
    for opt, arg in opts:
        if opt == '-k':
            arg_apiKey  = str(arg)
        if opt == '-o':
            arg_orgName = str(arg)
                    
    if arg_apiKey == None:
        killScript()
        
    apiKey = arg_apiKey
        
    success, errors, allOrgs = getOrganizations(apiKey)    
    if allOrgs is None:
        killScript("Unable to fetch organizations")
        
    organizationId = None
    organizationName = None
     
    if arg_orgName is None and len(allOrgs) > 0:
        organizationId      = allOrgs[0]['id']        
        organizationName    = allOrgs[0]['name']        
    else:    
        for org in allOrgs:
            if org['name'] == arg_orgName:
                organizationId      = org['id']
                organizationName    = org['name']
                break            
    if organizationId is None:
        killScript("Unable to find matching organization")   
        
    log('Using organization %s: "%s"' % (organizationId, organizationName))
            
    success, errors, openApiSpec = getOrganizationOpenapiSpec(apiKey, organizationId)
    if openApiSpec is None:
        killScript("Unable to fetch OpenAPI 2.0 spec")   
    
    timestampFilenameFriendly = ("%s" % datetime.datetime.now()).replace(":",".").replace(" ", "_")
    today = datetime.datetime.now().strftime("%Y-%m-%d")
        
    outputObject = {
        "info": {
            "name": "Meraki Dashboard API v1 - %s" % today,
            "description": "The Cisco Meraki Dashboard API is a modern REST API based on the OpenAPI specification.\n\n\n> Date: %s\n>\n> [What's New](https://meraki.io/whats-new/)\n\n---\n\n[API Documentation](https://meraki.io/api)\n\n[Community Support](https://meraki.io/community)\n\n[Meraki Homepage](https://www.meraki.com)" % today,
            "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
        },
        "auth": {
            "type": "apikey",
            "apikey": [
                {
                    "key": "value",
                    "value": "{{apiKey}}",
                    "type": "string"
                },
                {
                    "key": "key",
                    "value": "X-Cisco-Meraki-API-Key",
                    "type": "string"
                }
            ]
        },
        "variable": [],
        "item": []
    }
    
    for path in openApiSpec["paths"]:
        for method in openApiSpec["paths"][path]:
            category = findCategoryForMethod(openApiSpec["paths"][path][method])
            categoryObject = createCategoryObject(outputObject["item"], category)
            categoryObject["item"].append(createEndpoint(path, method, openApiSpec["paths"][path][method]))
            outputObject["item"] = mergeCategoryObject(outputObject["item"], categoryObject)
            
    outputObject["item"] = sortOutputItemCategories(outputObject["item"])
    
    outputObject["variable"] = extractVariableList(outputObject["item"])
        
    fileName = "Meraki_Dashboard_API_v1_-_%s.json" % timestampFilenameFriendly
    
    with open(fileName, 'w') as outfile:
        json.dump(outputObject, outfile, indent=4)
        
    log('File "%s" written' % fileName)
    
if __name__ == '__main__':
    main(sys.argv[1:])