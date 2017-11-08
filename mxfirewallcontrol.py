# This is a script to manage firewall rulesets, by backing them up, inserting new rules or replacing the
#  whole ruleset.
#
# To run the script, enter:
#  python mxfirewallcontrol.py -k <key> -o <org> [-f <filter>] [-c <command>] [-m <mode>]
#
# Mandatory arguments:
#  -k <key>     : Your Meraki Dashboard API key
#  -o <org>     : The name of the Meraki dashboard organization you want to process. Enter "/all" for all
#
# Optional arguments:
#  -f <filter>   : Define a subset of networks or templates to be processed. To use multiple filters, 
#                   separate them with commas. A network/template needs to satisfy all filters to be processed.
#                   Valid options:
#                  -f name:<name>               Network/template name must match <name>. Use * for wildcard.
#                                                Wildcard character only allowed in beginning or end of string
#                  -f tag:<tag>                 Network tags must include <tag>
#                  -f type:network              Process only non-template networks
#                  -f type:template             Process only configuration templates (default filter)
#                  -f type:any                  Process both networks and config templates. Cannot be combined
#                                                with tag filters
# -c <command>   : Specify the operation to be carried out. When specifying rule numbers, a positive number
#                                                indicates counting from top to bottom. First rule is "1".
#                                                A negative number  indicates counting from bottom to top. 
#                                                Last rule is "-1". Valid options:
#                  -c print                     Do not make changes, just print the ruleset to screen (default)
#                  -c create-backup             Save rulesets in folder mxfirewallctl_backup_<timestamp> as
#                                                filenames "<org name>__<net name>.txt"
#                  -c "append:<rules>"          Add <rules> to the end of ruleset
#                  -c append-file:<filename>    Ruleset in <filename> will be appended to existing rulesets
#                  -c "insert:<num>:<rules>"    Insert <rules> as rules starting with line number <num>
#                  -c insert-file:<num>:<file>  Insert contents of <file> as rules starting with line number <num>
#                  -c "replace:<rules>"         Rulesets will be replaced by the ones specified in <rules>
#                  -c replace-file:<filename>   Rulesets will be replaced by the one contained in <filename>
#                  -c load-folder:<folder>      Rulesets will be replaced by the ones contained in folder <folder>
#                                                The script will look for files with naming format:
#                                                "<org name>__<net name>.txt"
#                  -c remove:<num>              Remove rule line number <num>
#                  -c remove-marked:<label>     Remove all lines with comments that include <label>
#                  -c remove-all                Delete the whole ruleset
#                  -c default-allow             Remove default deny rule from the end, if such is found
#                  -c default-deny              Add a default deny rule to the end of the ruleset
# -m <mode>     : Define operating mode for commands that modify firewall rulesets. Valid options:
#                  -m simulation                Print changes for review, do not apply to cloud (default)
#                  -m commit                    Create backup and apply changes to cloud
#                  -m commit-no-backup          Apply changes to cloud without creating a backup
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-11-08


import sys, getopt, requests, json, time, datetime, os, re

class c_organizationdata:
    def __init__(self):
        self.name      = ''
        self.id        = ''
        self.shardhost = ''
        self.nwdata    = [] #List of dictionaries as returned by cloud. Primary key is 'id'
#end class  

class c_filter:
    def __init__(self):
        self.type      = ''
        self.value     = ''
#end class

#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

    
def printhelp():
    #prints help text

    printusertext('This is a script to manage firewall rulesets, by backing them up, inserting new rules')
    printusertext('or replacing the whole ruleset.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext('python mxfirewallcontrol.py -k <key> -o <org> [-f <filter>] [-c <command>] [-m <mode>]')
    printusertext('')
    printusertext('Mandatory arguments:')
    printusertext('  -k <key>     : Your Meraki Dashboard API key')
    printusertext('  -o <org>     : The name of the Meraki dashboard organization you want to process. Enter /all for all')
    printusertext('')
    printusertext('Optional arguments:')
    printusertext('  -f <filter>  : Define a subset of networks or templates to be processed. Valid options:')
    printusertext('                  -f name:<name>               Network/template name must match <name>. Use * for wildcard.')
    printusertext('                  -f tag:<tag>                 Network tags must include <tag>. Cannot be used with templates')
    printusertext('                  -f type:network              Process only non-template networks')
    printusertext('                  -f type:template             Process only configuration templates (default filter)')
    printusertext('                  -f type:any                  Process both networks and config templates.')
    printusertext('                                                Cannot be combined with tag filters')
    printusertext(' -c <command>   : Specify the operation to be carried out. When specifying rule numbers, a positive number')
    printusertext('                   indicates counting from top to bottom. First rule is "1". A negative number')
    printusertext('                   indicates counting from bottom to top. Last rule is "-1". Valid options:')
    printusertext('                  -c print                     Do not make changes, just print the ruleset to screen (default)')
    printusertext('                  -c create-backup             Save rulesets in folder mxfirewallctl_backup_<timestamp> as')
    printusertext('                                                filenames "<org name>__<net name>.txt"')
    printusertext('                  -c "append:<rules>"          Add <rules> to the end of ruleset')
    printusertext('                  -c append-file:<filename>    Ruleset in <filename> will be appended to existing rulesets')
    printusertext('                  -c "insert:<num>:<rules>"    Insert <rules> as rules starting with line number <num>')
    printusertext('                  -c insert-file:<num>:<file>  Insert contents of <file> as rules starting with line number <num>')
    printusertext('                  -c "replace:<rules>"         Rulesets will be replaced by the ones specified in <rules>')
    printusertext('                  -c replace-file:<filename>   Rulesets will be replaced by the one contained in <filename>')
    printusertext('                  -c load-folder:<folder>      Rulesets will be replaced by the ones contained in folder <folder>')
    printusertext('                                                The script will look for files with naming format:')
    printusertext('                                                "<org name>__<net name>.txt"')
    printusertext('                  -c remove:<num>              Remove rule line number <num>')
    printusertext('                  -c remove-marked:<label>     Remove all lines with comments that include <label>')
    printusertext('                  -c remove-all                Delete the whole ruleset')
    printusertext('                  -c default-allow             Remove default deny rule from the end, if such is found')
    printusertext('                  -c default-deny              Add a default deny rule to the end of the ruleset')
    printusertext(' -m <mode>     : Define operating mode for commands that modify firewall rulesets. Valid options:')
    printusertext('                  -m simulation                Print changes for review, do not apply to cloud (default)')
    printusertext('                  -m commit                    Create backup and apply changes to cloud')
    printusertext('                  -m commit-no-backup          Apply changes to cloud without creating a backup')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')
    
    
def getorglist(p_apikey):
    #returns the organizations' list for a specified admin
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 01: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'id':'null'})
        return returnvalue
    
    rjson = r.json()
    
    return(rjson)
    
    
def getorgid(p_apikey, p_orgname):
    #looks up org id for a specific org name
    #on failure returns 'null'
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 02: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_orgname:
            return record['id']
    return('null')
    
    
def getshardhost(p_apikey, p_orgid):
    #Looks up shard URL for a specific org. Use this URL instead of 'dashboard.meraki.com'
    # when making API calls with API accounts that can access multiple orgs.
    #On failure returns 'null'
        
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations/%s/snmp' % p_orgid, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
        
    rjson = r.json()
    
    return(rjson['hostname'])
   
    
def gettemplatelist(p_apikey, p_shardhost, p_orgid):
    #returns the complete configuration template list for an org

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/configTemplates' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 04: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'name': 'null', 'id': 'null'})
        return(returnvalue)
    
    return(r.json())
    
    
def getnwlist(p_apikey, p_shardurl, p_orgid):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 05: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'name': 'null', 'id': 'null'})
        return(returnvalue)
    
    return(r.json())
    
 
def readmxfwruleset(p_apikey, p_shardhost, p_nwid):
    #return the MX L3 firewall ruleset for a network

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/networks/%s/l3FirewallRules' % (p_shardhost, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 06: Unable to contact Meraki cloud')
        sys.exit(2)
            
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'srcPort':'null'})
        return returnvalue
    
    rjson = r.json()
    
    return(rjson)
    
    
def writemxfwruleset(p_apikey, p_shardhost, p_nwid, p_ruleset):
    #writes MX L3 ruleset for a device to cloud
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.put('https://%s/api/v0/networks/%s/l3FirewallRules/' % (p_shardhost, p_nwid), data=json.dumps({'rules': p_ruleset}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 07: Unable to contact Meraki cloud')
        sys.exit(2)
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')
 
 
def filternetworks (p_apikey, p_shardhost, p_orgid, p_filters):
    #returns list of networks and/or templates within the scope of "p_filters"
    
    #NOTE: THE DEFAULT FILTER SCOPE OF THIS SCRIPT SELECTS CONFIG TEMPLATES BUT NOT NETWORKS
    #      IF NO TYPE FILTER IS APPLIED AT EXECUTION TIME. MODIFY THE LINES BELOW TO CHANGE THIS
 
    #TODO: Evaluate if handling default filter needs to be rearchitected to a more change-friendly form
    
    flag_getnetworks    = False
    flag_gettemplates   = True
    rawnetlist          = []
    rawtemplist         = []
    filteredlist        = []
    
    #list of filters by type
    count_namefilters   = 0
    filter_namebegins   = []
    filter_namecontains = []
    filter_nameends     = []
    filter_nameequals   = []
    filter_tag          = []
    
    for item in p_filters: 
        if   item.type == 'type':
            if   item.value == 'network':
                flag_getnetworks  = True
                flag_gettemplates = False
            elif item.value == 'any':
                flag_getnetworks  = True
            #NOTE: LEAVE THE LINES BELOW COMMENTED, UNLESS MODIFYING DEFAULT FILTERS
            #    flag_gettemplates = True
            #elif item.value == 'template':
            #    flag_getnetworks  = False
            #    flag_gettemplates = True
        elif item.type == 'name_begins':
            filter_namebegins.append(item.value)
            count_namefilters += 1
        elif item.type == 'name_contains':
            filter_namecontains.append(item.value)
            count_namefilters += 1
        elif item.type == 'name_ends':
            filter_nameends.append(item.value)
            count_namefilters += 1
        elif item.type == 'name_equals':
            filter_nameequals.append(item.value)
            count_namefilters += 1
        elif item.type == 'tag':
            filter_tag.append(item.value)
    
    if flag_getnetworks:
        rawnetlist = getnwlist(p_apikey, p_shardhost, p_orgid)
        if len(rawnetlist) > 0:
            if rawnetlist[0]['id'] == 'null':
                printusertext('ERROR 08: Unable to get network list from Meraki cloud')
                sys.exit(2)
                
    #process tag filters now, since they are incompatible with config templates
    #transfer networks to next level of processing only if they satisfy tag requirements
    buffer1  = []
    tagflags = []
        
    if len(filter_tag) > 0:
        #set all flags to do_transfer
        for net in rawnetlist:
            tagflags.append(True)
            #examine tag incompliance and flag do_not_transfer accordingly
            for filter in filter_tag:
                if type(net['tags']) is str:
                    if net['tags'].find(filter) == -1:
                        tagflags[len(tagflags)-1] = False
                else:
                    tagflags[len(tagflags)-1] = False
                                        
        #copy flagged nets
        for net, flag in zip(rawnetlist, tagflags):
            if flag:
                buffer1.append(net)
               
    else: #no tag filters given, just send everything to next processing stage
        buffer1 += rawnetlist
            
    #add templates to buffer if flags indicate so      
    if flag_gettemplates:        
        rawtemplist = gettemplatelist(p_apikey, p_shardhost, p_orgid)
        if len(rawtemplist) > 0:
            if rawtemplist[0]['id'] == 'null':
                printusertext('ERROR 09: Unable to get template list from Meraki cloud')
                sys.exit(2)
    buffer1 += rawtemplist
    
    #process name filters
    nameflags = []
    buffer2   = []
    if count_namefilters > 0:
        for net in buffer1:
            #flag all as compliant
            nameflags.append(True)
            #loop through filter lists and flag as incompliant as needed
            for fnb in filter_namebegins:
                if not net['name'].startswith(fnb):
                    nameflags[len(nameflags)-1] = False
            for fnc in filter_namecontains:
                if net['name'].find(fnc) == -1:
                    nameflags[len(nameflags)-1] = False
            for fnd in filter_nameends:
                if not net['name'].endswith(fnd):
                    nameflags[len(nameflags)-1] = False
            for fnq in filter_nameequals:
                if not net['name'] == fnq:
                    nameflags[len(nameflags)-1] = False
        for net, flag in zip(buffer1, nameflags):
            if flag:
                buffer2.append(net)
    else:
        buffer2 += buffer1
    
    return(buffer2)

    
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
                    printusertext('ERROR 10: Invalid filter "%s"' % item)
                    sys.exit(2)
            elif ftype == 'tag':
                if len(fvalue) == 0:
                    printusertext('ERROR 11: Invalid filter "%s"' % item)
                    sys.exit(2)
                elif flag_gottemplate:    
                    printusertext('ERROR 12: Filter "%s" cannot be combined with type:template or type:any' % item)
                    sys.exit(2)
                flag_gottag = True
            elif ftype == 'type':
                if flag_gottype:
                    printusertext('ERROR 13: Filter "type" can only be used once: "%s"' % p_string)
                    sys.exit(2)
                if fvalue   == 'network':
                    flag_gotnetwork  = True
                    flag_defaulttype = False
                elif fvalue == 'template':
                    if flag_gottag:
                        printusertext('ERROR 14: Filter "tag" cannot be used with filter "type:template"')
                        sys.exit(2)
                    flag_gottemplate = True
                elif fvalue == 'any':
                    if flag_gottag:
                        printusertext('ERROR 15: Filter "tag" cannot be used with filter "type:any"')
                        sys.exit(2)
                    flag_gottemplate = True
                    flag_gotnetwork  = True
                else:
                    printusertext('ERROR 16: Invalid filter "%s"' % item)
                    sys.exit(2)
                flag_gottype = True
            else:
                printusertext('ERROR 17: Invalid filter "%s"' % item)
                sys.exit(2)
            #check for invalid wildcards regardless of filter type
            if '*' in fvalue:
                printusertext('ERROR 18: Invalid use of wildcard in filter "%s"' % item)
                sys.exit(2)
            
            processed.append(c_filter())
            processed[len(processed)-1].type  = ftype
            processed[len(processed)-1].value = fvalue
        else:
            printusertext('ERROR 19: Invalid filter string "%s"' % p_string)
            sys.exit(2)
            
    #check for filter incompatibilities with default type-filter, if it has not been changed
    if flag_defaulttype and flag_gottag:
        printusertext('ERROR 20: Default type filter is "template". Filter "tag" needs filter "type:network"')
        sys.exit(2)

    return (processed)
     
    
def printruleset(p_orgname, p_netname, p_ruleset):
    #Prints a single ruleset to stdout
    
    print('')
    print('MX Firewall Ruleset for Organization "%s", Network "%s"' % (p_orgname, p_netname))
    i = 1
    for line in p_ruleset:
        print('LINE:%d protocol:%s, srcPort:%s, srcCidr:%s, destPort:%s, destCidr:%s, policy:%s, syslogEnabled:%s, comment:%s' % (i,line['protocol'],line['srcPort'],line['srcCidr'],line['destPort'],line['destCidr'],line['policy'],line['syslogEnabled'],line['comment']))
        i += 1
        
    return(0)
   
   
def cmdprint(p_apikey, p_orglist):
    #Prints all rulesets in scope to stdout

    buffer = []
    
    for org in p_orglist:
        for net in org.nwdata:
            buffer = readmxfwruleset(p_apikey, org.shardhost, net['id'])
            if buffer[0]['srcPort'] != 'null':
                printruleset(org.name, net['name'], buffer)
            else:
                printusertext('WARNING: Unable to read MX ruleset for "%s" > "%s"' % (org.name,net['name']))

    return(0)
      
      
def formatfilename(p_orgname, p_netname):
    #make sure characters not suitable for filenames do not end up in string
    
    pattern = re.compile('([^\-_ \w])+')
    orgn    = pattern.sub('', p_orgname)
    orgn    = orgn.strip()
    netn    = pattern.sub('', p_netname)
    netn    = netn.strip()
    
    result  = orgn + '__' + netn + '.txt'

    return (result)
      
      
def cmdcreatebackup(p_apikey, p_orglist):
    #code for the create-backup command
    
    #create directory to place backups
    flag_creationfailed = True
    MAX_FOLDER_CREATE_TRIES = 5
    for i in range (0, MAX_FOLDER_CREATE_TRIES):
        time.sleep(2)
        timestamp = '{:%Y%m%d_%H%M%S}'.format(datetime.datetime.now())
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
        printusertext('ERROR 21: Unable to create directory for backups')
        sys.exit(2)
    else:
        printusertext('INFO: Backup directory is "%s"' % directory)
        
    buffer = []    
        
    #create backups - one file per network
    for org in p_orglist:    
        for net in org.nwdata:
            buffer = readmxfwruleset(p_apikey, org.shardhost, net['id'])
            if buffer[0]['srcPort'] != 'null':
                                
                filename = formatfilename(org.name, net['name'])
                filepath = directory + '/' + filename
                if os.path.exists(filepath):
                    printusertext('ERROR 22: Cannot create backup file: name conflict "%s"' % filename)
                    sys.exit(2)
                else:
                    buffer = readmxfwruleset(p_apikey, org.shardhost, net['id'])
                    try:
                        f = open(filepath, 'w')
                    except:
                        printusertext('ERROR 23: Unable to open file path for writing: "%s"' % filepath)
                        sys.exit(2)
                     
                    for line in buffer:
                        f.write('{"protocol":"%s", "srcPort":"%s", "srcCidr":"%s", "destPort":"%s", "destCidr":"%s", "policy":"%s", "syslogEnabled":%s, "comment":"%s"}\n' % (line['protocol'],line['srcPort'],line['srcCidr'],line['destPort'],line['destCidr'],line['policy'],str(line['syslogEnabled']).lower(),line['comment']))
                  
                    try:
                        f.close()
                    except:
                        printusertext('ERROR 24: Unable to close file path: "%s"' % filepath)
                        sys.exit(2)
                        
                    printusertext('INFO: Created backup for "%s". File: "%s"' % (net['name'], filename))
                    
            else:
                printusertext('WARNING: Unable to read MX ruleset for "%s" > "%s"' % (org.name,net['name']))

    return(0)
    
    
def stripdefaultrule(p_inputruleset):
    #strips the default allow ending rule from an MX L3 Firewall ruleset
    outputset = []
    
    if len(p_inputruleset) > 0:
        lastline = p_inputruleset[len(p_inputruleset)-1]
        if lastline == {'protocol': 'Any', 'policy': 'allow', 'comment': 'Default rule', 'srcCidr': 'Any', 'srcPort': 'Any', 'syslogEnabled': False, 'destPort': 'Any', 'destCidr': 'Any'}:
            outputset = p_inputruleset[:-1]
        else:
            outputset = p_inputruleset
            
    return(outputset)
   
   
def loadruleset(p_filepath):
    #Load a ruleset from file to memory. Drop default allow rules
    ruleset = []
    jdump = '['
    
    try:
        f = open(p_filepath, 'r')
    except:
        printusertext('ERROR 25: Unable to open file path for reading: "%s"' % p_filepath)
        sys.exit(2)
    
    for line in f:
        try:
            buffer = line
        except: 
            printusertext('ERROR 26: Unable to read from file: "%s"' % p_filepath)
            sys.exit(2)
            
        if len(buffer.strip())>1:  
            if not jdump.endswith('['):
                jdump += ','
            jdump += buffer[:-1]
            
    try:
        f.close()
    except:
        printusertext('ERROR 27: Unable to close input file "%s"' % p_filepath)
        sys.exit(2)
        
    jdump += ']'  
    
    try:
        ruleset = json.loads(jdump)
    except:
        printusertext('ERROR 28: Invalid input file format "%s"' % p_filepath)
        sys.exit(2)
    
    ruleset = stripdefaultrule(ruleset)
            
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
    
    #set flags
    if   p_mode == 'append':
        flag_append  = True
    elif p_mode == 'insert':
        flag_insert  = True
        if p_start == 0:
            printusertext('ERROR 51: Invalid start position "0" for insert command. First rule is #1')
            sys.exit(2)
    elif p_mode == 'replace':
        flag_replace = True
    else:
        printusertext('DEBUG: Invalid mode for cmdaddrules2(). Please check your script')
        sys.exit(2)
        
    if   p_source == 'file':
        flag_srcfile = True
    elif p_source == 'string':
        flag_srcstr  = True
    else:
        printusertext('DEBUG: Invalid source for cmdaddrules2(). Please check your script')
        sys.exit(2)
    
    #create backups before making changes, unless overriden by flag
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printusertext('INFO: Simulation mode. Changes will not be saved to cloud')

    #load ruleset to be added from file or command line
    diffset = []    
    if flag_srcfile:
        diffset = loadruleset(p_data)
    else:
        try:
            strload = json.loads(p_data)
        except:
            printusertext('ERROR 50: Ruleset to be added must be given in JSON format')
            sys.exit(2)
        #if loaded from CLI, ruleset might be either dict or table
        if isinstance(strload, dict):
            diffset.append(strload)
        else:
            diffset = strload
        diffset = stripdefaultrule(diffset)

    for org in p_orglist:
        for net in org.nwdata:
            flag_readsuccessful = True
            oldset = []
            
            #if insert or append mode, add the first part of the existing ruleset before the new one
            if flag_append or flag_insert:
                buffer      = readmxfwruleset(p_apikey, org.shardhost, net['id'])
                
                #adjust starting position to allow positive/negative counting (from start or end)
                bufferlen   = len(buffer)
                adjustedpos = bufferlen
                if flag_insert:
                    if p_start > 0:
                        if p_start < bufferlen:
                            adjustedpos = p_start-1
                        else:
                            printusertext('WARNING: Index out of range for "%s"' % net['name'])
                    else:
                        if p_start*-1 < bufferlen:
                            adjustedpos = bufferlen + p_start +1
                        else:
                            adjustedpos = 0
                            printusertext('WARNING: Index out of range for "%s"' % net['name'])
                        
                if buffer[0]['srcPort'] != 'null':
                    if flag_insert:
                        oldset = stripdefaultrule(buffer[:adjustedpos])
                    else:
                        oldset = stripdefaultrule(buffer)
                else:
                    flag_readsuccessful = False
                
            #add the new ruleset to be applied
            newset = oldset + diffset
                        
            #if insert mode, add the rest of the existing ruleset
            if flag_readsuccessful and flag_insert:
                newset += stripdefaultrule(buffer[adjustedpos:])  
                        
            if flag_readsuccessful:    
                if p_flagcommit:
                    printusertext('INFO: Writing ruleset for "%s"' % net['name'])
                    rcode = writemxfwruleset(p_apikey, org.shardhost, net['id'], newset)
                    if rcode == 'null':
                        printusertext('WARNING: Unable to write ruleset for "%s"' % net['name'])
                else: #print ruleset for review
                    printruleset(org.name, net['name'], newset)
            else:
                printusertext('WARNING: Skipping "%s": Unable to read existing ruleset' % net['name'])                    
    return(0)
    
    
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
        printusertext('DEBUG: Invalid mode for cmdremove(). Please check your script')
        sys.exit(2)
    
    linenum = 0
    if flag_modenumber:
        try:
            linenum = int(p_data)
        except:
            printusertext('ERROR 49: Integer expected in command "remove:<num>"')
            sys.exit(2)
    else:
        if len(p_data) < 1:
            printusertext('ERROR 48: Label must be at least 1 character long in command "remove-marked:<label>"')
            sys.exit(2)
    
    if (flag_modenumber and linenum != 0) or flag_modelabel:
        #create backups before making changes, unless overriden by flag
        if p_flagbackup and p_flagcommit:
            cmdcreatebackup(p_apikey, p_orglist)
        elif not p_flagcommit:
            printusertext('INFO: Simulation mode. Changes will not be saved to cloud')
     
        for org in p_orglist:
            for net in org.nwdata:
                newset = []
                buffer = stripdefaultrule(readmxfwruleset(p_apikey, org.shardhost, net['id']))
                if buffer[0]['srcPort'] != 'null':
                    bufferlen = len(buffer)
                    adjustednum = linenum
                    flag_madechanges = False
                    
                    if flag_modenumber:
                        #do adjustment of line number to enable counting backwards
                        if linenum < 0:
                            if linenum*-1 <=  bufferlen:
                                adjustednum = bufferlen + linenum + 1
                        if adjustednum < 1 or adjustednum > bufferlen:
                            printusertext('WARNING: Index out of range for "%s"' % net['name'])
                            
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
                            printusertext('INFO: Writing ruleset for "%s"' % net['name'])
                            rcode = writemxfwruleset(p_apikey, org.shardhost, net['id'], newset)
                            if rcode == 'null':
                                printusertext('WARNING: Unable to write ruleset for "%s"' % net['name'])
                        else:    
                            printusertext('INFO: No changes for ruleset in "%s"' % net['name'])
                    else: #print ruleset for review
                        printruleset(org.name, net['name'], newset)
                        
                else:
                    printusertext('WARNING: Skipping "%s": Unable to read existing ruleset' % net['name'])
    else:
        printusertext('ERROR 29: First rule number is "1". Last rule number is "-1"')
        sys.exit(2)
        
    return(0)
    
    
def cmddefaultdeny(p_apikey, p_orglist, p_flagcommit, p_flagbackup):
    #add a default deny rule to the end of the ruleset, if there is not already one
    
    denyrule = {"protocol":"any", "srcPort":"Any", "srcCidr":"Any", "destPort":"Any", "destCidr":"Any", "policy":"deny", "syslogEnabled":False, "comment":"compare"}
    
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printusertext('INFO: Simulation mode. Changes will not be saved to cloud')
    
    for org in p_orglist:
        for net in org.nwdata:
            ruleset = stripdefaultrule(readmxfwruleset(p_apikey, org.shardhost, net['id']))
            if ruleset[0]['srcPort'] != 'null':
                oldsetlen = len(ruleset)
                if oldsetlen > 0:
                    #compare all fields except syslog and comment
                    lastline = ruleset[oldsetlen-1]
                    denyrule['syslogEnabled'] = lastline['syslogEnabled']
                    denyrule['comment']       = lastline['comment']
                    if denyrule != lastline:
                        denyrule['syslogEnabled'] = False
                        denyrule['comment']       = 'Default deny added by mxfwctl'
                        ruleset.append(denyrule)
                        if p_flagcommit:
                            printusertext('INFO: Writing ruleset for "%s"' % net['name'])
                            rcode = writemxfwruleset(p_apikey, org.shardhost, net['id'], ruleset)
                            if rcode == 'null':
                                printusertext('WARNING: Unable to write ruleset for "%s"' % net['name'])
                        else: #print ruleset for review
                            printruleset(org.name, net['name'], ruleset)
                    else:
                        printusertext('INFO: No changes in ruleset for "%s"' % net['name'])
                        if not p_flagcommit:
                            printruleset(org.name, net['name'], ruleset)
            else:
                printusertext('WARNING: Skipping "%s": Unable to read existing ruleset' % net['name'])
    return(0)
    
    
def cmddefaultallow(p_apikey, p_orglist, p_flagcommit, p_flagbackup):
    #remove default deny rule from the end of the ruleset, if there is one
    
    denyrule = {"protocol":"any", "srcPort":"Any", "srcCidr":"Any", "destPort":"Any", "destCidr":"Any", "policy":"deny", "syslogEnabled":False, "comment":"compare"}
    
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printusertext('INFO: Simulation mode. Changes will not be saved to cloud')
    
    for org in p_orglist:
        for net in org.nwdata:    
            oldset = stripdefaultrule(readmxfwruleset(p_apikey, org.shardhost, net['id']))
            if oldset[0]['srcPort'] != 'null':
                oldsetlen = len(oldset)
                if oldsetlen > 0:
                    #compare all fields except syslog and comment
                    lastline = oldset[oldsetlen-1]
                    denyrule['syslogEnabled'] = lastline['syslogEnabled']
                    denyrule['comment']       = lastline['comment']
                    if denyrule == lastline:
                        if p_flagcommit:
                            printusertext('INFO: Writing ruleset for "%s"' % net['name'])
                            rcode = writemxfwruleset(p_apikey, org.shardhost, net['id'], oldset[:-1])
                            if rcode == 'null':
                                printusertext('WARNING: Unable to write ruleset for "%s"' % net['name'])
                        else: #print ruleset for review
                            printruleset(org.name, net['name'], oldset[:-1])
                    else:
                        printusertext('INFO: No changes in ruleset for "%s"' % net['name'])
                        if not p_flagcommit:
                            printruleset(org.name, net['name'], oldset[:-1])
                    
            else:
                printusertext('WARNING: Skipping "%s": Unable to read existing ruleset' % net['name'])
    
    return(0)
    
    
def cmdremoveall(p_apikey, p_orglist, p_flagcommit, p_flagbackup):
    #remove all rules in ruleset
    
    if p_flagbackup and p_flagcommit:
        cmdcreatebackup(p_apikey, p_orglist)
    elif not p_flagcommit:
        printusertext('INFO: Simulation mode. Changes will not be saved to cloud')
    
    for org in p_orglist:
        for net in org.nwdata:    
            if p_flagcommit:
                printusertext('INFO: Erasing ruleset for "%s"' % net['name'])
                rcode = writemxfwruleset(p_apikey, org.shardhost, net['id'], [])
                if rcode == 'null':
                    printusertext('WARNING: Unable to write ruleset for "%s"' % net['name'])
            else:
                printusertext('INFO: Commit mode will erase MX ruleset for "%s"' % net['name'])
    
    return(0)
    
    
def cmdloadfolder(p_apikey, p_orglist, p_folder, p_flagcommit, p_flagbackup):
    #code for command "load-folder <folder>"
    
    #create a temporary limited org list copy with a single network to be able to reuse cmdaddrules()
    temporglist = []
    temporglist.append(c_organizationdata())
    
    for org in p_orglist:
        temporglist[0].id          = org.id
        temporglist[0].name        = org.name
        temporglist[0].shardhost   = org.shardhost
        temporglist[0].nwdata      = []
        for net in org.nwdata:
            temporglist[0].nwdata.append(net)        
            filename = formatfilename(org.name, net['name'])
            path = p_folder + '/' + filename
            
            printusertext('INFO: Source file for "%s > %s" is "%s"' % (org.name, net['name'], path))
                        
            cmdaddrules2(p_apikey, temporglist, 'file', path, 'replace', p_flagcommit, p_flagbackup)      

    return(0)
    
    
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
                    printusertext('ERROR 30: Missing definition <file> in command append-file:<file>')
                    sys.exit(2)
            else:
                printusertext('ERROR 31: Missing definition <file> in command append-file:<file>')
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
                printusertext('ERROR 32: Error in command "insert-file:<num>:<file>"')
                sys.exit(2)
                
        elif cmd == 'replace-file':
            if len(splitstr) > 1:
                parameter = splitstr[1].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'file', parameter, 'replace', p_flagcommit, p_flagbackup)
                else:
                    printusertext('ERROR 33: Missing definition <file> in command replace-file:<file>')
                    sys.exit(2)
            else:
                printusertext('ERROR 34: Missing definition <file> in command replace-file:<file>')
                sys.exit(2)
                
        elif cmd == 'load-folder':
            if len(splitstr) > 1:
                parameter = splitstr[1].strip()
                if len(parameter) > 0:
                    cmdloadfolder(p_apikey, p_orglist, parameter, p_flagcommit, p_flagbackup)
                else:
                    printusertext('ERROR 35: Missing definition <folder> in command load-folder:<folder>')
                    sys.exit(2)
            else:
                printusertext('ERROR 36: Missing definition <folder> in command load-folder:<folder>')
                sys.exit(2)
            
        elif cmd == 'append':        
            if len(splitstr) > 1:
                parameter = p_commandstr[p_commandstr.find(':')+1:].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'string', parameter, 'append', p_flagcommit, p_flagbackup)
                else:
                    printusertext('ERROR 37: Missing definition <string> in command append:<string>')
                    sys.exit(2)
            else:
                printusertext('ERROR 38: Missing definition <string> in command append:<string>')
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
                printusertext('ERROR 39: Error in command "insert:<num>:<string>"')
                sys.exit(2)
                
        elif cmd == 'replace':
            if len(splitstr) > 1:
                parameter = p_commandstr[p_commandstr.find(':')+1:].strip()
                if len(parameter) > 0:
                    cmdaddrules2(p_apikey, p_orglist, 'string', parameter, 'replace', p_flagcommit, p_flagbackup)
                else:
                    printusertext('ERROR 40: Missing definition <file> in command replace-file:<file>')
                    sys.exit(2)
            else:
                printusertext('ERROR 41: Missing definition <file> in command replace-file:<file>')
                sys.exit(2)
            
        elif cmd == 'remove':
            if len(splitstr) > 1:
                cmdremove(p_apikey, p_orglist, 'number', splitstr[1].strip(), p_flagcommit, p_flagbackup)
            else:
                printusertext('ERROR 42: Missing line number in "remove:<num>"')
                sys.exit(2)
                
        elif cmd == 'remove-all':
            cmdremoveall(p_apikey, p_orglist, p_flagcommit, p_flagbackup)
            
        elif cmd == 'remove-marked':
            if len(splitstr) > 1:
                cmdremove(p_apikey, p_orglist, 'label', splitstr[1].strip(), p_flagcommit, p_flagbackup)
            else:
                printusertext('ERROR 43: Missing label in "remove-marked:<label>"')
                sys.exit(2)             
                
        elif cmd == 'default-allow':
            cmddefaultallow(p_apikey, p_orglist, p_flagcommit, p_flagbackup)
            
        elif cmd == 'default-deny':
            cmddefaultdeny(p_apikey, p_orglist, p_flagcommit, p_flagbackup)
            
        else:
            printusertext('ERROR 44: Invalid command "%s"' % p_commandstr)
            sys.exit(2)
            
    else:
        printusertext('DEBUG: Command string parsing failed')
        sys.exit(2)
    
    return (0)

    
def main(argv):
    #python mxfirewallcontrol -k <key> -o <org> [-f <filter>] [-c <command>] [-m <mode>]

    #set default values for command line arguments
    arg_apikey  = ''
    arg_org     = ''
    arg_filter  = ''
    arg_command = ''
    arg_mode    = 'simulation'
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:f:c:m:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-o':
            arg_org     = arg
        elif opt == '-f':
            arg_filter   = arg
        elif opt == '-c':
            arg_command = arg
        elif opt == '-m':
            arg_mode    = arg
                      
    #check if all parameters are required parameters have been given
    if arg_apikey == '' or arg_org == '':
        printhelp()
        sys.exit(2)
        
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
        printusertext('ERROR 45: Argument -m <mode> is invalid')
        sys.exit(2)
        
    printusertext('INFO: Retrieving organization info')
        
    #compile list of organizations to be processed
    orglist = []
    if arg_org == '/all':
        orgjson = getorglist(arg_apikey)
                
        i = 0
        for record in orgjson:
            orglist.append(c_organizationdata())
            orglist[i].name = record['name']
            orglist[i].id   = record['id']
            i += 1
        
    else:
        orglist.append(c_organizationdata())
        orglist[0].name = arg_org
        orglist[0].id   = getorgid(arg_apikey, arg_org)
        if orglist[0].id == 'null':
            printusertext('ERROR 46: Fetching source organization ID failed')
            sys.exit(2)
        
    #get shard host/FQDN where destination org is stored
    #this call sometimes fails. implementing a try-verify-wait-repeat loop
    MAX_SHARD_RESOLVE_TRIES = 10
    for record in orglist:
        flag_unabletoresolveshard = True
        for i in range (0, MAX_SHARD_RESOLVE_TRIES):
            shardhost = getshardhost(arg_apikey, record.id)
            if shardhost == 'null':
                time.sleep(API_EXEC_DELAY*(i+1))
            else:
                flag_unabletoresolveshard = False
                break
        if flag_unabletoresolveshard:
            printusertext('ERROR 47: Unable to read data for org "%s"' % record.name)
            sys.exit(2)
        else:
            record.shardhost = shardhost
            
    printusertext('INFO: Selecting networks and templates according to filters')
            
    #parse filter argument
    filters = parsefilter(arg_filter)
    
    #compile filtered networks' list
    for org in orglist:
        filterednwlist = filternetworks (arg_apikey, org.shardhost, org.id, filters)
        org.nwdata = filterednwlist
                          
    #parse and execute command
    parsecommand(arg_apikey, orglist, arg_command, flag_modecommit, flag_modebackup)
                   
    printusertext('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])