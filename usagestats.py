# This is a script to calculate and compare usage statistics among different subnets.
#
# The full manual for this script can be found here:
#  https://github.com/meraki/automation-scripts/blob/master/usagestats_manual.pdf 
#
# To run the script, enter:
#  python usagestats.py -k <key> [-d <database> -c <command> -i <initfile> -g <groups> -f <filter>] [-u <user> -p <pass> -r <recipient> -s <server>]
#
# Example:
#  python usagestats.py -k 1234 -i myproject.cfg -c report:last-month
#
# Mandatory argument:
#   -k <key>            : Your Meraki Dashboard API key
# Database and command operation arguments:
#   -d <database>       : SQLite database filename. Can be omitted, if one is defined in the init config file
#                         A separate database filename should be used for every report project. The first time a project
#                         is created, its configuration should be given as an init config file, or command line arguments.
#                         After the project is created, a copy of its configuration is stored in the database file.
#   -c <command>        : Defines the operation to be executed by the script. Valid options:
#                           sync               : Populate the database with information pulled from Dashboard. It is
#                                                recommended that the sync operation is run at least once a week
#                                                for every report project. The "report" command also executes a sync
#                           report:<time>      : Generate a usage report for the time period defined in <time>. Valid
#                                                options for <time>:
#                                                <integer>                   : Report for last <integer> days
#                                                last-week                   : Report for last week (Mon-Sun)
#                                                last-month                  : Report for last calendar month
#                                                <start date> to <end date>  : Report between two dates, including them
#                                                                              Date format: yyyy-mm-dd
#                           report-offline:<t> : Same as "report:", but does not execute a database sync first
#                           dbdump             : Dump contents of database to screen
#                           dbreconfigure      : Overwrites configuration stored in the database with a new one. Does not
#                                                touch network or usage data. Be very careful when using this option
#                         If omitted, the default command is "report:last-week".
# Optional arguments to create a database:
#   -i <initfile>       : Init config file, containing values to arguments (see section "Writing an init config file").
#                         This file is only used when a new database is created.
#   -g <groups>         : Define groups to compare for bandwidth usage. Valid forms for <groups>:
#                           "<name>=<subnet>,<subnet>;<name>=<subnet>,<subnet>"
#                         The value <name> defines a name for the group.
#                         Valid values for <subnet>:
#                           sub:<ip address>/<mask>         eg. sub:10.0.0.0/8
#                           vid:<VLAN ID>                   eg. vid:10
#                           vname:<VLAN name>               eg. vname:Corp
#                         To make a subnet/vlan definition specific to one org, network or network tag prefix it
#                         with one or more of the following:
#                           @org:<org name>, @net:<net name>, @tag:<net tag>
#                         Leave a space ( ) between the last prefix and the subnet/vlan definition.
#                         Example:
#                           "Corp=sub:192.168.10.0/24,sub:10.10.10.0/24,vname:Corp;Guest=sub:172.16.0.0/12,@org:Myorg vid:10"
#                         You can use "vlanid" and "vlanname" instead of "vid" and "vname".
#                         If omitted, one group will be displayed, with name "Overall" and subnet "0.0.0.0/0".
#   -f <filter>         : Process only certain organizations, networks, network tags or device types.
#                         You can define multiple filters by separating them with commas. Only one filter per type
#                         is allowed. Available filters:
#                           org:<org name>
#                           net:<net name>
#                           tag:<net tag>
#                           dtag:<device tag>
#                           dtype:<device type>
#                         Valid options for dtype:
#                           dtype:mr
#                           dtype:ms
#                           dtype:mx
#                           dtype:all
#                         Option "dtype:mx" includes teleworker gateways (Zx). Example of a valid filter combination:
#                           "org:My company,tag:branch,dtype:mr"
#                         If omitted, the default filter is "dtype:mx".
# Optional arguments to send report by email. User, password and recipient are required for this function:
#   -u <user>           : The username (email address) that will be used to send the alert message
#   -p <pass>           : Password for the email address where the message is sent from
#   -r <recipient>      : Recipient email address
#   -s <server>         : Server to use for sending SMTP. If omitted, Gmail will be used
#
# Writing an init config file:
#  An init config file can contain two sections: Groups and Options, as defined by the following headers:
#   [GROUPS]
#   [OPTIONS]
#  Groups are defined as a separate section [GROUPS] with the following format:
#   [GROUPS]
#   groupname=First
#   subnet=10.0.0.0/24
#   subnet=192.168.0.0/16
#   vlanid=10
#   vlanname=Corp
#
#   groupname=Second
#   subnet=10.20.20.0/24
#   @org:Orgname@net:Netname vlanid=500
#   @tag:Taggednet vlanname=Guest
#
#   A group is defined as a line containing the name of the group (groupname:<value>), followed by lines defining the 
#   subnets, VLAN IDs and VLAN names it consists of. The prefixes @org: @net: and @tag: can be used to make a line
#   specific to an organization, network to network tag. You can use "vid" and "vname" instead of "vlanid" and "vlanname".
#  
#  The following attributes are supported under the [OPTIONS] section:
#   database=<filename>             : Define database filename
#   filter=<filter>                 : Define filter
#
#  Blank lines an lines beginning with a hash character (#) will be ignored.
#
# An example of an init config file can be found here:
#   https://github.com/meraki/automation-scripts/blob/master/usagestats_initconfig.txt
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# #TODO: add dbpurge?
# #TODO: add dbarchive?
# #TODO: add exclude-meraki-traffic?
# #TODO: add dbinfo?
# #TODO: check why the script is throwing warnings when the same subnet has been configured multiple times (sub+vid+vname)


import sys, getopt, requests, json, time, ipaddress, datetime, sqlite3, os.path, smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

#SECTION: CLASS DEFINITIONS


class c_organizationdata:
    def __init__(self):
        self.name       = ''
        self.id         = ''
        self.shardhost  = ''
        self.nets       = [] #array of c_networkdata()
#end class  

class c_networkdata:
    def __init__(self):
        self.name       = ''
        self.id         = ''
        self.tags       = ''
        self.orgid      = '' #used by cmdreport()
        self.orgname    = '' #used by cmdreport()
        self.totaldown  = 0  #used by cmdreport()
        self.totalup    = 0  #used by cmdreport()
        self.devs       = [] #array of c_devicedata()
        self.groups     = [] #c_groupdata() will be added here
#end class

class c_devicedata:
    def __init__(self):
        self.name       = ''
        self.serial     = ''
        self.tags       = ''
        self.clients    = []
#end class

#class for subnet group definitions
class c_groupdata:
    def __init__(self):
        self.name       = ''
        self.id         = ''
        self.dbuffer    = []
        self.ubuffer    = []
        self.subnets    = []
#end class

#subnet definition class. groups consist of multiples of these
class c_subnetdata:
    def __init__(self):
        self.subnet     = ''
        self.vname      = ''
        self.vid        = ''
        self.orgname    = ''
        self.orgid      = ''
        self.netname    = ''
        self.netid      = ''
        self.nettag     = ''
#end class

#class that contains options as read from command line parameters or init file
class c_optiondata:
    def __init__(self):
        self.initfile   = ''
        self.dbfile     = ''
        self.rawcmd     = ''
        self.rawfilter  = ''
        self.rawgroups  = ''
        self.rawnet     = ''
        self.org        = ''
        self.netname    = ''
        self.nettag     = ''
        self.emailuser  = ''
        self.emailpass  = ''
        self.emailrecp  = ''
        self.emailsrvr  = ''
        self.sendemail  = False
#end class

class c_filterdata():
    def __init__(self):
        self.org        = ''
        self.netname    = ''
        self.nettag     = ''
        self.devtag     = ''
        self.devtype    = []
#end class


#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOR
#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21
#connect and read timeouts for the Requests module
REQUESTS_CONNECT_TIMEOUT = 30
REQUESTS_READ_TIMEOUT = 30
#Date format string for user input
DATE_USER_FORMAT = '%Y-%m-%d'
#used to track if the database format used by this script has changed since a project database was created
DB_VERSION = 4

#SECTION: GLOBAL VARIABLES: DO NOT MODIFY
LAST_MERAKI_REQUEST = datetime.datetime.now()   #used by merakirequestthrottler()
DATE_DB_FORMAT = '%Y-%m-%d'                     #Date format used for storage in database


#SECTION: CODE


def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

    
def printhelp():
    #prints help text

    printusertext('This is a script to calculate and compare usage statistics among different subnets.')
    printusertext('Read the manual for more information: #TODO INSERT GITHUB LINK')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext('python usagestats.py -k <key> [-d <db> -c <cmd> -i <initf> -g <grps> -f <filtr>] [-u <usr> -p <pw> -r <rcp> -s <srv>]')
    printusertext('')
    printusertext('Example:')
    printusertext('python usagestats.py -k 1234 -i myproject.cfg -c report:last-month')
    printusertext('')
    printusertext('Mandatory argument:')
    printusertext(' -k <key>            : Your Meraki Dashboard API key')
    printusertext('Database and command operation arguments:')
    printusertext(' -d <database>       : SQLite database filename. Can be omitted, if one is defined in the init config file')
    printusertext('                       A separate database filename should be used for every report project. The first time a project')
    printusertext('                       is created, its configuration should be given as an init cfg file, or command line arguments.')
    printusertext('                       After the project is created, a copy of its configuration is stored in the database file.')
    printusertext(' -c <command>        : Defines the operation to be executed by the script. Valid options:')
    printusertext('                         sync               : Populate the database with information pulled from Dashboard. It is')
    printusertext('                                              recommended that the sync operation is run at least once a week')
    printusertext('                                              for every report project. The "report" command also executes a sync')
    printusertext('                         report:<time>      : Generate a usage report for the time period defined in <time>. Valid')
    printusertext('                                              options for <time>:')
    printusertext('                                              <integer>                   : Report for last <integer> days')
    printusertext('                                              last-week                   : Report for last week (Mon-Sun)')
    printusertext('                                              last-month                  : Report for last calendar month')
    printusertext('                                              <start date> to <end date>  : Report between two dates, including them')
    printusertext('                                                                            Date format: yyyy-mm-dd')
    printusertext('                         report-offline:<t> : Same as "report:", but does not execute a database sync first')
    printusertext('                         dbdump             : Dump contents of database to screen')
    printusertext('                         dbreconfigure      : Overwrites configuration stored in the database with a new one. Doesn\'t')
    printusertext('                                              touch network or usage data. Be very careful when using this option')
    printusertext('                       If omitted, the default command is "report:last-week".')
    printusertext('Optional arguments to create a database:')
    printusertext(' -i <initfile>       : Init config file, containing values to arguments (see section "Writing an init config file").')
    printusertext('                       This file is only used when a new database is created.')
    printusertext(' -g <groups>         : Define groups to compare for bandwidth usage. Valid forms for <groups>:')
    printusertext('                         "<name>=<subnet>,<subnet>;<name>=<subnet>,<subnet>"')
    printusertext('                       The value <name> defines a name for the group.')
    printusertext('                       Valid values for <subnet>:')
    printusertext('                         sub:<ip address>/<mask>         eg. sub:10.0.0.0/8')
    printusertext('                         vid:<VLAN ID>                   eg. vid:10')
    printusertext('                         vname:<VLAN name>               eg. vname:Corp')
    printusertext('                       To make a subnet/vlan definition specific to one org, network or network tag prefix it')
    printusertext('                       with one or more of the following:')
    printusertext('                         @org:<org name>, @net:<net name>, @tag:<net tag>')
    printusertext('                       Leave a space ( ) between the last prefix and the subnet/vlan definition.')
    printusertext('                       Example:')
    printusertext('                    "Corp=sub:192.168.10.0/24,sub:10.10.10.0/24,vname:Corp;Guest=sub:172.16.0.0/12,@org:Myorg vid:10"')
    printusertext('                       You can use "vlanid" and "vlanname" instead of "vid" and "vname".')
    printusertext('                       If omitted, one group will be displayed, with name "Overall" and subnet "0.0.0.0/0".')
    printusertext(' -f <filter>         : Process only certain organizations, networks, network tags or device types.')
    printusertext('                       You can define multiple filters by separating them with commas. Only one filter per type')
    printusertext('                       is allowed. Available filters:')
    printusertext('                         org:<organization name>')
    printusertext('                         net:<network name>')
    printusertext('                         tag:<network tag>')
    printusertext('                         dtag:<device tag>')
    printusertext('                         dtype:<device type>')
    printusertext('                       Valid options for dtype:')
    printusertext('                         dtype:mr')
    printusertext('                         dtype:ms')
    printusertext('                         dtype:mx')
    printusertext('                         dtype:all')
    printusertext('                       Option "dtype:mx" includes teleworker gateways (Zx). Example of a valid filter combination:')
    printusertext('                         "org:My company,tag:branch,dtype:mr"')
    printusertext('                       If omitted, the default filter is "dtype:mx".')
    printusertext('Optional arguments to send report by email. User, password and recipient are required for this function:')
    printusertext(' -u <user>           : The username (email address) that will be used to send the alert message')
    printusertext(' -p <pass>           : Password for the email address where the message is sent from')
    printusertext(' -r <recipient>      : Recipient email address')
    printusertext(' -s <server>         : Server to use for sending SMTP. If omitted, Gmail will be used')
    printusertext('')
    printusertext('Use double quotes ("") to pass arguments containing spaces in Windows.')
    
    
    
def merakirequestthrottler(p_requestcount=1):
    #makes sure there is enough time between API requests to Dashboard not to hit shaper
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY*p_requestcount):
        time.sleep(API_EXEC_DELAY*p_requestcount)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return
          
    
def getorglist(p_apikey):
    #returns the organizations' list for a specified admin
    
    merakirequestthrottler()
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 01: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'id':'null'})
        return returnvalue
    
    rjson = r.json()
    
    return(rjson)
      
    
def getshardhost(p_apikey, p_orgid):
    #patch
    return("api-mp.meraki.com")
   
   
def getnwlist(p_apikey, p_shardhost, p_orgid):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'name': 'null', 'id': 'null'})
        return(returnvalue)
    
    return(r.json())
    
    
def getdevicelist(p_apikey, p_shardhost, p_nwid):
    #returns a list of all devices in a network
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/networks/%s/devices' % (p_shardhost, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 04: Unable to contact Meraki cloud')
        sys.exit(2)
        
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'serial': 'null', 'model': 'null'})
        return(returnvalue)
    
    return(r.json())
    
    
def getvlanlist(p_apikey, p_shardhost, p_nwid):
    #returns list of all MX VLANs in a network
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/networks/%s/vlans' % (p_shardhost, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 05: Unable to contact Meraki cloud')
        sys.exit(2)
        
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'id': 'null'})
        return(returnvalue)
    
    return(r.json())
    

def getclientlist(p_apikey, p_shardhost, p_serial, p_timespan):
    #get client list for a network device from Dashboard. No artificial delay
    try:
        r = requests.get('https://%s/api/v0/devices/%s/clients?timespan=%s' % (p_shardhost, p_serial, p_timespan), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 06: Unable to contact Meraki cloud')
        sys.exit(2)
        
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'id': 'null'})
        return(returnvalue)
    
    return(r.json())
    

def loadinitfile(p_filename):
    #Loads script options from init config file. The options will be converted to the same format that CLI arguments
    #would provide them. Their values will be later processed later in another function
    opt = c_optiondata()
    section = ''
    groupstr = ''
    
    try:
        f = open(p_filename, 'r')
    except:
        printusertext('ERROR 07: Unable to open file "%s"' % p_filename)
        sys.exit(2)
        
    for line in f:
        stripped = line.strip()
        #drop blank lines
        if len(stripped) > 0:
            #drop comments
            if stripped[0] != '#':
                if   stripped == '[GROUPS]' :
                    section = 'grp'
                elif stripped == '[OPTIONS]':
                    section = 'opt'
                elif section == 'grp':
                    #groups' parsing logic goes here
                    splitline = stripped.split('=')
                    if len(splitline) < 2:
                        printusertext('ERROR 08: Invalid config line in file "%s": "%s"' % (p_filename, stripped))
                        sys.exit(2)
                    elif splitline[0].strip() == 'groupname':
                        if len(groupstr) > 0:
                            groupstr += ';'
                        groupstr += splitline[1].strip() + '='
                    #check only last chars of subnet/vlan label to allow for @ modifiers
                    elif splitline[0].strip()[-6:] == 'subnet':
                        if len(groupstr) > 0 and groupstr[-1:] != '=':
                            groupstr += ','
                        if len(splitline[0].strip()) > 6:
                            groupstr += splitline[0].strip() + ' '
                        groupstr += 'sub:' + splitline[1].strip()
                    elif splitline[0].strip()[-8:] == 'vlanname' or splitline[0].strip()[-6:] == 'vlanid' or splitline[0].strip()[-5:] == 'vname' or splitline[0].strip()[-3:] == 'vid':
                        if len(groupstr) > 0 and groupstr[-1:] != '=':
                            groupstr += ','
                        groupstr += splitline[0].strip() + ':' + splitline[1].strip()
                                        
                elif section == 'opt':
                    #options' parsing logic goes here
                    
                    splitline = stripped.split('=')
                    if len(splitline) < 2:
                        printusertext('ERROR 09: Invalid config line in file "%s": "%s"' % (p_filename, stripped))
                        sys.exit(2)
                    elif splitline[0].strip() == 'database':
                        opt.dbfile      = splitline[1].strip()
                    elif splitline[0].strip() == 'filter':
                        opt.rawfilter   = splitline[1].strip()
    
    f.close()
    
    opt.rawgroups = groupstr
                    
    return(opt)
    
    
def decodegroups(p_groupstr, p_dbfile):
    #converts a groups' definition string into an object structure
        
    grp = []
    gcount = 0
    
    splitstr = p_groupstr.split(';')
    for block in splitstr:
        grp.append(c_groupdata())
        scount = 0 # subnet count in this group
        splitblock = block.split('=')
        grp[gcount].name = splitblock[0].strip()
        grp[gcount].id = str(gcount)
        if len(splitblock) > 1:
            payload = splitblock[1].split(',')
        else:
            printusertext('ERROR 10: Invalid group definition "%s"' % block.strip())
            sys.exit(2)
        for net in payload:
            grp[gcount].subnets.append(c_subnetdata())
            rest = net.strip()
            flag_gotmod = False
            prevcursor = 0
            rcursor = 0
            rcursor = rest.find('@')
            flag_gotmod = rcursor != -1
            flag_gotsubnet = True
            colonptr = rest.rfind(':')
            if rest[colonptr-6:colonptr]    == 'vlanid':
                grp[gcount].subnets[scount].vid = rest[colonptr+1:].strip()
                rest = rest[:colonptr-6]
                #check to see if script read anything other than blank space
                flag_gotsubnet = len(grp[gcount].subnets[scount].vid) > 0 
            elif rest[colonptr-3:colonptr]  == 'vid':
                grp[gcount].subnets[scount].vid = rest[colonptr+1:].strip()
                rest = rest[:colonptr-3]
                flag_gotsubnet = len(grp[gcount].subnets[scount].vid) > 0
            elif rest[colonptr-8:colonptr]  == 'vlanname':
                grp[gcount].subnets[scount].vname = rest[colonptr+1:].strip()
                rest = rest[:colonptr-8]
                flag_gotsubnet = len(grp[gcount].subnets[scount].vname) > 0
            elif rest[colonptr-5:colonptr]  == 'vname':
                grp[gcount].subnets[scount].vname = rest[colonptr+1:].strip()
                rest = rest[:colonptr-5]
                flag_gotsubnet = len(grp[gcount].subnets[scount].vname) > 0
            elif rest[colonptr-3:colonptr]  == 'sub':
                grp[gcount].subnets[scount].subnet = rest[colonptr+1:].strip()
                rest = rest[:colonptr-3]
                flag_gotsubnet = len(grp[gcount].subnets[scount].subnet) > 0
            else:
                flag_gotsubnet = False
            
            if not flag_gotsubnet:
                printusertext('ERROR 11: Invalid subnet definition "%s"' % net.strip())
                sys.exit(2)
            
            while flag_gotmod:
                prevcursor = rcursor
                rcursor = rest[1:].find('@')
                if rcursor > -1:
                    smod = rest[1:rcursor+1].split(':')               
                else:
                    smod = rest[1:].split(':')
                    flag_gotmod = False
                    
                flag_modparsefail = False    
                if len(smod) > 1:
                    modlabel = smod[0].strip()
                    if modlabel == 'org':
                        if grp[gcount].subnets[scount].orgname == '':
                            grp[gcount].subnets[scount].orgname = smod[1].strip()
                        else:
                            flag_modparsefail = True
                    elif modlabel == 'net':
                        if grp[gcount].subnets[scount].netname == '':
                            grp[gcount].subnets[scount].netname = smod[1].strip()
                        else:
                            flag_modparsefail = True
                    elif modlabel == 'tag':
                        if grp[gcount].subnets[scount].nettag == '':
                            grp[gcount].subnets[scount].nettag  = smod[1].strip()
                        else:
                            flag_modparsefail = True
                    else:
                        flag_modparsefail = True
                if flag_modparsefail:
                    printusertext('ERROR 12: Invalid subnet definition %s' % net.strip())
                    sys.exit(2)
                rest = rest[rcursor+1:].strip()
                                 
            scount += 1
        gcount += 1
        
    #if the function made it through here, it is safe to say that the group string is clean,
    #so it can be chopped up and stored in the database
    try:
        db = sqlite3.connect(p_dbfile)
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS 
                groups(id INTEGER PRIMARY KEY, groupid INTEGER, groupname TEXT, subnets TEXT)''')
        db.commit()
        cursor.execute('''SELECT groupid FROM groups''')
        data = cursor.fetchall()
        if len(data) == 0:
            for i in range (0, len(grp)):
                splitgroup = splitstr[i].split('=')
                cursor.execute( '''INSERT INTO groups(groupid, groupname, subnets) 
                    VALUES(?,?,?)''', ( i,splitgroup[0].strip(),splitgroup[1].strip() ) )
            db.commit()
        db.close()
    except:
        printusertext('ERROR 13: Unable to connect to database file "%s"' % p_dbfile)
        sys.exit(2)
        
    return (grp)
        
    
def buildorgstructure(p_apikey, p_filters):
    #builds master object where all org, net, device and client data will be read
    orgs = []
     
    printusertext('INFO: Retrieving organization info')
        
    #compile list of organizations to be processed
    orgjson = getorglist(p_apikey)
    if orgjson[0]['id'] == 'null':
        printusertext('ERROR 14: Unable to retrieve org list')
        sys.exit(2)
            
    i = 0
    for record in orgjson:
        if p_filters.org == '' or record['name'] == p_filters.org:
            orgs.append(c_organizationdata())
            orgs[i].name = record['name']
            orgs[i].id   = record['id']
            i += 1
        
    #get shard host/FQDN where destination org is stored
    #this call sometimes fails. implementing a try-verify-wait-repeat loop
    MAX_SHARD_RESOLVE_TRIES = 10
    for record in orgs:
        flag_unabletoresolveshard = True
        for i in range (0, MAX_SHARD_RESOLVE_TRIES):
            shardhost = getshardhost(p_apikey, record.id)
            if shardhost == 'null':
                time.sleep(API_EXEC_DELAY*(i+1))
            else:
                flag_unabletoresolveshard = False
                break
        if flag_unabletoresolveshard:
            printusertext('ERROR 15: Unable to read data for org "%s"' % record.name)
            sys.exit(2)
        else:
            record.shardhost = shardhost 
    
    #compile list of networks and devices to be processed
    for org in orgs:
        netcount = 0
        netbuffer = getnwlist(p_apikey, org.shardhost, org.id)
        if len(netbuffer) > 0:
            if netbuffer[0]['id'] != 'null':
                for net in netbuffer:
                    if p_filters.netname == '' or p_filters.netname == net['name']:
                        if p_filters.nettag == '' or net['tags'].find(p_filters.nettag) > -1:
                            org.nets.append(c_networkdata())
                            org.nets[netcount].name = net['name']
                            org.nets[netcount].id   = net['id']
                            org.nets[netcount].tags = net['tags']
                            
                            devcount = 0
                            devbuffer = getdevicelist(p_apikey, org.shardhost, net['id'])
                            if len(devbuffer) > 0:
                                if devbuffer[0]['serial'] != 'null':
                                    for dev in devbuffer:
                                        flag_matchdevtype = False
                                        for dtype in p_filters.devtype:
                                            if dev['model'][:len(dtype)] == dtype:
                                                flag_matchdevtype = True
                                                break
                                        if flag_matchdevtype:                    
                                            #match devtag. tags might not exist
                                            flag_passdevtagtest = False
                                            if p_filters.devtag == '': #if no devtag filter, nothing to check
                                                flag_passdevtagtest = True
                                            elif 'tags' in dev: #avoid invalid reference crash
                                                if dev['tags'].find(p_filters.devtag) > -1:
                                                    flag_passdevtagtest = True
                                            #(else fail test)
                                                    
                                            if flag_passdevtagtest:
                                                org.nets[netcount].devs.append(c_devicedata())
                                                if not dev['name'] is None:
                                                    org.nets[netcount].devs[devcount].name   = dev['name']
                                                org.nets[netcount].devs[devcount].serial = dev['serial']
                                                if 'tags' in dev:
                                                    org.nets[netcount].devs[devcount].tags   = dev['tags']
                                                devcount += 1
                                else:
                                    printusertext('WARNING: Unable to read device data for net "%s"' % net['name'])
                            else:
                                printusertext('INFO: Network "%s" contains no devices' % net['name'])
                                        
                            netcount += 1  
            else:
                printusertext('WARNING: Unable to read network data for org "%s"' % org.name)
        else:
            printusertext('INFO: Organization "%s" contains no networks' % org.name)
            
    #remove orgs and nets that contain no devices
    cleanorgs = []
    orgcount = 0
    for org in orgs:
        netcount = 0
        flag_neworg = True
        for net in org.nets:
            devcount = 0
            flag_newnet = True
            for dev in net.devs:
                if flag_newnet:
                    if flag_neworg:
                        cleanorgs.append(c_organizationdata())
                        cleanorgs[orgcount].name        = org.name
                        cleanorgs[orgcount].id          = org.id
                        cleanorgs[orgcount].shardhost   = org.shardhost
                        orgcount += 1
                        flag_neworg = False
                    cleanorgs[orgcount-1].nets.append(c_networkdata())
                    cleanorgs[orgcount-1].nets[netcount].name = net.name
                    cleanorgs[orgcount-1].nets[netcount].id   = net.id
                    cleanorgs[orgcount-1].nets[netcount].tags = net.tags
                    netcount += 1
                    flag_newnet = False
                cleanorgs[orgcount-1].nets[netcount-1].devs.append(c_devicedata())
                cleanorgs[orgcount-1].nets[netcount-1].devs[devcount].name   = dev.name
                cleanorgs[orgcount-1].nets[netcount-1].devs[devcount].serial = dev.serial
                cleanorgs[orgcount-1].nets[netcount-1].devs[devcount].tags   = dev.tags
                devcount += 1            
                        
    return (cleanorgs)
    
    
def decodefilters(p_filterstr):
    #extract individual filter components from raw filter string
    
    output = c_filterdata()
    
    splitstr = p_filterstr.split(',')
    
    try:
        for item in splitstr:
            splititem = item.split(':')
            if len(splititem) > 1:
                label = splititem[0].strip().lower()
                if label == 'org':
                    if output.org == '':
                        output.org = splititem[1].strip()
                    else:
                        raise ValueError('org')
                elif label == 'net':
                    if output.netname == '':
                        output.netname = splititem[1].strip()
                    else:
                        raise ValueError('net')
                elif label == 'tag':
                    if output.nettag == '':
                        output.nettag = splititem[1].strip()
                    else:
                        raise ValueError('tag')
                elif label == 'dtype':
                    if len(output.devtype) == 0:
                        value = splititem[1].strip().lower()
                        if value == 'mr':
                            output.devtype.append('MR')
                        if value == 'ms':
                            output.devtype.append('MS')
                        if value == 'mx':
                            output.devtype.append('MX')
                            output.devtype.append('Z')
                        if value == 'all':
                            output.devtype.append('MR')
                            output.devtype.append('MS')
                            output.devtype.append('MX')
                            output.devtype.append('Z')
                    else:
                        raise ValueError('dtype')
                elif label == 'dtag':
                    if output.devtag == '':
                        output.devtag = splititem[1].strip()
                    else:
                        raise ValueError('dtag')
                        
            else:
                raise ValueError('label')
    except:
        printusertext('ERROR 16: Invalid filter combination "%s"' % p_filterstr)
        sys.exit(2)
        
    if len(output.devtype) == 0:
        output.devtype.append('MX')
        output.devtype.append('Z')
           
    return(output)    
    

def cmdsyncdatabase(p_apikey, p_orgs, p_dbfile):
    #pulls VLAN usage data from Dashboard to local SQLite database
    
    printusertext('INFO: Starting database sync. Please be patient')
    
    #create network ids to names mapping table if needed
    try:
        db = sqlite3.connect(p_dbfile)
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS 
                networks(id INTEGER PRIMARY KEY, netid TEXT, netname TEXT, netorgid TEXT)''')
        cursor.execute('''CREATE TABLE IF NOT EXISTS 
                organizations(id INTEGER PRIMARY KEY, orgid TEXT, orgname TEXT)''')
        db.commit()
    except:
        printusertext('ERROR 17: Unable to connect to database file "%s"' % p_dbfile)
        sys.exit(2)
                
    for org in p_orgs:
        printusertext('INFO: Processing organization "%s"' % org.name)
        try:
            cursor.execute('''SELECT orgid FROM organizations WHERE orgid=?''', (org.id,))
            data = cursor.fetchall()
            if len(data) == 0:
                cursor.execute('''INSERT INTO organizations(orgid, orgname) VALUES(?,?)''', (org.id,org.name))
                db.commit()
        except:
            printusertext('ERROR 18: Unable to connect to database file "%s"' % p_dbfile)
            sys.exit(2)
        
        for net in org.nets:
            printusertext('INFO: Processing network "%s"...' % net.name)
            #make sure network name to id mapping and data table exist
            try:
                cursor.execute('''SELECT netid FROM networks WHERE netid=?''', (net.id,))
                data = cursor.fetchall()
                if len(data) == 0:
                    cursor.execute('''CREATE TABLE IF NOT EXISTS 
                        data_''' + net.id + '''(id INTEGER PRIMARY KEY, date TEXT, groupid TEXT, up TEXT, down TEXT)''')
                    db.commit()
                    cursor.execute('''INSERT INTO 
                        networks(netid, netname, netorgid) VALUES(?,?,?)''', (net.id,net.name,org.id))
                    db.commit()
            except:
                printusertext('ERROR 19: Unable to connect to database file "%s"' % p_dbfile)
                sys.exit(2)
                                   
            today = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time(0,0,0))
            max_past_date = today - datetime.timedelta(days=29)
                
            #find newest data entry
            try:
                cursor.execute('''SELECT date FROM data_''' + net.id + ''' ORDER BY date DESC''')
                data = cursor.fetchone()
                if data is None:    
                    newestdate = max_past_date
                else:
                    newestdate = datetime.datetime.strptime(data[0], DATE_DB_FORMAT)
                    
                    if (newestdate < max_past_date):
                        newestdate = max_past_date
                    
            except: 
                printusertext('ERROR 20: Unable to connect to database file "%s"' % p_dbfile)
                sys.exit(2)   
            
            dcount = (today - newestdate).days #cannot be more than 29 days and contains no time
            
            for group in net.groups:
                for i in range(0,dcount):
                    group.dbuffer.append(0.0)
                    group.ubuffer.append(0.0)
                  
            if dcount > 1:
                for dev in net.devs:
                    #preload first buffers with client usage data to simplify main loop
                    startdate   = today - datetime.timedelta(days=dcount-1)
                    merakirequestthrottler()             
                    dstart  = int((datetime.datetime.now()-startdate).total_seconds())  
                    clientsafter = getclientlist(p_apikey, org.shardhost, dev.serial, str(dstart))                  
                    for client in clientsafter:
                        flag_gotmatch = False
                        for group in net.groups:
                            for subnet in group.subnets:
                                if (subnet.subnet != '' and ipaddress.IPv4Address(client['ip']) in ipaddress.IPv4Network(subnet.subnet)) or (subnet.vid != '' and (client['vlan'] == int(subnet.vid))):
                                    group.dbuffer[0] += client['usage']['sent'] #values returned by API are reverse
                                    group.ubuffer[0] += client['usage']['recv']
                                    flag_gotmatch = True
                                    break
                            if flag_gotmatch:
                                break 
                    
                    #main loop: for every day: get client data and add it up. more processing later
                    for i in range(1, dcount):
                        startdate   = today - datetime.timedelta(days=dcount-i)
                        merakirequestthrottler()           
                        dend  = int((datetime.datetime.now()-startdate).total_seconds()) - 86400
                        clientsafter = getclientlist(p_apikey, org.shardhost, dev.serial, str(dend))
                                                          
                        for client in clientsafter:
                            flag_gotmatch = False
                            for group in net.groups:
                                for subnet in group.subnets:
                                    if (subnet.subnet != '' and ipaddress.IPv4Address(client['ip']) in ipaddress.IPv4Network(subnet.subnet)) or (subnet.vid != '' and (client['vlan'] == int(subnet.vid))):
                                        group.dbuffer[i] += client['usage']['sent'] #values returned by API are reverse
                                        group.ubuffer[i] += client['usage']['recv']
                                        flag_gotmatch = True
                                        break
                                if flag_gotmatch:
                                    break                   
                #end "for dev in net.devs"
                
                #calculate daily group usage and write to database
                for i in range (1, dcount):
                    for group in net.groups:
                        try:
                            cursor.execute('''INSERT INTO data_''' + net.id + '''(date, groupid, up, down) 
                                VALUES(?,?,?,?)''', ((today - datetime.timedelta(days=dcount-i)).date().isoformat(), group.id, str(int(group.dbuffer[i-1]-group.dbuffer[i])), str(int(group.ubuffer[i-1]-group.ubuffer[i]))))
                        except:
                            printusertext('ERROR 21: Unable to connect to database file "%s"' % p_dbfile)
                            sys.exit(2)
                    try:
                        db.commit()
                    except:
                        printusertext('ERROR 22: Unable to connect to database file "%s"' % p_dbfile)
                        sys.exit(2)
            #end "if dcount > 0"
        #end "for net in org.nets"
    #end "for org in orgs"
                                                     
    try:
        db.close()
    except:
        printusertext('ERROR 23: Unable to connect to database file "%s"' % p_dbfile)
        sys.exit(2)
        
    printusertext('INFO: Database sync complete')
    
    return (0)    

    
def cmddatabasedump(p_opt):
    #dumps contents of database to screen
    
    if os.path.exists(p_opt.dbfile):
        try:
            db = sqlite3.connect(p_opt.dbfile)
            cursor = db.cursor()
            cursor.execute('''SELECT name FROM sqlite_master WHERE type='table' ''')
            data = cursor.fetchall()
             
            if len(data) != 0:
                for record in data:
                    print (' ---')
                    print ('TABLE %s' % record[0])
                    execstring = '''SELECT * FROM ''' + record[0]
                    if record[0][:4] == 'data':
                        execstring += ''' ORDER BY date DESC'''
                    cursor.execute(execstring)
                    recdata = cursor.fetchall()
                    for item in recdata:
                        print (item)
                    
            db.close()
        except:
            printusertext('ERROR 24: Unable to connect to database file "%s"' % p_opt.dbfile)
            sys.exit(2)
    else:
        printusertext('ERROR 25: File "%s" does not exist' % p_opt.dbfile)
        sys.exit(2)
    
    return (0)
    
   
def cmdreport(p_opt):
    #creates reports according to user preferences
    #TODO: add warning for missing data
        
    splitcmd = p_opt.rawcmd.split(':')
    firstpart = splitcmd[0].strip().lower()
    if (firstpart != 'report' and firstpart != 'report-offline') or len(splitcmd) != 2:
        printusertext('ERROR 26: Invalid command syntax "%s"' % p_opt.rawcmd)
        sys.exit(2)
        
    #parse time definition parameters and set start and end dates accordingly    
        
    timedef = splitcmd[1].strip().lower()
    
    if timedef == 'last-week':
        
        todaydate = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time(0,0,0))
        weekdaytoday = todaydate.date().weekday()
        #last and first day of previous week
        enddate      = (todaydate - datetime.timedelta(days=weekdaytoday+1) )
        startdate    = enddate - datetime.timedelta(6)       
        
    
    elif timedef == 'last-month':
        
        todaydate = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time(0,0,0))
        #last and first day of previous month
        enddate     = todaydate - datetime.timedelta(days=int(todaydate.strftime('%d')))
        startdate   = enddate - datetime.timedelta(days=int(enddate.strftime('%d'))-1)
    
    else:
        dates = timedef.split('to')
        if len(dates) == 2:
            try:
                date1 = datetime.datetime.strptime(dates[0].strip(), DATE_USER_FORMAT)
                date2 = datetime.datetime.strptime(dates[1].strip(), DATE_USER_FORMAT)
            except:
                printusertext('ERROR 27: Invalid time range definition "%s"' % timedef)
                sys.exit(2)
                            
            if date1 < date2:
                startdate   = date1
                enddate     = date2
            else:
                startdate   = date2
                enddate     = date1
                  
        elif len(dates) == 1:
            # "-c report:<integer>"
            try:
                dayscount = int(timedef.strip())
            except:
                printusertext('ERROR 28: Invalid time range definition "%s"' % timedef)
                sys.exit(2)
        
            todaydate   = datetime.datetime.combine(datetime.datetime.now().date(), datetime.time(0,0,0))
            enddate     = todaydate - datetime.timedelta(days=1)
            startdate   = todaydate - datetime.timedelta(days=dayscount)
                    
        else:
            printusertext('ERROR 29: Invalid time range definition "%s"' % timedef)
            sys.exit(2)
        
    if os.path.exists(p_opt.dbfile):
    
        #connect to database and extract data
        
        try:
            db = sqlite3.connect(p_opt.dbfile)
            cursor  = db.cursor()
            cursor.execute('''SELECT netid, netname, netorgid, orgid, orgname FROM 
                networks, organizations 
                WHERE netorgid = orgid 
                ORDER BY orgname, netname ASC''')
            nets    = cursor.fetchall()
            cursor.execute('''SELECT groupid, groupname, subnets FROM groups ORDER BY groupid ASC''')
            groups  = cursor.fetchall()
        except:
            printusertext('ERROR 30: Unable to connect to database file "%s"' % p_opt.dbfile)
            sys.exit(2)
           
        if len(nets) > 0 and len(groups) > 0:
        
            netgroupupdown = []
            
            for net in nets:
                netgroupupdown.append(c_networkdata())
                lastnet = len(netgroupupdown) - 1
                netgroupupdown[lastnet].id      = net[0]
                netgroupupdown[lastnet].name    = net[1]
                netgroupupdown[lastnet].orgid   = net[3]
                netgroupupdown[lastnet].orgname = net[4]
                for group in groups:
                    netgroupupdown[lastnet].groups.append(c_groupdata())
                    lastgrp = len(netgroupupdown[lastnet].groups)-1
                    netgroupupdown[lastnet].groups[lastgrp].id   = group[0]
                    netgroupupdown[lastnet].groups[lastgrp].name = group[1]
                    netgroupupdown[lastnet].groups[lastgrp].dbuffer.append(0)
                    netgroupupdown[lastnet].groups[lastgrp].ubuffer.append(0)    

                    try:
                        cursor.execute('''SELECT date, groupid, up, down FROM data_''' + net[0] + ''' 
                            WHERE date >= ? AND date <= ? AND groupid = ? 
                            ORDER BY date ASC''', (startdate.date().isoformat(), enddate.date().isoformat(), netgroupupdown[lastnet].groups[lastgrp].id))
                        data = cursor.fetchall()
                    except:
                        printusertext('ERROR 31: Unable to connect to database file "%s"' % p_opt.dbfile)
                        sys.exit(2)
                        
                    for line in data:                        
                        netgroupupdown[lastnet].groups[lastgrp].dbuffer[0] += int(line[2])
                        netgroupupdown[lastnet].groups[lastgrp].ubuffer[0] += int(line[3])
                        netgroupupdown[lastnet].totaldown += int(line[2])
                        netgroupupdown[lastnet].totalup   += int(line[3])  
                                         
            #render results    
            
            reportstr  = '' #plaintext version of report
            reporthtml = '<html><head></head><body>' #HTML version of report
            prevorgid  = 'null'
            for net in netgroupupdown:
                if net.orgid != prevorgid:
                    if len(reportstr) == 0:
                        #TODO: CHANGE TO USE DATE_USER_FORMAT GLOBAL VAR
                        reportstr  += '\r\nUsage report: %s to %s\r\n' % (startdate.date().isoformat(), enddate.date().isoformat())
                        reporthtml += '<h1>Usage report: %s to %s</h1>' % (startdate.date().isoformat(), enddate.date().isoformat())
                        for group in groups:
                            reportstr  += 'Group "%s": %s\r\n' % (group[1], group[2])
                            reporthtml += '<p>Group "%s": %s</p>' % (group[1], group[2])
                    reportstr  += '\r\n###\r\n\r\nOrganization: "%s"\r\n' % net.orgname
                    reporthtml += '<br><br><h2>Organization: "%s"</h3>' % net.orgname
                    prevorgid = net.orgid
                reportstr  += '\r\nNetwork: "%s"\r\n' % net.name
                reportstr  += 'Group name                     up kB       up %         down kB     down %        total kB    total %\r\n'
                reporthtml += '<h3>Network: "%s"</h3>' % net.name
                reporthtml += '<table><tr><td style="min-width:100px">Group name</td><td style="min-width:60px">up kB</td><td style="min-width:60px">up %</td><td style="min-width:60px">down kB</td><td style="min-width:60px">down %</td><td style="min-width:60px">total kB</td><td style="min-width:60px">total %</td></tr>'
                
                for group in net.groups:
                    
                    if net.totaldown == 0:
                        percentdown = 0
                    else:
                        percentdown = (group.dbuffer[0]/net.totaldown)*100
                    if net.totalup   == 0:
                        percentup   = 0
                    else:
                        percentup   = (group.ubuffer[0]/net.totalup)*100
                    grpcombinedkb = group.dbuffer[0] + group.ubuffer[0]
                    netcombinedkb = net.totaldown + net.totalup
                    if netcombinedkb == 0:
                        grpcombinedprc = 0
                    else:
                        grpcombinedprc = (grpcombinedkb/netcombinedkb)*100
                    reportstr  += '%-20s %15d %10.2f %15d %10.2f %15d %10.2f\r\n' % (group.name, group.ubuffer[0], percentup, group.dbuffer[0], percentdown, grpcombinedkb, grpcombinedprc)
                    reporthtml += '<tr><td>%-20s</td><td>%15d</td><td>%10.2f</td><td>%15d</td><td>%10.2f</td><td>%15d</td><td>%10.2f</td></tr>' % (group.name, group.ubuffer[0], percentup, group.dbuffer[0], percentdown, grpcombinedkb, grpcombinedprc)
                reporthtml += '</table>'
            reporthtml += '</body>'   
                    
            if p_opt.sendemail:
                # me == my email address
                # you == recipient's email address
                me       = p_opt.emailuser
                you      = p_opt.emailrecp
                password = p_opt.emailpass

                # Create message container - the correct MIME type is multipart/alternative.
                msg = MIMEMultipart('alternative')
                msg['Subject'] = "Subject: Network usage report [%s to %s]" % (startdate.date().isoformat(), enddate.date().isoformat())
                msg['From'] = me
                msg['To'] = you
            
                # Record the MIME types of both parts - text/plain and text/html.
                part1 = MIMEText(reportstr, 'plain')
                part2 = MIMEText(reporthtml, 'html')
                
                # Attach parts into message container.
                # According to RFC 2046, the last part of a multipart message, in this case
                # the HTML message, is best and preferred.
                msg.attach(part1)
                msg.attach(part2)
            
                try:
                    server = smtplib.SMTP(p_opt.emailsrvr)
                    server.ehlo()
                    server.starttls()
                    server.login(me,password)
                    server.sendmail(me, you, msg.as_string())
                    server.quit()
                except:
                    printusertext('ERROR 32: Unable to send email')
                    sys.exit(2)
                printusertext('INFO: Email sent to %s' % you)
            else:
                print(reportstr)

        try:
            db.close()
        except:
            printusertext('ERROR 33: Unable to connect to database file "%s"' % p_opt.dbfile)
            sys.exit(2)       
        
    else:
        printusertext('ERROR 34: File "%s" does not exist' % p_opt.dbfile)
        sys.exit(2)

    return (0)
    
    
def main(argv):
    printusertext('INFO: Script started at %s' % datetime.datetime.now())
    
    #python usagestats.py -k <key> [-d <database> -c <command> -i <initfile> -g <groups> -f <filter>]

    #initialize variables for command line arguments
    arg_apikey      = ''
    arg_dbfile      = ''
    arg_cmd         = ''
    arg_initfile    = ''
    arg_groups      = ''
    arg_filter      = ''
    arg_user        = ''
    arg_pass        = ''
    arg_recipient   = ''
    arg_server      = ''
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:d:c:i:g:f:u:p:r:s:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-d':
            arg_dbfile  = arg
        elif opt == '-c':
            arg_cmd     = arg
        elif opt == '-i':
            arg_initfile= arg
        elif opt == '-g':
            arg_groups  = arg
        elif opt == '-f':
            arg_filter  = arg
        elif opt == '-u':
            arg_user    = arg
        elif opt == '-p':
            arg_pass    = arg
        elif opt == '-r':
            arg_recipient = arg
        elif opt == '-s':
            arg_server  = arg
                      
    #check if all required parameters have been given
    if arg_apikey == '':
        printhelp()
        sys.exit(2)
        
    if arg_dbfile == '' and arg_initfile == '':
        printusertext('ERROR 35: Either a database or an init config file must be defined')
        sys.exit(2)
        
    #make sure that either all email parameters are given, or none:
    emailparams = 0
    if arg_user     != '':
        emailparams += 1
    if arg_pass     != '':
        emailparams += 1
    if arg_recipient!= '':
        emailparams += 1
    if 0 < emailparams < 3:
        printusertext('ERROR 36: -u <user> -p <pass> -r <recipient> must be given to send email')
        sys.exit(2)
             
    #start collecting user option information
    opt = c_optiondata()
        
    #check if dbfile exists and load config from it if possible
    opt.dbfile = arg_dbfile
    if os.path.exists(opt.dbfile):
        try:
            db = sqlite3.connect(opt.dbfile)
            cursor = db.cursor()
            if arg_cmd.strip().lower() == 'dbreconfigure':
                cursor.execute('''DROP TABLE IF EXISTS config''')
                cursor.execute('''DROP TABLE IF EXISTS groups''')
                db.commit()
            else:
                cursor.execute('''SELECT groups, filter, dbversion FROM config ''')
                for row in cursor:
                    if row[2] != DB_VERSION:
                        printusertext('ERROR 37: Database version not compatible. Please start a new database' % opt.dbfile)
                        sys.exit(2)
                    opt.rawgroups = row[0]
                    opt.rawfilter = row[1]
            db.close()
        except:
            printusertext('ERROR 38: File "%s" is not a compatible SQLite database' % opt.dbfile)
            sys.exit(2)
    else:
        printusertext('INFO: Creating new database file "%s"' % arg_dbfile)
    
    #load init config file
    initopt = c_optiondata()
    if os.path.exists(arg_initfile):
        initopt = loadinitfile(arg_initfile)
        
    #fill db config blanks from initfile
    for key in opt.__dict__.keys():
        if opt.__dict__[key] == '':
            opt.__dict__[key] = initopt.__dict__[key]
    
    #check if dbfile info was loaded from init file
    if opt.dbfile == '':
        printusertext('ERROR 39: Database file must be defined in init file of command line argument')
        sys.exit(2)
        
        
    #if no config loaded from dbfile of init config file, load config from CLI arguments   
    #these should only be processed if no config existed in db or init
    if opt.rawgroups == '':
        opt.rawgroups = arg_groups
    if opt.rawfilter == '':
        opt.rawfilter = arg_filter   
    #these are report time options
    opt.rawcmd        = arg_cmd
    opt.emailuser     = arg_user 
    opt.emailpass     = arg_pass 
    opt.emailrecp     = arg_recipient 
    opt.emailsrvr     = arg_server 
    if emailparams == 3:    #this was set way back, towards the beginning of main()
        opt.sendemail = True
    
        
    #if no config from options has been loaded from db, init file, or cli arguments, set defaults
    #NOTE: EDIT THESE LINES TO MODIFY DEFAULT BEHAVIOR
    if opt.rawcmd       ==  '':
        opt.rawcmd      =   'report:last-week'
    if opt.rawfilter    ==  '':
        opt.rawfilter   =   'dtype:mx'
    if opt.rawgroups    ==  '':
        opt.rawgroups   =   'Overall=sub:0.0.0.0/0'
    if opt.emailsrvr    ==  '':
        opt.emailsrvr   =   'smtp.gmail.com:587'
    
    #connect to db and write configuration if needed
    try:
        db = sqlite3.connect(opt.dbfile)
        cursor = db.cursor()
        cursor.execute('''CREATE TABLE IF NOT EXISTS 
                config(id INTEGER PRIMARY KEY, dbversion INTEGER, groups TEXT, filter TEXT)''')
        db.commit()
        cursor.execute('''SELECT groups FROM config ''')
        data = cursor.fetchall()
        if len(data) == 0:
            cursor.execute('''INSERT INTO config(dbversion, groups, filter)
                  VALUES(''' + str(DB_VERSION) + ''',?,?)''', (opt.rawgroups,opt.rawfilter))
            db.commit()
        cursor.execute('''SELECT * FROM config ''')
        data = cursor.fetchall()        
        if len(data) == 0:
            raise ValueError ('no write')
        db.close()
    except:
        printusertext('ERROR 40: Unable to connect to database file "%s"' % opt.dbfile)
        sys.exit(2)
        
    
    #if command is dbdump, dump database without connecting to Dashboard       
    if opt.rawcmd == 'dbdump':
    
        cmddatabasedump(opt)
        
    elif opt.rawcmd == 'dbreconfigure':
    
        groups = decodegroups(opt.rawgroups, opt.dbfile)
        
    elif opt.rawcmd == 'sync' or (opt.rawcmd[:6] == 'report' and opt.rawcmd[:14] != 'report-offline'):
        
        #decode raw filter
        filters = decodefilters(opt.rawfilter)
                
        #decode raw groups
        groups = decodegroups(opt.rawgroups, opt.dbfile)
        
        #contact cloud and build orgs/nets structure
        orgs = buildorgstructure(arg_apikey, filters)
                                
        #section start: apply groups to org structure
        for org in orgs:
            for net in org.nets:
                gcount = 0
                flag_resolve_vlans = False
                for group in groups:
                    scount = 0
                    net.groups.append(c_groupdata())
                    net.groups[gcount].id   = group.id
                    net.groups[gcount].name = group.name
                    for sub in group.subnets:
                        if (sub.orgname == '' and sub.netname == '' and sub.nettag == '') or (sub.orgname != '' and sub.orgname == org.name) or (sub.netname != '' and sub.netname == net.name) or (sub.nettag  != '' and net.tags.find(sub.nettag) > -1):   
                            net.groups[gcount].subnets.append(c_subnetdata())
                            net.groups[gcount].subnets[scount] = sub
                            if net.groups[gcount].subnets[scount].subnet == '':
                                #if subnet is empty, set flag to resolve all network VLANs in one API call later
                                flag_resolve_vlans = True
                            scount += 1
                    gcount += 1
                    
                if flag_resolve_vlans:
                    
                    netvlans = getvlanlist(arg_apikey, org.shardhost, net.id)
                                        
                    flag_vlanresolvefail = False
                    if netvlans[0]['id'] != 'null':
                        for group in net.groups:
                            for sub in group.subnets:
                                flag_pendingresolve = True
                                for vlan in netvlans:
                                    if sub.vname == '' and sub.vid == '':
                                        flag_pendingresolve = False
                                        break
                                    elif (sub.vname != '' and sub.vname == vlan['name']) or (sub.vid != '' and sub.vid == vlan['id']):
                                        sub.subnet = vlan['subnet']
                                        flag_pendingresolve = False
                                        break
                                if flag_pendingresolve:
                                    printusertext('WARNING: Unable to resolve VLAN "%s%s" for network "%s"' % (sub.vname, sub.vid, net.name))
                    else:
                        printusertext('WARNING: Unable to read MX VLAN mappings for network "%s"' % net.name)
        #section end: apply groups to org structure               
                        
                    
        #execute sync
        cmdsyncdatabase(arg_apikey, orgs, opt.dbfile)
        
     
    #if command == report, execute report
    if opt.rawcmd[:6] == 'report':
        cmdreport(opt)
    
        
    printusertext('INFO: Reached end of script at %s' % datetime.datetime.now())
            
if __name__ == '__main__':
    main(sys.argv[1:])