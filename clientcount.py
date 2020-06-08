# This is a Python 3 script to count the total unique client MAC addresses connected to MR access points for 
#  an organization during the last month.
#
# Usage:
#  clientcount.py -k <api key> [-o <org name>]
#
# Parameters:
#  -k <api key>     :   Mandatory. Your Meraki Dashboard API key
#  -o <org name>    :   Optional. Name of the organization you want to process. Use keyword "/all" to explicitly
#                       specify all orgs. Default is "/all"
#
# Example:
#  clientcount.py -k 1234 -o "Big Industries Inc" 
#
# Notes:
#  * In Windows, use double quotes ("") to enter command line parameters containing spaces.
#  * This script was built for Python 3.7.1.
#  * Depending on your operating system, the command to start python can be either "python" or "python3". 
# 
# Required Python modules:
#  Requests     : http://docs.python-requests.org
#
# After installing Python, you can install these additional modules using pip with the following commands:
#  pip install requests
#
# Depending on your operating system, the command can be "pip3" instead of "pip".

import sys, getopt, requests, json, time, datetime, os, sqlite3

#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR

API_EXEC_DELAY              = 0.21 #Used in merakirequestthrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

#SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakirequestthrottler()
ARG_APIKEY                  = '' #DO NOT STATICALLY SET YOUR API KEY HERE
ARG_ORGNAME                 = '' #DO NOT STATICALLY SET YOUR ORGANIZATION NAME HERE
ORG_LIST                    = None #list of organizations, networks and MRs the used API key has access to
MAX_CLIENT_TIMESPAN         = 2592000 #maximum timespan GET clients Dashboard API call supports
        
class c_Net:
    def __init__(self):
        id          = ''
        name        = ''
        shard       = 'api.meraki.com'
        devices     = []
        
class c_Organization:
    def __init__(self):
        id          = ''
        name        = ''
        shard       = 'api.meraki.com'
        nets        = []
        
        
#SECTION: General use functions

def merakirequestthrottler():
    #makes sure there is enough time between API requests to Dashboard not to hit shaper
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return
    
def printhelp():
    print('This is a Python 3 script to count the total unique client MAC addresses connected to MR access points for')
    print(' an organization during the last month.')
    print('')
    print('Usage:')
    print(' clientcount.py -k <api key> [-o <org name>]')
    print('')
    print('Parameters:')
    print(' -k <api key>     :   Mandatory. Your Meraki Dashboard API key')
    print(' -o <org name>    :   Optional. Name of the organization you want to process. Use keyword "/all" to explicitly')
    print('                      specify all orgs. Default is "/all"')
    print('')
    print('Example:')
    print(' clientcount.py -k 1234 -o "Big Industries Inc"')
    print('')
    print('Notes:')
    print(' * In Windows, use double quotes ("") to enter command line parameters containing spaces.')
    
    
#SECTION: Meraki Dashboard API communication functions

def getInventory(p_org):
    #returns a list of all networks in an organization
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_org.shard, p_org.id), headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 06: Unable to contact Meraki cloud')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
    

def getNetworks(p_org):
    #returns a list of all networks in an organization
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_org.shard, p_org.id), headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 07: Unable to contact Meraki cloud')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())
        

def getOrgs():
    #returns the organizations' list for a specified admin, with filters applied
        
    merakirequestthrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        print('ERROR 01: Unable to contact Meraki cloud')
        return(None)
    
    if r.status_code != requests.codes.ok:
        return(None)
        
    rjson = r.json()
    orglist = []
    listlen = -1
    
    if ARG_ORGNAME.lower() == '/all':
        for org in rjson:
            orglist.append(c_Organization())
            listlen += 1
            orglist[listlen].id     = org['id']
            orglist[listlen].name   = org['name']
    else:
        for org in rjson:
            if org['name'] == ARG_ORGNAME:
                orglist.append(c_Organization())
                listlen += 1
                orglist[listlen].id     = org['id']
                orglist[listlen].name   = org['name']
    
    return(orglist)
    
    
def getShardHost(p_org):
    #quick-n-dirty patch
    return("api-mp.meraki.com")
  
    
def refreshOrgList():
    global ORG_LIST
    
    print('INFO: Starting org list refresh at %s...' % datetime.datetime.now())

    flag_firstorg = True
    orglist = getOrgs()
    
    if not orglist is None:
        for org in orglist:
            print('INFO: Processing org "%s"' % org.name)
            
            org.shard = 'api.meraki.com'
            orgshard = getShardHost(org)
            if not orgshard is None:
                org.shard = orgshard
            netlist = getNetworks(org)
            devlist = getInventory(org)
                            
            if not devlist is None and not netlist is None:
            
                db = sqlite3.connect(':memory:')
                dbcursor = db.cursor()
                dbcursor.execute('''CREATE TABLE devices (serial text, networkId text)''')
                db.commit()
                
                for device in devlist:
                    if not device['networkId'] is None:
                        if device['model'].startswith('MR'):
                            dbcursor.execute('''INSERT INTO devices VALUES (?,?)''', (device['serial'],device['networkId']))
                db.commit()   
                                                
                flag_firstnet = True
                
                for net in netlist:
                    if net['type'] != 'systems manager': #ignore systems manager nets
                        dbcursor.execute('''SELECT serial FROM devices WHERE networkId = ?''', (net['id'],))
                        
                        devicesofnet = dbcursor.fetchall()
                        
                        if len(devicesofnet) > 0: #network has MRs
                            if flag_firstnet:
                                if flag_firstorg:
                                    ORG_LIST = []
                                    lastorg = -1
                                    flag_firstorg = False
                                
                                ORG_LIST.append(org)
                                lastorg += 1
                                lastnet = -1
                                ORG_LIST[lastorg].nets = []
                                
                                flag_firstnet = False
                                
                            ORG_LIST[lastorg].nets.append(c_Net())
                            lastnet += 1
                            ORG_LIST[lastorg].nets[lastnet].id      = net['id']
                            ORG_LIST[lastorg].nets[lastnet].name    = net['name']
                            ORG_LIST[lastorg].nets[lastnet].shard   = org.shard
                            ORG_LIST[lastorg].nets[lastnet].devices = []
                            
                            for device in devicesofnet:
                                ORG_LIST[lastorg].nets[lastnet].devices.append(device[0])
                                                    
                db.close()
                
    LAST_ORGLIST_REFRESH = datetime.datetime.now()      
    print('INFO: Refresh complete at %s' % LAST_ORGLIST_REFRESH)
                     
    return None

    
def getclientlist(p_shardhost, p_serial, p_timespan):
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/devices/%s/clients?timespan=%s' % (p_shardhost, p_serial, p_timespan), headers={'X-Cisco-Meraki-API-Key': ARG_APIKEY, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 02: Unable to contact Meraki cloud')
        return(None)
        
    if r.status_code != requests.codes.ok:
        return(None)
    
    return(r.json())   

    
#SECTION: main
    
def main(argv):
    global ARG_APIKEY
    global ARG_ORGNAME
    
    #initialize command line arguments
    ARG_APIKEY      = ''
    ARG_ORGNAME     = ''
    arg_numresults  = ''
    arg_mode        = ''
    arg_filter      = ''    
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:m:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
        
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            ARG_APIKEY      = arg
        elif opt == '-o':
            ARG_ORGNAME     = arg
        elif opt == '-m':
            arg_mode        = arg
            
    #check that all mandatory arguments have been given
    if ARG_APIKEY == '':
        printhelp()
        sys.exit(2)        
            
    #set defaults for empty command line arguments
    if ARG_ORGNAME == '':
        ARG_ORGNAME = '/all'
   
    refreshOrgList()
    
    if ORG_LIST is None:
        print('ERROR 03: No organizations with MR access points for the specified API key')
        sys.exit(2) 
        
    print ('INFO: Starting client device database creation at %s...' % datetime.datetime.now())
    db = sqlite3.connect(':memory:')
    
    dbcursor = db.cursor()
    
    dbcursor.execute('''CREATE TABLE clients
             (id text, description text, dhcpHostName text, mac text, ip text, vlan text, orgid text, orgname text, netid text, netname text)''')
              
    db.commit()
    
    flag_madechanges = False
    for org in ORG_LIST:
        print ('INFO: Processing org "%s"' % org.name)
        for net in org.nets:
            print ('INFO: Processing net "%s"' % net.name)
            for dev in net.devices:
                clients = getclientlist(org.shard, dev, MAX_CLIENT_TIMESPAN)
                for client in clients:
                    dbcursor.execute('''INSERT INTO clients VALUES (?,?,?,?,?,?,?,?,?,?)''', 
                        (client['id'],
                        client['description'],
                        client['dhcpHostname'],
                        client['mac'],
                        client['ip'],
                        client['vlan'],
                        org.id,
                        org.name,
                        net.id,
                        net.name))
                    flag_madechanges = True
                    
    if flag_madechanges:
        db.commit()
        
    print ('INFO: Database creation complete at %s' % datetime.datetime.now())
   
    dbcursor.execute('''SELECT DISTINCT mac FROM clients''')
    
    retvalue = dbcursor.fetchall()
    
    print ('\nTotal unique client MAC addresses across all WLAN APs: %s\n' % len(retvalue))    
    
    #List unique MAC addresses
    #for line in retvalue:
    #    print (line[0])   
    
    db.close()
    
if __name__ == '__main__':
    main(sys.argv[1:])