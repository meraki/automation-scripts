readMe = '''This is a script to manage administrator accounts across organizations.

Syntax, Windows:
  python manageadmins.py -k <api key> -o <org> -c <command> 
    [-a <admin email> -n <admin name> -p <privilege>]
  
Syntax, Linux and Mac:
  python3 manageadmins.py -k <api key> -o <org> -c <command> 
    [-a <admin email> -n <admin name> -p <privilege>]

Mandatory arguments:
  -k <api key>         : Your Meraki Dashboard API key
  -o <organization>    : Dashboard organizations in scope. Valid forms:
                         -o <org name>      Organizations name containing given text
                         -o /all            All organizations accessible by your API key
  -c <command>         : Command to be executed. Valid forms:
                         -c add             Add an administrator
                         -c delete          Delete an administrator
                         -c find            Find organizations in scope accessible by a 
                                            specific admin
                         -c list            List administrators

Optional arguments:
  -a <admin email>     : Email of admin account to be added/deleted/matched. Required for 
                         commands add, delete and find
  -n <admin name>      : Name for admin to be added by the "add" command. Required for "add".
  -p <privilege level> : Privilege level for admin to be added by the "add" command. Default
                         is "full". Valid options:
                         -p full             Full organization admin
                         -p read-only        Read only organization admin
 
Example, remove admin "miles.meraki@ikarem.net" from all organizations:
    python manageadmins.py -k 1234 -o /all -c delete -a miles.meraki@ikarem.net
Example, add admin "miles.meraki@ikarem.net" to all organizations with names containing 
  text "TIER1_":
    python manageadmins.py -k 1234 -o TIER1_ -c add -a miles.meraki@ikarem.net -n Miles

This script was developed using Python 3.6.4.

Required module:
  Requests: http://python-requests.org

Install the required module with the following commands:

Windows:
    pip install requests
Linux and Mac:
    pip3 install requests
'''


import sys, getopt, json, time, datetime

from urllib.parse import urlencode
from requests import Session, utils

API_MAX_RETRIES         = 3
API_CONNECT_TIMEOUT     = 60
API_TRANSMIT_TIMEOUT    = 60
API_STATUS_RATE_LIMIT   = 429

#Set to True or False to enable/disable console logging of sent API requests
FLAG_REQUEST_VERBOSE    = True

#change this to "https://api.meraki.com/api/v1" to disable mega proxy
API_BASE_URL            = "https://api-mp.meraki.com/api/v1"

class NoRebuildAuthSession(Session):
    def rebuild_auth(self, prepared_request, response):
        """
        This method is intentionally empty. Needed to prevent auth header stripping on redirect. More info:
        https://stackoverflow.com/questions/60358216/python-requests-post-request-dropping-authorization-header
        """


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
     
def getOrganizationAdmins(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/admins" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response 
    
def createOrganizationAdmin(p_apiKey, p_organizationId, p_email, p_name, p_privilege):
    endpoint = "/organizations/%s/admins" % p_organizationId
    body = { 
        "email": p_email,
        "name": p_name,
        "orgAccess": p_privilege
        }
    success, errors, headers, response = merakiRequest(p_apiKey, "POST", endpoint, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
def deleteOrganizationAdmin(p_apiKey, p_organizationId, p_adminId):
    endpoint = "/organizations/%s/admins/%s" % (p_organizationId, p_adminId)
    success, errors, headers, response = merakiRequest(p_apiKey, "DELETE", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
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
    
    
def adminIdForEmail(p_adminList, p_adminEmail):
    #returns admin id associated with an email or None, if it is not found
    
    if not p_adminList is None:
        for admin in p_adminList:
            if admin['email'] == p_adminEmail:
                return (admin['id'])

    return (None)
    
    
def filterOrgList(p_orgList, p_filter):
    #tries to match a list of orgs to a name filter
    #   /all    all organizations
    #   <name>  match if given text is found in name
        
    returnlist = []
    
    if not p_orgList is None:     
        if p_filter == "/all":
            return (p_orgList)        
       
        for org in p_orgList:
            if org["name"].find(p_filter) != -1:
                returnlist.append(org)
       
    return(returnlist)
    
    
def cmdAdd(p_apikey, p_orgs, p_email, p_name, p_privilege):
    #creates an administrator in all orgs in scope
    
    if p_privilege not in ['full', 'read-only']:
        killScript('Unsupported privilege level "%s"' % p_privilege)
        
    if p_orgs is None:
        return
    
    for org in p_orgs:
        success, errors, headers, orgAdmins = getOrganizationAdmins(p_apikey, org["id"])
        adminId   = adminIdForEmail(orgAdmins, p_email)
        if not adminId is None:
            log('Skipping org "%s". Admin already exists' % org["name"])
        else:
            success, errors, headers, response = createOrganizationAdmin(p_apikey, org["id"], p_email, p_name, p_privilege)
            if success:
                log("Operation successful")
            else:
                log("Operation failed")
                           
    
def cmdDelete(p_apiKey, p_orgs, p_admin):
    #deletes an administrator from all orgs in scope

    if p_orgs is None:
        return

    for org in p_orgs:
        success, errors, headers, orgAdmins = getOrganizationAdmins(p_apiKey, org["id"])
        adminId   = adminIdForEmail(orgAdmins, p_admin)
        if adminId is None:
            log('Skipping org "%s". Admin "%s" not found"' % (org["name"], p_admin))
        else:            
            success, errors, headers, response = deleteOrganizationAdmin(p_apiKey, org["id"], adminId)
            if success:
                log("Operation successful")
            else:
                log("Operation failed")       
    
    
def cmdFind(p_apikey, p_orgList, p_admin):
    #finds organizations that contain an admin with specified email
    
    if p_orgList is None:
        return
        
    buffer = ""
    matches = 0
        
    for org in p_orgList:
        success, errors, headers, orgAdmins = getOrganizationAdmins(p_apikey, org["id"])
        adminId   = adminIdForEmail(orgAdmins, p_admin)
        if not adminId is None:
            matches += 1
            buffer += 'Found admin "%s" in org "%s"\n' % (p_admin, org["name"])
            
    print("\n%d matches\n" % matches)
    print(buffer)
                
    
def cmdList(p_apikey, p_orgList):
    #lists all admins in specified orgs
    
    if p_orgList is None:
        return
        
    buffer = ""
    
    for org in p_orgList:
        success, errors, headers, orgAdmins = getOrganizationAdmins(p_apikey, org["id"])
        
        if not orgAdmins is None:
            buffer += '\nAdministrators for org "%s"\n' % org["name"]
            buffer += '%-30s %-50s %-20s\n' % ("Name", "email", "Org Privilege")
            for admin in orgAdmins:
                buffer += '%-30s %-50s %-20s\n' % (admin['name'], admin['email'], admin['orgAccess'])
                
    print(buffer)
        
    
def main(argv):
    #initialize variables for command line arguments
    arg_apiKey      = ''
    arg_orgName     = ''
    arg_admin       = ''
    arg_command     = ''
    arg_name        = ''
    arg_privilege   = ''
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:c:a:n:p:')
    except getopt.GetoptError:
        killScript()
    
    for opt, arg in opts:
        if   opt == '-h':
            killScript()
        elif opt == '-k':
            arg_apiKey  = arg
        elif opt == '-o':
            arg_orgName = arg
        elif opt == '-c':
            arg_command = arg    
        elif opt == '-a':
            arg_admin   = arg
        elif opt == '-n':
            arg_name    = arg
        elif opt == '-p':
            arg_privilege = arg
            
    #check if all parameters are required parameters have been given
    if arg_apiKey == '' or arg_orgName == '' or arg_command == '':
        killScript()
        
    #fail invalid commands quickly, not to annoy user
    cleanCmd = arg_command.lower().strip()
    if cleanCmd not in ['add', 'delete', 'find', 'list']:
        killScript('Invalid command "%s"' % cleanCmd)
        
    if arg_admin == '' and cleanCmd != 'list':
        killScript('Command "%s" needs parameter -a <admin account>' % arg_command)
        
    if cleanCmd == 'add' and arg_name == '':
        killScript('Command "add" needs parameter -n <name>')
        
    #set default values for optional arguments
    if arg_privilege == '':
        arg_privilege = 'full'                
    
    #build list of organizations to be processed
    
    #get list org all orgs belonging to this admin
    success, errors, headers, rawOrgList = getOrganizations(arg_apiKey)
    if rawOrgList is None:
        killScript('Error retrieving organization list')
    
    #match list of orgs to org filter
    matchedOrgs = filterOrgList(rawOrgList, arg_orgName)
    
    #launch correct command code
    if cleanCmd == 'add':
        cmdAdd(arg_apiKey, matchedOrgs, arg_admin, arg_name, arg_privilege)
    elif cleanCmd == 'delete':
        cmdDelete(arg_apiKey, matchedOrgs, arg_admin)
    elif cleanCmd == 'find':
        cmdFind(arg_apiKey, matchedOrgs, arg_admin)
    elif cleanCmd == 'list':
        cmdList(arg_apiKey, matchedOrgs)
    
if __name__ == '__main__':
    main(sys.argv[1:])