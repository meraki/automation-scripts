# This is a script to manage administrator accounts across organizations.
#
# To run the script, enter:
#  python manageadmins.py -k <api key> -o <organization> -a <admin account email> -n <admin name> -p <privilege>
#
# Mandatory arguments:
#  -k <api key>         : Your Meraki Dashboard API key
#  -o <organization>    : Dashboard organizations in scope. Valid forms:
#                           -o <org name>       Organizations with matching name. Use * for wildcard (one * only)
#                           -o /all             All organizations accessible by your API key
#  -c <command>         : Command to be executed. Valid forms:
#                           -c add              Add an administrator
#                           -c delete           Delete an administrator
#                           -c find             Find organizations in scope accessible by a specific admin
#                           -c list             List administrators
#
# Optional arguments:
#  -a <admin account>   : Email of admin account to be added/deleted/matched. Required for commands add, delete and find
#  -n <admin name>      : Name for admin to be added by the "add" command. Required for "add".
#  -p <privilege level> : Privilege level for admin to be added by the "add" command. Default is "full". Valid options:
#                           -p full             Full organization admin
#                           -p read-only        Read only organization admin
# 
# Example, remove admin "miles.meraki@ikarem.net" from all organizations:
#  python manageadmins.py -k 1234 -o /all -c delete -a miles.meraki@ikarem.net
# Example, add admin "miles.meraki@ikarem.net" to all organizations with a name starting with "TIER1_":
#  python manageadmins.py -k 1234 -o TIER1_* -c add -a miles.meraki@ikarem.net -n Miles
#
# This script was developed using Python 3.6.4. You will need the Requests module to run it. You can install
#  it modules via pip:
#  pip install requests
#
# More info on this module:
#   http://python-requests.org
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2018-03-06


import sys, getopt, requests, json, time
from datetime import datetime


#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

#connect and read timeouts for the Requests module
REQUESTS_CONNECT_TIMEOUT = 30
REQUESTS_READ_TIMEOUT    = 30

#used by merakirequestthrottler(). DO NOT MODIFY
LAST_MERAKI_REQUEST = datetime.now() 


class c_orgdata:
    def __init__(self):
        self.id     = ''
        self.name   = ''
        self.shard  = '' #Meraki cloud shard where this org is stored


def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message) 
    
    
def printhelp():
    #prints help text

    printusertext('This is a script to manage administrator accounts across organizations.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext('python manageadmins.py -k <api key> -o <organization> -a <admin account email> -n <admin name> -p <privilege>')
    printusertext('')
    printusertext('Mandatory arguments:')
    printusertext(' -k <api key>         : Your Meraki Dashboard API key')
    printusertext(' -o <organization>    : Dashboard organizations in scope. Valid forms:')
    printusertext('                        -o <org name>       Organizations with matching name. Use * for wildcard (one * only)')
    printusertext('                        -o /all             All organizations accessible by your API key')
    printusertext(' -c <command>         : Command to be executed. Valid forms:')
    printusertext('                        -c add              Add an administrator')
    printusertext('                        -c delete           Delete an administrator')
    printusertext('                        -c find             Find organizations in scope accessible by a specific admin')
    printusertext('                        -c list             List administrators')
    printusertext('')
    printusertext('Optional arguments:')
    printusertext(' -a <admin account>   : Email of admin account to be added/deleted/matched. Required for add, delete and find')
    printusertext(' -n <admin name>      : Name for admin to be added by the "add" command. Required for "add".')
    printusertext(' -p <privilege level> : Privilege level for admin to be added by the "add" command. Default is "full". Valid options:')
    printusertext('                         -p full             Full organization admin')
    printusertext('                         -p read-only        Read only organization admin')
    printusertext('')
    printusertext('Example, remove admin "miles.meraki@ikarem.net" from all organizations:')
    printusertext(' python manageadmins.py -k 1234 -o /all -c delete -a miles.meraki@ikarem.net')
    printusertext('Example, add admin "miles.meraki@ikarem.net" to all organizations with a name starting with "TIER1_":')
    printusertext(' python manageadmins.py -k 1234 -o TIER1_* -c add -a miles.meraki@ikarem.net -n Miles')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')    


def merakirequestthrottler(p_requestcount=1):
    #makes sure there is enough time between API requests to Dashboard not to hit shaper
    global LAST_MERAKI_REQUEST
    
    if (datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY*p_requestcount):
        time.sleep(API_EXEC_DELAY*p_requestcount)
    
    LAST_MERAKI_REQUEST = datetime.now()
    return   
    
    
def getorglist(p_apikey):
    #returns the organizations' list for a specified admin
    
    merakirequestthrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        printusertext('ERROR 01: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'id':'null'})
        return returnvalue
    
    rjson = r.json()
    
    return(rjson)
    
    
def getorgadmins(p_apikey, p_orgid, p_shardhost):
    #returns the list of admins for a specified organization
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/admins' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        printusertext('ERROR 02: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'id':'null'})
        return returnvalue
    
    rjson = r.json()
    
    return(rjson)
  

def addorgadmin(p_apikey, p_orgid, p_shardurl, p_email, p_name, p_privilege):
   #creates admin into an organization
   
    merakirequestthrottler()
    
    try:
        r = requests.post('https://%s/api/v0/organizations/%s/admins' % (p_shardurl, p_orgid), data=json.dumps({'name': p_name, 'email': p_email, 'orgAccess': p_privilege}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
        
    if r.status_code != requests.codes.ok:
        return ('fail')
      
    return('ok')  
  
    
def deleteorgadmin(p_apikey, p_orgid, p_shardhost, p_adminid):
    #removes an administrator from an organization
    
    merakirequestthrottler()
    try:
        r = requests.delete('https://%s/api/v0/organizations/%s/admins/%s' % (p_shardhost, p_orgid, p_adminid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        printusertext('ERROR 04: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        return ('fail')
    
    return ('ok')
    
    
def findadminid(p_adminlist, p_adminemail):
    #returns admin id associated with an email or 'null', if it is not found
    
    for admin in p_adminlist:
        if admin['email'] == p_adminemail:
            return (admin['id'])  

    return('null')
    
    
def filterorglist(p_apikey, p_filter, p_orglist):
    #tried to match a list of org IDs to a filter expression
    #   /all    all organizations
    #   <name>  match if name matches. name can contain one wildcard at start, middle or end
    
    returnlist = []
    
    flag_processall     = False
    flag_gotwildcard    = False
    if p_filter == '/all':
        flag_processall = True
    else:
        wildcardpos = p_filter.find('*')
        
        if wildcardpos > -1:
            flag_gotwildcard = True
            startsection    = ''
            endsection      = ''
                        
            if   wildcardpos == 0:
                #wildcard at start of string, only got endsection
                endsection   = p_filter[1:]
                
            elif wildcardpos == len(p_filter) - 1:
                #wildcard at start of string, only got startsection
                startsection = p_filter[:-1]
            else:
                #wildcard at middle of string, got both startsection and endsection
                wildcardsplit = p_filter.split('*')
                startsection  = wildcardsplit[0]
                endsection    = wildcardsplit[1]
                
                
    for org in p_orglist:
        if flag_processall:
            returnlist.append(c_orgdata())
            returnlist[len(returnlist)-1].id    = org['id']
            returnlist[len(returnlist)-1].name  = org['name']
        elif flag_gotwildcard:
            flag_gotmatch = True
            #match startsection and endsection
            startlen = len(startsection)
            endlen   = len(endsection)
            
            if startlen > 0:
                if org['name'][:startlen] != startsection:
                    flag_gotmatch = False
            if endlen   > 0:
                if org['name'][-endlen:]   != endsection:
                    flag_gotmatch = False
                    
            if flag_gotmatch:
                returnlist.append(c_orgdata())
                returnlist[len(returnlist)-1].id    = org['id']
                returnlist[len(returnlist)-1].name  = org['name']  
        else:
            #match full name
            if org['name'] == p_filter:
                returnlist.append(c_orgdata())
                returnlist[len(returnlist)-1].id    = org['id']
                returnlist[len(returnlist)-1].name  = org['name'] 
       
    return(returnlist)
    
    
def cmdadd(p_apikey, p_orgs, p_email, p_name, p_privilege):
    #creates an administrator in all orgs in scope
    
    if p_privilege not in ['full', 'read-only']:
        printusertext('ERROR 09: Unsupported privilege level "%s"' % p_privilege)
        sys.exit(2)
    
    for org in p_orgs:
        orgadmins = getorgadmins(p_apikey, org.id, 'api.meraki.com')
        adminid   = findadminid(orgadmins, p_email)
        if adminid != 'null':
            printusertext('INFO: Skipping org "%s". Admin already exists' % org.name)
        else:
            printusertext('INFO: Creating admin "%s" in org "%s"' % (p_email, org.name))
            addorgadmin(p_apikey, org.id, 'api.meraki.com', p_email, p_name, p_privilege)
            
            #verify that admin was correctly created
            orgadmins = getorgadmins(p_apikey, org.id, 'api.meraki.com')
            adminid   = findadminid(orgadmins, p_email)
            if adminid == 'null':
                printusertext('WARNING: Unable to create admin "%s" in org "%s"' % (p_email, org.name))
                
    return(0)
    
def cmddelete(p_apikey, p_orgs, p_admin):
    #deletes an administrator from all orgs in scope

    for org in p_orgs:
        orgadmins = getorgadmins(p_apikey, org.id, 'api.meraki.com')
        adminid   = findadminid(orgadmins, p_admin)
        if adminid != 'null':
            printusertext('INFO: Removing admin "%s" from org "%s"' % (p_admin, org.name))
            deleteorgadmin(p_apikey, org.id, 'api.meraki.com', adminid)
        else:
            printusertext('INFO: Admin "%s" cannot be found in org "%s"' % (p_admin, org.name))
            
        #verify that the admin has actually been deleted
        orgadmins = getorgadmins(p_apikey, org.id, 'api.meraki.com')
        adminid   = findadminid(orgadmins, p_admin)
        if adminid != 'null':
            printusertext('WARNING: Unable to remove admin "%s" from org "%s"' % (p_admin, org.name))
    
    return(0)
    
    
def cmdfind(p_apikey, p_orgs, p_admin):
    #finds organizations that contain an admin with specified email
    
    for org in p_orgs:
        orgadmins = getorgadmins(p_apikey, org.id, 'api.meraki.com')
        adminid   = findadminid(orgadmins, p_admin)
        if adminid != 'null':
            print('Found admin "%s" in org "%s"' % (p_admin, org.name))
            
    return(0)
    
    
def cmdlist(p_apikey, p_orgs):
    #lists all admins in specified orgs
    
    for org in p_orgs:
        orgadmins = getorgadmins(p_apikey, org.id, 'api.meraki.com')
        if orgadmins[0]['id'] != 'null':
            print('\nAdministrators for org "%s"' % org.name)
            print('NAME                           EMAIL                                              ORG PRIVILEGE')
            for admin in orgadmins:
                print('%-30s %-50s %-20s' % (admin['name'], admin['email'], admin['orgAccess']))
    
    return(0)
    
    
def main(argv):
    #initialize variables for command line arguments
    arg_apikey      = ''
    arg_orgname     = ''
    arg_admin       = ''
    arg_command     = ''
    arg_name        = ''
    arg_privilege   = ''
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:c:a:n:p:')
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
            arg_orgname = arg
        elif opt == '-c':
            arg_command = arg    
        elif opt == '-a':
            arg_admin   = arg
        elif opt == '-n':
            arg_name    = arg
        elif opt == '-p':
            arg_privilege = arg
            
    #check if all parameters are required parameters have been given
    if arg_apikey == '' or arg_orgname == '' or arg_command == '':
        printhelp()
        sys.exit(2)
        
    #fail invalid commands quickly, not to annoy user
    cleancmd = arg_command.lower().strip()
    if cleancmd not in ['add', 'delete', 'find', 'list']:
        printusertext('ERROR 05: Invalid command "%s"' % cleancmd)
        sys.exit(2)    
    if arg_admin == '' and cleancmd != 'list':
        printusertext('ERROR 06: Command "%s" needs parameter -a <admin account>' % arg_command)
        sys.exit(2)
    if cleancmd == 'add' and arg_name == '':
        printusertext('ERROR 07: Command "add" needs parameter -n <name>')
        sys.exit(2)
        
    #set default values for optional arguments
    if arg_privilege == '':
        arg_privilege = 'full'
                
    
    #build list of organizations to be processed
    
    #get list org all orgs belonging to this admin
    raworglist = getorglist(arg_apikey)
    if raworglist[0]['id'] == 'null':
        printusertext('ERROR 08: Error retrieving organization list')
        sys.exit(2)
    
    #match list of orgs to org filter
    matchedorgs = filterorglist(arg_apikey, arg_orgname, raworglist)
    
    #launch correct command code
    if cleancmd == 'add':
        cmdadd(arg_apikey, matchedorgs, arg_admin, arg_name, arg_privilege)
    elif cleancmd == 'delete':
        cmddelete(arg_apikey, matchedorgs, arg_admin)
    elif cleancmd == 'find':
        cmdfind(arg_apikey, matchedorgs, arg_admin)
    elif cleancmd == 'list':
        cmdlist(arg_apikey, matchedorgs)
    
if __name__ == '__main__':
    main(sys.argv[1:])