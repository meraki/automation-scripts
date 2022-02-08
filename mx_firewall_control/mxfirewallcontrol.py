readMe = """This is a script to manage firewall rulesets, by backing them up, inserting new rules or replacing the
whole ruleset.

To run the script, enter:
  python mxfirewallcontrol.py -k <key> -o <org> [-f <filter>] [-c <command>] [-m <mode>]

Mandatory arguments:
  -k <key>     : Your Meraki Dashboard API key
  -o <org>     : The name of the Meraki dashboard organization you want to process. Enter "/all" for all

Optional arguments:
  -f <filter>   : Define a subset of networks or templates to be processed. To use multiple filters, 
                  separate them with commas. A network/template needs to satisfy all filters to be processed.
                  Valid options:
                  -f name:<name>                Network/template name must match <name>. Use * for wildcard.
                                                Wildcard character only allowed in beginning or end of string
                  -f tag:<tag>                  Network tags must include <tag>
                  -f type:network               Process only non-template networks
                  -f type:template              Process only configuration templates (default filter)
                  -f type:any                   Process both networks and config templates. Cannot be combined
                                                with tag filters
                  -f type:all                   Same as "-f type:any"
  -c <command>  : Specify the operation to be carried out. When specifying rule numbers, a positive number
                  indicates counting from top to bottom. First rule is "1". A negative number  indicates counting
                  from bottom to top. Last rule is "-1". Valid options:
                  -c print                      Do not make changes, just print the ruleset to screen (default)
                  -c create-backup              Save rulesets in folder mxfirewallctl_backup_<timestamp> as
                                                filenames "<org name>__<net name>.txt"
                  -c restore-backup:<folder>    Rulesets will be replaced by the ones contained in folder <folder>
                                                The script will look for files with naming format:
                                                "<org name>__<net name>.txt"
                  -c load-folder:<folder>       Same as "-c restore-backup:<folder>"
                  -c "append:<rules>"           Add <rules> to the end of ruleset
                  -c append-file:<filename>     Ruleset in <filename> will be appended to existing rulesets
                  -c "insert:<num>:<rules>"     Insert <rules> as rules starting with line number <num>
                  -c insert-file:<num>:<file>   Insert contents of <file> as rules starting with line number <num>
                  -c "replace:<rules>"          Rulesets will be replaced by the ones specified in <rules>
                  -c replace-file:<filename>    Rulesets will be replaced by the one contained in <filename>
                  -c remove:<num>               Remove rule line number <num>
                  -c remove-marked:<label>      Remove all lines with comments that include <label>
                  -c remove-all                 Delete the whole ruleset
                  -c default-allow              Remove default deny rule from the end, if such is found
                  -c default-deny               Add a default deny rule to the end of the ruleset
  -m <mode>     : Define operating mode for commands that modify firewall rulesets. Valid options:
                  -m simulation                 Print changes for review, do not apply to cloud (default)
                  -m commit                     Create backup and apply changes to cloud
                  -m commit-no-backup           Apply changes to cloud without creating a backup

The full manual for this script can be found here:
https://github.com/meraki/automation-scripts/blob/master/mxfirewallcontrol_manual.pdf"""


#MODIFY THESE FLAGS TO CHANGE DEFAULT SCRIPT OPERATING PARAMETERS
DEFAULT_FLAG_PROCESS_NETWORKS   = False     # If no filter for network/template scope is set, process only templates
DEFAULT_FLAG_PROCESS_TEMPLATES  = True      # If no filter for network/template scope is set, process only templates

MX_RULE_DEFAULT_ALLOW_ALL       = {
                                    "protocol"      : "Any",
                                    "srcPort"       : "Any",
                                    "srcCidr"       : "Any",
                                    "destPort"      : "Any",
                                    "destCidr"      : "Any",
                                    "policy"        : "allow",
                                    "syslogEnabled" : False,
                                    "comment"       : "Default rule"
                                }


import sys, getopt, requests, json, time, datetime, os, re

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
    
# getOrganizationConfigTemplates
#
# Description: List the configuration templates for this organization
# Endpoint: GET /organizations/{organizationId}/configTemplates
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-organization-config-templates

def getOrganizationConfigTemplates(apiKey, organizationId):
    url = "/organizations/" + str(organizationId) + "/configTemplates"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    
# getNetworkApplianceFirewallL3FirewallRules
#
# Description: Return the L3 firewall rules for an MX network
# Endpoint: GET /networks/{networkId}/appliance/firewall/l3FirewallRules
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!get-network-appliance-firewall-l3-firewall-rules

def getNetworkApplianceFirewallL3FirewallRules(apiKey, networkId):
    url = "/networks/" + str(networkId) + "/appliance/firewall/l3FirewallRules"
    success, errors, headers, response = merakiRequest(apiKey, "get", url, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response

# updateNetworkApplianceFirewallL3FirewallRules
#
# Description: Update the L3 firewall rules of an MX network
# Endpoint: PUT /networks/{networkId}/appliance/firewall/l3FirewallRules
#
# Endpoint documentation: https://developer.cisco.com/meraki/api-v1/#!update-network-appliance-firewall-l3-firewall-rules
#
# Request body schema:
#     rules: Array. An ordered array of the firewall rules (not including the default rule)
#     syslogDefaultRule: Boolean. Log the special default rule (boolean value - enable only if you've configured a syslog server) (optional)

def updateNetworkApplianceFirewallL3FirewallRules(apiKey, networkId, body=None):
    url = "/networks/" + str(networkId) + "/appliance/firewall/l3FirewallRules"
    success, errors, headers, response = merakiRequest(apiKey, "put", url, p_requestBody=body, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, response
    

class c_organizationdata:
    def __init__(self):
        self.name       = ''
        self.id         = ''
        self.shardhost  = ''
        self.nwdata     = [] #List of dictionaries as returned by cloud. Primary key is 'id'
#end class  

class c_filter:
    def __init__(self):
        self.type       = ''
        self.value      = ''
#end class



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
    
def printhelp():
    print(readMe)   
    
def printSimulationBanner():
    log('SIMULATION MODE. CHANGES WILL NOT BE SAVED. USE "-m commit" TO OVERRIDE')  

def getApiKey(argument):
    if not argument is None:
        return str(argument)
    return os.environ.get(API_KEY_ENV_VAR_NAME, None)  
 
 
def filterNetworks (apiKey, organization, filters):
    #returns list of networks and/or templates within the scope of "filters"
    
    #NOTE:  THE DEFAULT FILTER SCOPE OF THIS SCRIPT SELECTS CONFIG TEMPLATES BUT NOT NETWORKS
    #       IF NO TYPE FILTER IS APPLIED AT EXECUTION TIME. MODIFY CONSTANTS AT START OF
    #       SCRIPT TO CHANGE THIS
     
    flag_getnetworks    = DEFAULT_FLAG_PROCESS_NETWORKS
    flag_gettemplates   = DEFAULT_FLAG_PROCESS_TEMPLATES
    
    #list of filters by type
    filter_namebegins   = []
    filter_namecontains = []
    filter_nameends     = []
    filter_nameequals   = []
    filter_tag          = []
    
    for item in filters: 
        if   item.type == 'type':
            if  item.value == 'network':
                    flag_getnetworks  = True
                    flag_gettemplates = False
            elif item.value == 'network':
                    flag_getnetworks  = False
                    flag_gettemplates = True
            elif item.value in ['any', 'all']:
                    flag_getnetworks  = True
                    flag_gettemplates = True
        elif item.type == 'name_begins':
            filter_namebegins.append(item.value)
        elif item.type == 'name_contains':
            filter_namecontains.append(item.value)
        elif item.type == 'name_ends':
            filter_nameends.append(item.value)
        elif item.type == 'name_equals':
            filter_nameequals.append(item.value)
        elif item.type == 'tag':
            filter_tag.append(item.value)
    
    
    networksForNameFilterProcessing = []
    
    if flag_getnetworks:
        success, errors, rawNetworks = getOrganizationNetworks(apiKey, organization['id'])
        if rawNetworks is None:
            log('WARNING: Unable to fetch networks for organization %s "%s"' % (organization['id'], organization['name']))
        else:
            for net in rawNetworks:
                if 'appliance' in net['productTypes']:
                    flag_networkInScope = False
                    if len(filter_tag) == 0:
                        flag_networkInScope = True
                    for tag in filter_tag:
                        if tag in net['tags']:
                            flag_networkInScope = True
                            break
                    if flag_networkInScope:
                        networksForNameFilterProcessing.append(net)
            
    #add templates to buffer if flags indicate so      
    if flag_gettemplates:  
        success, errors, rawTemplates = getOrganizationConfigTemplates(apiKey, organization['id'])  
        if rawTemplates is None:
            log('WARNING: Unable to fetch templates for organization %s "%s"' % (organization['id'], organization['name']))
        else:
            networksForNameFilterProcessing += rawTemplates
    
    fullyFilteredNetworksAndTemplates = []
    
    #process name filters
    for net in networksForNameFilterProcessing:
        if 'appliance' in net['productTypes']:
            flag_networkIsCompliant = True
            #loop through filter lists and flag as incompliant as needed
            for fnb in filter_namebegins:
                if not net['name'].startswith(fnb):
                    flag_networkIsCompliant = False
            for fnc in filter_namecontains:
                if net['name'].find(fnc) == -1:
                    flag_networkIsCompliant = False
            for fnd in filter_nameends:
                if not net['name'].endswith(fnd):
                    flag_networkIsCompliant = False
            for fnq in filter_nameequals:
                if not net['name'] == fnq:
                    flag_networkIsCompliant = False
            if flag_networkIsCompliant:
                fullyFilteredNetworksAndTemplates.append(net)
    
    return(fullyFilteredNetworksAndTemplates)
    
    
def parsefilter(p_string):
    #parses filter command line argument
    processed        = []
    flag_gotname     = False
    flag_gottype     = False
    flag_gottag      = False
    flag_gotall      = False
    flag_gotnetwork  = False
    flag_gottemplate = False
    flag_defaulttype = True
    
    if len(p_string) == 0:
        return('')
    
    inputfilters = p_string.split(',') 
    
    for item in inputfilters:
        splititem = item.split(':')
        if len(splititem) == 2 and not flag_gotall:
            ftype  = splititem[0].strip()
            fvalue = splititem[1].strip()
            
            #process wildcards
            if ftype == 'name':
                if len(fvalue) > 0:
                    if fvalue.endswith('*'):
                        if fvalue.startswith('*'):
                            #search for extra *
                            ftype  = 'name_contains'
                            fvalue = fvalue[1:-1]
                        else: 
                            ftype = 'name_begins'
                            fvalue = fvalue[:-1]
                    elif fvalue.startswith('*'):
                        ftype = 'name_ends'
                        fvalue = fvalue[1:]
                    else: 
                        ftype = 'name_equals'
                else: #len(fvalue) <= 0
                    log('ERROR 10: Invalid filter "%s"' % item)
                    sys.exit(2)
            elif ftype == 'tag':
                if len(fvalue) == 0:
                    log('ERROR 11: Invalid filter "%s"' % item)
                    sys.exit(2)
                elif flag_gottemplate:    
                    log('ERROR 12: Filter "%s" cannot be combined with type:template or type:any' % item)
                    sys.exit(2)
                flag_gottag = True
            elif ftype == 'type':
                if flag_gottype:
                    log('ERROR 13: Filter "type" can only be used once: "%s"' % p_string)
                    sys.exit(2)
                if fvalue   == 'network':
                    flag_gotnetwork  = True
                    flag_defaulttype = False
                elif fvalue == 'template':
                    if flag_gottag:
                        log('ERROR 14: Filter "tag" cannot be used with filter "type:template"')
                        sys.exit(2)
                    flag_gottemplate = True
                elif fvalue in ['any', 'all']:
                    if flag_gottag:
                        killScript('Filter "tag" cannot be used with filter "type:any/all"')
                    flag_gottemplate = True
                    flag_gotnetwork  = True
                else:
                    log('ERROR 16: Invalid filter "%s"' % item)
                    sys.exit(2)
                flag_gottype = True
            else:
                log('ERROR 17: Invalid filter "%s"' % item)
                sys.exit(2)
            #check for invalid wildcards regardless of filter type
            if '*' in fvalue:
                log('ERROR 18: Invalid use of wildcard in filter "%s"' % item)
                sys.exit(2)
            
            processed.append(c_filter())
            processed[len(processed)-1].type  = ftype
            processed[len(processed)-1].value = fvalue
        else:
            log('ERROR 19: Invalid filter string "%s"' % p_string)
            sys.exit(2)
            
    #check for filter incompatibilities with default type-filter, if it has not been changed
    if flag_defaulttype and flag_gottag:
        killScript('Default type filter is "template". Filter "tag" needs filter "type:network"')

    return (processed)
     
    
def printRuleset(organizationName, networkName, rules):
    # Prints a single ruleset to stdout
    
    print('\nMX Firewall Ruleset for Organization "%s", Network "%s"\n' % (organizationName, networkName))
    
    formatStr = '%-5s %-4s %-6s %-28s %-6s %-28s %-6s %-5s %s'
    
    print(formatStr % (
        'Line#', 
        'prot', 
        'sPort', 
        'source CIDR',
        'dPort', 
        'destination CIDR', 
        'policy', 
        'sysLg', 
        'Comment') )
    
    i = 1
    for line in rules:
        print(formatStr % (
            i,
            line['protocol'],
            line['srcPort'],
            line['srcCidr'],
            line['destPort'],
            line['destCidr'],
            line['policy'],
            line['syslogEnabled'],
            line['comment']) )
        i += 1
        
    print('')
           
   
def cmdprint(apiKey, p_orglist):
    #Prints all rulesets in scope to stdout

    printBuffer = []
    
    for org in p_orglist:
        for net in org['networks']:
            success, errors, response = getNetworkApplianceFirewallL3FirewallRules(apiKey, net['id'])
            if not response is None:
                printBuffer.append( {'organizationName': org['name'], 'networkName': net['name'], 'rules': response['rules']} )
            else:
                log('WARNING: Unable to read MX ruleset for "%s" > "%s"' % (org['name'], net['name']))
                
    for line in printBuffer:
        printRuleset(line['organizationName'], line['networkName'], line['rules'])
      
      
def formatfilename(p_orgname, p_netname):
    #make sure characters not suitable for filenames do not end up in string
    
    pattern = re.compile('([^\-_ \w])+')
    orgn    = pattern.sub('', p_orgname)
    orgn    = orgn.strip()
    netn    = pattern.sub('', p_netname)
    netn    = netn.strip()
    
    result  = orgn + '__' + netn + '.txt'

    return (result)
      
      
def cmdcreatebackup(apiKey, organizations):
    #code for the create-backup command
    
    #create directory to place backups
    flag_creationfailed = True
    MAX_FOLDER_CREATE_TRIES = 5
    for i in range (0, MAX_FOLDER_CREATE_TRIES):
        time.sleep(2)
        timestamp = '{:%Y-%m-%d_%H.%M.%S}'.format(datetime.datetime.now())
        directory = 'mxfwctl_backup_' + timestamp
        flag_noerrors = True
        try:
            os.makedirs(directory)
        except:
            flag_noerrors = False
        if flag_noerrors:
            flag_creationfailed = False
            break
    if flag_creationfailed:
        killScript('Unable to create directory for backups')
    else:
        log('Backup directory is "%s"' % directory)
                
    #create backups - one file per network
    for org in organizations:    
        for net in org['networks']:
            success, errors, response = getNetworkApplianceFirewallL3FirewallRules(apiKey, net['id'])
            if response is None:
                log('WARNING: Unable to read MX ruleset for "%s" > "%s"' % (org['name'], net['name']))
            else:
                filename = formatfilename(org['name'], net['name'])
                filepath = directory + '/' + filename
                if os.path.exists(filepath):
                    log('WARNING: Cannot create backup file: name conflict "%s"' % filename)
                    continue
                try:
                    f = open(filepath, 'w')
                except:
                    log('WARNING: Unable to open file path for writing: "%s"' % filepath)
                    continue
                 
                for line in response['rules']:
                    #f.write(json.dumps(line))
                    f.write('{"protocol":"%s", "srcPort":"%s", "srcCidr":"%s", "destPort":"%s", "destCidr":"%s", "policy":"%s", "syslogEnabled":%s, "comment":"%s"}\n' % (
                        line['protocol'],line['srcPort'],line['srcCidr'],line['destPort'],line['destCidr'],line['policy'],str(line['syslogEnabled']).lower(),line['comment']))
              
                try:
                    f.close()
                except:
                    log('WARNING: Unable to close file path: "%s"' % filepath)
                    continue
                    
                log('INFO: Created backup for "%s". File: "%s"' % (net['name'], filename))
    
    
def stripDefaultRule(ruleSet):
    #strips the default allow ending rule from an MX L3 Firewall ruleset
    
    if len(ruleSet) > 0:
        lastLine = ruleSet[len(ruleSet)-1]
        rulesMatch = True
        for key in lastLine:
            if not key in MX_RULE_DEFAULT_ALLOW_ALL:
                return None
            observedValue = lastLine[key]
            if observedValue is str:
                observedValue = observedValue.lower()
            defaultValue = MX_RULE_DEFAULT_ALLOW_ALL[key]
            if defaultValue is str:
                defaultValue = defaultValue.lower()
            if observedValue != defaultValue:
                rulesMatch = False
                break
            
        if rulesMatch:
            return ruleSet[:-1]
            
        return ruleSet
    return []
   
   
def loadruleset(p_filepath):
    #Load a ruleset from file to memory. Drop default allow rules
    ruleset = []
    jdump = '['
    
    try:
        f = open(p_filepath, 'r')
    except:
        log('ERROR 25: Unable to open file path for reading: "%s"' % p_filepath)
        return None
    
    for line in f:
        try:
            buffer = line
        except: 
            log('ERROR 26: Unable to read from file: "%s"' % p_filepath)
            return None
            
        if len(buffer.strip())>1:  
            if not jdump.endswith('['):
                jdump += ','
            jdump += buffer[:-1]
            
    try:
        f.close()
    except:
        log('ERROR 27: Unable to close input file "%s"' % p_filepath)
        return None
        
    jdump += ']'  
    
    try:
        ruleset = json.loads(jdump)
    except:
        log('ERROR 28: Invalid input file format "%s"' % p_filepath)
        return None
            
    return(ruleset)
    
       
def cmdaddrules2(p_apikey, p_orglist, p_source, p_data, p_mode, p_flagcommit=False, p_flagbackup=True, p_start=0):
    #new code for commands "-c append-file:<file>" and "-c replace-file:<file>", etc
    
    #flags for p_mode
    flag_append  = False
    flag_insert  = False
    flag_replace = False
    
    #flags for p_source
    flag_srcfile = False
    flag_srcstr  = False
    flag_srcdir  = False
    
    #set flags
    if   p_mode == 'append':
        flag_append  = True
    elif p_mode == 'insert':
        flag_insert  = True
        if p_start == 0:
            killScript('ERROR 51: Invalid start position "0" for insert command. First rule is #1')
    elif p_mode == 'replace':
        flag_replace = True
    else:
        killScript('DEBUG: Invalid mode for cmdaddrules2(). Please check your script')
        
    if   p_source == 'file':
        flag_srcfile = True
    elif p_source == 'string':
        flag_srcstr  = True
    elif p_source == 'folder':
        flag_srcdir  = True
    else:
        killScript('DEBUG: Invalid source for cmdaddrules2(). Please check your script')
    
    #create backups before making changes, unless overriden by flag
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printSimulationBanner()

    #load ruleset to be added from file or command line
    diffset = []    
    if flag_srcfile:
        diffset = loadruleset(p_data)
        if diffset is None:
            killScript('Unable to load source ruleset')
    elif flag_srcstr:
        try:
            strload = json.loads(p_data)
        except:
            killScript('ERROR 50: Ruleset to be added must be given in JSON format')
        #if loaded from CLI, ruleset might be either dict or table
        if isinstance(strload, dict):
            diffset.append(strload)
        else:
            diffset = strload

    for org in p_orglist:
        for net in org['networks']:
            oldset = []
            
            if flag_srcdir:
                diffset = loadruleset(net['source'])                
                if diffset is None:
                    continue
                diffset = stripDefaultRule(diffset)
            
            #if insert or append mode, add the first part of the existing ruleset before the new one
            if flag_append or flag_insert:
                success, errors, netRules = getNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'])
                if netRules is None:
                    log('WARNING: Unable to read ruleset for "%s"' % net['name'])
                    continue
                
                buffer      = stripDefaultRule(netRules['rules'])
                
                #adjust starting position to allow positive/negative counting (from start or end)
                bufferlen   = len(buffer)
                adjustedpos = bufferlen
                if flag_insert:
                    if p_start > 0:
                        if p_start < bufferlen:
                            adjustedpos = p_start-1
                        else:
                            log('WARNING: Index out of range for "%s"' % net['name'])
                    else:
                        if p_start*-1 < bufferlen:
                            adjustedpos = bufferlen + p_start + 1
                        else:
                            adjustedpos = 0
                            log('WARNING: Index out of range for "%s"' % net['name'])
                        
                if flag_insert:
                    oldset = buffer[:adjustedpos]
                else:
                    oldset = buffer
                
            #add the new ruleset to be applied
            newset = oldset + diffset
                        
            #if insert mode, add the rest of the existing ruleset
            if flag_insert:
                newset += buffer[adjustedpos:]
                
            # if last rule of merged ruleset is "allow any", remove it
            newset = stripDefaultRule(newset)
                          
            if p_flagcommit:
                log('Writing ruleset for "%s"' % net['name'])
                success, errors, response = updateNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'], body={'rules': newset})
                if not success:
                    log('WARNING: Unable to write ruleset for "%s"' % net['name'])
            else: #print ruleset for review
                printBuffer = newset + [MX_RULE_DEFAULT_ALLOW_ALL]
                printRuleset(org['name'], net['name'], printBuffer)   
    
    
def cmdremove(p_apikey, p_orglist, p_mode, p_data, p_flagcommit=False, p_flagbackup=True):
    #code for command "-c remove:<num>" and "-c remove-marked:<label>"
        
    flag_modenumber = True
    flag_modelabel  = False
    
    if   p_mode == 'number':
        flag_modenumber  = True
        flag_modelabel   = False
    elif p_mode == 'label':
        flag_modenumber  = False
        flag_modelabel   = True
    else:
        log('DEBUG: Invalid mode for cmdremove(). Please check your script')
        sys.exit(2)
    
    linenum = 0
    if flag_modenumber:
        try:
            linenum = int(p_data)
        except:
            killScript('Integer expected in command "remove:<num>"')
    else:
        if len(p_data) < 1:
            killScript('ERROR 48: Label must be at least 1 character long in command "remove-marked:<label>"')
    
    if (flag_modenumber and linenum != 0) or flag_modelabel:
        #create backups before making changes, unless overriden by flag
        if p_flagbackup and p_flagcommit:
            cmdcreatebackup(p_apikey, p_orglist)
        elif not p_flagcommit:
            printSimulationBanner()
     
        for org in p_orglist:
            for net in org['networks']:
                success, errors, oldRules = getNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'])
                if oldRules is None:
                    log('WARNING: Unable to read ruleset for "%s"' % net['name'])
                    continue                    
            
                newset = []
                buffer = stripDefaultRule(oldRules['rules'])
                bufferlen = len(buffer)
                adjustednum = linenum
                flag_madechanges = False
                
                if flag_modenumber:
                    #do adjustment of line number to enable counting backwards
                    if linenum < 0:
                        if linenum*-1 <=  bufferlen:
                            adjustednum = bufferlen + linenum + 1
                    if adjustednum < 1 or adjustednum > bufferlen:
                        log('WARNING: Index out of range for "%s"' % net['name'])
                        
                for i in range (0, bufferlen):
                    if flag_modenumber:
                        if i+1 != adjustednum:
                            newset.append(buffer[i])
                        else:    
                            flag_madechanges = True
                    else: #mode label
                        if buffer[i]['comment'].find(p_data) == -1:
                            newset.append(buffer[i])
                        else:
                            flag_madechanges = True
                if p_flagcommit:
                    if flag_madechanges: #if original ruleset was empty, there is nothing to remove
                        log('INFO: Writing ruleset for "%s"' % net['name'])
                        success, errors, response = updateNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'], body={'rules': newset})
                        if not success:
                            log('WARNING: Unable to write ruleset for "%s"' % net['name'])
                    else:    
                        log('INFO: No changes for ruleset in "%s"' % net['name'])
                else: #print ruleset for review
                    printBuffer = newset + [MX_RULE_DEFAULT_ALLOW_ALL]
                    printRuleset(org['name'], net['name'], printBuffer)
                        
    else:
        killScript('First rule number is "1". Last rule number is "-1"')
    
RULE_DEFAULT_DENY = {
    "protocol":"any",
    "srcPort":"Any",
    "srcCidr":"Any",
    "destPort":"Any",
    "destCidr":"Any",
    "policy":"deny",
    "syslogEnabled":False,
    "comment":"Default deny"
}
    
def cmddefaultdeny(p_apikey, p_orglist, p_flagcommit, p_flagbackup):
    #add a default deny rule to the end of the ruleset, if there is not already one
    
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printSimulationBanner()
    
    for org in p_orglist:
        for net in org['networks']:   
            success, errors, response = getNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'])
            if response is None:
                log('WARNING: Unable to read ruleset for "%s"' % net['name'])
                continue    
            ruleset = stripDefaultRule(response['rules'])
            oldsetlen = len(ruleset)
            if oldsetlen > 0:
                #compare all fields except syslog and comment
                lastline = ruleset[oldsetlen-1]
                rulesMatch = True
                for field in lastline:
                    if (field not in ['syslogEnabled', 'comment']) and (field in RULE_DEFAULT_DENY):
                        if lastline[field] != RULE_DEFAULT_DENY[field]:
                            rulesMatch = False
                            break
                if not rulesMatch:
                    ruleset.append(RULE_DEFAULT_DENY)
                    if p_flagcommit:
                        log('INFO: Writing ruleset for "%s"' % net['name'])
                        success, errors, response = updateNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'], body={'rules': ruleset})
                        if not success:
                            log('WARNING: Unable to write ruleset for "%s"' % net['name'])
                else:
                    log('INFO: No changes in ruleset for "%s"' % net['name'])
                    
                if not p_flagcommit:
                    printRuleset(org['name'], net['name'], ruleset + [MX_RULE_DEFAULT_ALLOW_ALL])
    
    
def cmddefaultallow(p_apikey, p_orglist, p_flagcommit, p_flagbackup):
    #remove default deny rule from the end of the ruleset, if there is one
    
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printSimulationBanner()
    
    for org in p_orglist:
        for net in org['networks']:    
            success, errors, response = getNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'])
            if response is None:
                log('WARNING: Unable to read ruleset for "%s"' % net['name'])
                continue     
            oldset = stripDefaultRule(response['rules'])
            oldsetlen = len(oldset)
            if oldsetlen > 0:
                #compare all fields except syslog and comment
                lastline = oldset[oldsetlen-1]
                rulesMatch = True
                for field in lastline:
                    if (field not in ['syslogEnabled', 'comment']) and (field in RULE_DEFAULT_DENY):
                        if lastline[field] != RULE_DEFAULT_DENY[field]:
                            rulesMatch = False
                            break
                if rulesMatch:
                    if p_flagcommit:
                        log('INFO: Writing ruleset for "%s"' % net['name'])
                        success, errors, response = updateNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'], body={'rules': oldset[:-1]})
                        if not success:
                            log('WARNING: Unable to write ruleset for "%s"' % net['name'])
                else:
                    log('INFO: No changes in ruleset for "%s"' % net['name'])
                
                if not p_flagcommit:
                    printRuleset(org['name'], net['name'], oldset[:-1] + [MX_RULE_DEFAULT_ALLOW_ALL])
    
    
def cmdremoveall(p_apikey, p_orglist, p_flagcommit, p_flagbackup):
    #remove all rules in ruleset
    
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printSimulationBanner()
    
    for org in p_orglist:
        for net in org['networks']:    
            if p_flagcommit:
                log('Erasing ruleset for "%s"...' % net['name'])
                success, errors, response = updateNetworkApplianceFirewallL3FirewallRules(p_apikey, net['id'], body={'rules': []})
                if not success:
                    log('WARNING: Unable to write ruleset for "%s"' % net['name'])
            else:
                log('INFO: Commit mode will erase MX ruleset for "%s"' % net['name'])
    
    
def cmdloadfolder(p_apikey, p_orglist, p_folder, p_flagcommit, p_flagbackup):
    #code for command "restore-backup <folder>"
        
    for org in p_orglist:
        for net in org['networks']:     
            filename = formatfilename(org['name'], net['name'])
            path = p_folder + '/' + filename
            
            net['source'] = path
            
            log('Source file for "%s > %s" is "%s"' % (org['name'], net['name'], net['source']))
                        
    cmdaddrules2(p_apikey, p_orglist, 'folder', None, 'replace', p_flagcommit, p_flagbackup)      
    
    
def parsecommand(p_apikey, p_orglist, p_commandstr, p_flagcommit, p_flagbackup):
    #parses command line argument "-c <command>"
          
    splitstr = p_commandstr.split(':')
    
    if len(splitstr) > 0:
        
        cmd = splitstr[0].strip()
        
        if   cmd == '':
            #default command: print
            cmdprint(p_apikey, p_orglist)
            
        elif cmd == 'print':
            cmdprint(p_apikey, p_orglist)
            
        elif cmd == 'create-backup':
            cmdcreatebackup(p_apikey, p_orglist)
            
        elif cmd == 'append-file':
            if len(splitstr) > 1:
                parameter = splitstr[1].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'file', parameter, 'append', p_flagcommit, p_flagbackup)
                else:
                    log('ERROR 30: Missing definition <file> in command append-file:<file>')
                    sys.exit(2)
            else:
                log('ERROR 31: Missing definition <file> in command append-file:<file>')
                sys.exit(2)
                
        elif cmd == 'insert-file':
            flag_processingsuccess = True
            if len(splitstr) > 2:
                try:
                    parameter1 = int(splitstr[1].strip())
                except:
                    flag_processingsuccess = False
                parameter2 = splitstr[2].strip()
                
                if len(parameter2) > 0 and flag_processingsuccess:
                    cmdaddrules2(p_apikey, p_orglist, 'file', parameter2, 'insert', p_flagcommit, p_flagbackup,parameter1)
                else:
                    flag_processingsuccess = False
            else:
                flag_processingsuccess = False
            if not flag_processingsuccess:
                log('ERROR 32: Error in command "insert-file:<num>:<file>"')
                sys.exit(2)
                
        elif cmd == 'replace-file':
            if len(splitstr) > 1:
                parameter = splitstr[1].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'file', parameter, 'replace', p_flagcommit, p_flagbackup)
                else:
                    log('ERROR 33: Missing definition <file> in command replace-file:<file>')
                    sys.exit(2)
            else:
                log('ERROR 34: Missing definition <file> in command replace-file:<file>')
                sys.exit(2)
                
        elif cmd in ['restore-backup', 'load-folder']:
            if len(splitstr) > 1:
                parameter = splitstr[1].strip()
                if len(parameter) > 0:
                    cmdloadfolder(p_apikey, p_orglist, parameter, p_flagcommit, p_flagbackup)
                else:
                    log('ERROR 35: Missing definition <folder> in command restore-backup:<folder>')
                    sys.exit(2)
            else:
                log('ERROR 36: Missing definition <folder> in command restore-backup:<folder>')
                sys.exit(2)
            
        elif cmd == 'append':        
            if len(splitstr) > 1:
                parameter = p_commandstr[p_commandstr.find(':')+1:].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'string', parameter, 'append', p_flagcommit, p_flagbackup)
                else:
                    log('ERROR 37: Missing definition <string> in command append:<string>')
                    sys.exit(2)
            else:
                log('ERROR 38: Missing definition <string> in command append:<string>')
                sys.exit(2)
            
        elif cmd == 'insert':
            flag_processingsuccess = True
            if len(splitstr) > 2:
                pos1 = p_commandstr.find(':')+1
                pos2 = pos1 + p_commandstr[pos1:].find(':')+1
                try:
                    parameter1 = int(p_commandstr[pos1:pos2-1].strip())
                except:
                    flag_processingsuccess = False
                parameter2 = p_commandstr[pos2:].strip()
                
                if len(parameter2) > 0 and flag_processingsuccess:
                    cmdaddrules2(p_apikey, p_orglist, 'string', parameter2, 'insert', p_flagcommit, p_flagbackup,parameter1)
                else:
                    flag_processingsuccess = False
            else:
                flag_processingsuccess = False
            if not flag_processingsuccess:
                log('ERROR 39: Error in command "insert:<num>:<string>"')
                sys.exit(2)
                
        elif cmd == 'replace':
            if len(splitstr) > 1:
                parameter = p_commandstr[p_commandstr.find(':')+1:].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'string', parameter, 'replace', p_flagcommit, p_flagbackup)
                else:
                    log('ERROR 40: Missing definition <file> in command replace-file:<file>')
                    sys.exit(2)
            else:
                log('ERROR 41: Missing definition <file> in command replace-file:<file>')
                sys.exit(2)
            
        elif cmd == 'remove':
            if len(splitstr) > 1:
                cmdremove(p_apikey, p_orglist, 'number', splitstr[1].strip(), p_flagcommit, p_flagbackup)
            else:
                log('ERROR 42: Missing line number in "remove:<num>"')
                sys.exit(2)
                
        elif cmd == 'remove-all':
            cmdremoveall(p_apikey, p_orglist, p_flagcommit, p_flagbackup)
            
        elif cmd == 'remove-marked':
            if len(splitstr) > 1:
                cmdremove(p_apikey, p_orglist, 'label', splitstr[1].strip(), p_flagcommit, p_flagbackup)
            else:
                log('ERROR 43: Missing label in "remove-marked:<label>"')
                sys.exit(2)             
                
        elif cmd == 'default-allow':
            cmddefaultallow(p_apikey, p_orglist, p_flagcommit, p_flagbackup)
            
        elif cmd == 'default-deny':
            cmddefaultdeny(p_apikey, p_orglist, p_flagcommit, p_flagbackup)
            
        else:
            log('ERROR 44: Invalid command "%s"' % p_commandstr)
            sys.exit(2)
            
    else:
        log('DEBUG: Command string parsing failed')
        sys.exit(2)
    
    return (0)

    
def main(argv):
    #python mxfirewallcontrol -k <key> -o <org> [-f <filter>] [-c <command>] [-m <mode>]

    #set default values for command line arguments
    arg_apikey  = None
    arg_org     = None
    arg_filter  = ''
    arg_command = ''
    arg_mode    = 'simulation'
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:f:c:m:')
    except getopt.GetoptError:
        killScript()
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey  = str(arg)
        elif opt == '-o':
            arg_org     = arg
        elif opt == '-f':
            arg_filter   = arg
        elif opt == '-c':
            arg_command = arg
        elif opt == '-m':
            arg_mode    = arg
                      
    apiKey = getApiKey(arg_apikey)
    if apiKey is None or arg_org is None:
        killScript()
        
    #set flags
    flag_defaultscope       = False
    if arg_filter   == '':
        flag_defaultscope   = True
        
    flag_defaultcommand     = False
    if arg_command == '':
        flag_defaultcommand = True
        
    flag_invalidmode        = True
    flag_modecommit         = False
    flag_modebackup         = True
    if arg_mode    == '':
        flag_invalidmode    = False
    elif arg_mode  == 'simulation':
        flag_invalidmode    = False
    elif arg_mode  == 'commit':
        flag_modecommit     = True
        flag_invalidmode    = False
    elif arg_mode  == 'commit-no-backup':
        flag_modecommit     = True
        flag_modebackup     = False
        flag_invalidmode    = False    
        

    if flag_invalidmode: 
        killScript("Argument -m <mode> is invalid")    
        
    log('Retrieving organization info...')
        
    #compile list of organizations to be processed
    
    success, errors, rawOrganizations = getOrganizations(apiKey)
    if rawOrganizations is None:
        killScript("Unable to fetch organizations' list")
        
    organizations = []
    
    for org in rawOrganizations:
        if arg_org == '/all' or org['name'] == arg_org:
            organizations.append(org)
            
    log('Selecting networks and templates according to filters...')
            
    #parse filter argument
    filters = parsefilter(arg_filter)
    
    for org in organizations:
        filteredNetworks    = filterNetworks (apiKey, org, filters)
        org['networks']     = filteredNetworks

     
    #parse and execute command
    parsecommand(apiKey, organizations, arg_command, flag_modecommit, flag_modebackup)
                   
    log('End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])