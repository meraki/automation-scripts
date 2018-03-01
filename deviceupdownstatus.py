# This is a script to print a list of all devices in a organization's inventory and their up/down status.
#  The script will not return up/down status for MV security cameras, as this was not supported at time of writing.
#
# To run the script, enter:
#  python deviceupdownstatus.py -k <api key> -o <org name> [-a <snmp auth key> -p <snmp priv key>]
#
# Mandatory arguments:
#  -k <api key>         : Your Meraki Dashboard API key
#  -o <org name>        : Your Dashboard Organization name
# Optional arguments to use SNMPv3:
#  -a <snmp auth key>   : SNMPv3 authorization key. Required for SNMPv3
#  -p <snmp priv key>   : SNMPv3 privacy key. Required for SNMPv3
# 
# Example:
#  python deviceupdownstatus.py -k 1234 -o "Meraki Inc" -a authpass123 -p privpass123
#
# This script was developed using Python 3.6.4. You will need the Requests and PySNMP modules to run it. You can install
#  these modules via pip:
#  pip install requests
#  pip install pysnmp
#
# More info on these modules:
#   http://python-requests.org
#   http://pysnmp.sourceforge.net
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2018-03-01

import sys, getopt, requests, json, time
from pysnmp.hlapi import *
from datetime import datetime

#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

#connect and read timeouts for the Requests module
REQUESTS_CONNECT_TIMEOUT = 30
REQUESTS_READ_TIMEOUT    = 30

#used by merakirequestthrottler(). DO NOT MODIFY
LAST_MERAKI_REQUEST = datetime.now() 

class c_serialstatus:
    def __init__(self):
        self.serial     = ''
        self.status     = ''
        
class c_deviceinfo:
    def __init__(self):
        self.serial     = ''
        self.model      = ''
        self.name       = ''
        self.networkId  = ''
        self.status     = '' #this will be filled via SNMP
        
class c_snmpinfo:
    def __init__(self):
        self.host       = ''
        self.usercommunity = '' # SNMPv3 user / SNMPv2c community. Same in Meraki Dashboard
        self.v3enabled  = False
        self.v2cenabled = False
        self.authkey    = '' #not returned by API
        self.privkey    = '' #not returned by API

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)  


def printhelp():
    #prints help text

    printusertext('This is a script to print a list of all devices in a organization\'s inventory and their up/down status.')
    printusertext(' The script will not return up/down status for MV security cameras, as this was not supported at time of writing.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext(' python deviceupdownstatus.py -k <api key> -o <org name> [-a <snmp auth key> -p <snmp priv key>]')
    printusertext('')
    printusertext('Mandatory argument:s')
    printusertext(' -k <key>             : Your Meraki Dashboard API key')
    printusertext(' -o <org name>        : Your Dashboard Organization name')
    printusertext('Optional arguments to use SNMPv3:')
    printusertext(' -a <snmp auth key>   : SNMPv3 authorization key. Required for SNMPv3')
    printusertext(' -p <snmp priv key>   : SNMPv3 privacy key. Required for SNMPv3')
    printusertext('')
    printusertext('Example:')
    printusertext(' python deviceupdownstatus.py -k 1234 -o "Meraki Inc" -a authpass123 -p privpass123')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')    
    
        
def snmppolldevicestatuses (p_shardhost, p_usercommunity, p_authkey = '', p_privkey = ''):
    #returns a list of c_serialstatus objects containing serial numbers of devices returned by SNMP and their up/down status
    #note that SNMP only returns status for devices assigned to a network, not the whole inventory

    returnlist  = []
    serialslist = []
    statuslist  = []
    flag_snmpv3 = True
        
    if p_authkey == '' or p_privkey == '':
        flag_snmpv3 = False
        
    #snmp poll serials' list
    if flag_snmpv3:
        try:
            g = nextCmd(SnmpEngine(),
                UsmUserData(p_usercommunity, p_authkey, p_privkey,
                                   authProtocol=usmHMACSHAAuthProtocol,
                                   privProtocol=usmAesCfb128Protocol),
                UdpTransportTarget((p_shardhost, 16100)),
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.4.1.29671.1.1.4.1.8')),
                lexicographicMode = False,
                lookupMib = False)
        except:
            printusertext ("ERROR 01: SNMPv3 nextCmd failed")
            sys.exit(2)
    else: #using SNMPv2c
        try:
            g = nextCmd(SnmpEngine(),
                CommunityData(p_usercommunity),
                UdpTransportTarget((p_shardhost, 16100)),
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.4.1.29671.1.1.4.1.8')),
                lexicographicMode = False,
                lookupMib = False)
        except:
            printusertext ("ERROR 02: SNMPv2c nextCmd failed")
            sys.exit(2)
            
    flag_continue = True
    
    while flag_continue:
        try:
            errorIndication, errorStatus, errorIndex, varBinds = next(g)
        except StopIteration:
            flag_continue = False
        except:
            printusertext ("ERROR 03: SNMP next failed")
            sys.exit(2)
        if flag_continue:
            for vb in varBinds:
                try:
                    #mash everything to a str and grab the right characters. this works more reliably
                    crashbuffer = str(vb)[-17:-3]                                     
                    serialslist.append(crashbuffer)
                except:
                    printusertext ('WARNING: SNMP poll for serials returned no data')
            
    #snmp poll statuses' list
    if flag_snmpv3:
        try:
            g = nextCmd(SnmpEngine(),
                UsmUserData(p_usercommunity, p_authkey, p_privkey,
                                   authProtocol=usmHMACSHAAuthProtocol,
                                   privProtocol=usmAesCfb128Protocol),
                UdpTransportTarget((p_shardhost, 16100)),
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.4.1.29671.1.1.4.1.3')),
                lexicographicMode = False,
                lookupMib = False)
        except:
            printusertext ("ERROR 04: SNMPv3 nextCmd failed")
            sys.exit(2)
    else: #using SNMPv2c
        try:
            g = nextCmd(SnmpEngine(),
                CommunityData(p_usercommunity),
                UdpTransportTarget((p_shardhost, 16100)),
                ContextData(),
                ObjectType(ObjectIdentity('1.3.6.1.4.1.29671.1.1.4.1.3')),
                lexicographicMode = False,
                lookupMib = False)
        except:
            printusertext ("ERROR 05: SNMPv2c nextCmd failed")
            sys.exit(2)    
            
    flag_continue = True
    
    while flag_continue:
        try:
            errorIndication, errorStatus, errorIndex, varBinds = next(g)
        except StopIteration:
            flag_continue = False
        except:
            printusertext ("ERROR 06: SNMP next failed")
            sys.exit(2)
        if flag_continue:
            for vb in varBinds:
                try:
                    crashbuffer = vb[len(vb)-1]
                    statuslist.append(crashbuffer)
                except:
                    printusertext ('WARNING: SNMP poll for statuses returned no data')       
    
    lastitem = len(statuslist)
    for i in range (0, lastitem):
        returnlist.append(c_serialstatus())
        returnlist[i].serial = serialslist[i]
        if statuslist[i] == 1:
            returnlist[i].status = 'up'
        else:
            returnlist[i].status = 'down'
            
    return (returnlist)
    
    
def merakirequestthrottler(p_requestcount=1):
    #makes sure there is enough time between API requests to Dashboard not to hit shaper
    global LAST_MERAKI_REQUEST
    
    if (datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY*p_requestcount):
        time.sleep(API_EXEC_DELAY*p_requestcount)
    
    LAST_MERAKI_REQUEST = datetime.now()
    return   
    

def getorgid(p_apikey, p_orgname):
    #looks up org id for a specific org name
    #on failure returns 'null'
    
    merakirequestthrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 07: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_orgname:
            return record['id']
    return('null')    
    
    
def getsnmpinfo(p_apikey, p_orgid):
    #Looks up shard URL for a specific org. Use this URL instead of 'dashboard.meraki.com'
    # when making API calls with API accounts that can access multiple orgs.
    #On failure returns 'null'
        
    merakirequestthrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations/%s/snmp' % p_orgid, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        printusertext('ERROR 08: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnobject = c_snmpinfo()
    
    if r.status_code != requests.codes.ok:
        returnobject.host = 'null'
        return (returnobject)
        
    rjson = r.json()
    
    returnobject.host           = rjson['hostname']
    returnobject.v3enabled      = rjson['v3Enabled']
    returnobject.v2cenabled     = rjson['v2cEnabled']
    if rjson['v2cEnabled']:
        returnobject.usercommunity  = rjson['v2CommunityString']
    elif rjson['v3Enabled']:
        returnobject.usercommunity  = rjson['v3User']
    
    return(returnobject)
    
    
def getinventory(p_apikey, p_shardhost, p_orgid):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 09: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append(c_deviceinfo())
        returnvalue[0].serial = 'null'
        return(returnvalue)
    
    rjson = r.json()
        
    rjlen = len(rjson)
    for i in range (0, rjlen):
        returnvalue.append(c_deviceinfo())
        returnvalue[i].serial = rjson[i]['serial']
        returnvalue[i].model  = rjson[i]['model']
        if rjson[i]['networkId'] is None:
            returnvalue[i].networkId = ''
        else:
            returnvalue[i].networkId = rjson[i]['networkId']
            
    return(returnvalue)  


def getdevicename(p_apikey, p_shardhost, p_nwid, p_serial):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/networks/%s/devices/%s' % (p_shardhost, p_nwid, p_serial), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 10: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return('')
    
    rjson = r.json()
    
    if rjson['name'] is None:
        return(rjson['mac'])
              
    return(rjson['name'])    
    

def main(argv):
    #initialize variables for command line arguments
    arg_apikey      = ''
    arg_orgname     = ''
    arg_authkey     = ''
    arg_privkey     = ''
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:a:p:')
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
        elif opt == '-a':
            arg_authkey = arg
        elif opt == '-p':
            arg_privkey = arg
            
    #check if all parameters are required parameters have been given
    if arg_apikey == '':
        printhelp()
        sys.exit(2)
        
    #resolve orgid    
    orgid = getorgid(arg_apikey, arg_orgname)    
        
    #get SNMP info
    #this call sometimes fails. implementing a try-verify-wait-repeat loop
    MAX_SHARD_RESOLVE_TRIES = 10
    flag_unabletoresolveshard = True
    for i in range (0, MAX_SHARD_RESOLVE_TRIES):
        snmpinfo = getsnmpinfo(arg_apikey, orgid)
        if snmpinfo.host == 'null':
            time.sleep(API_EXEC_DELAY*(i+1))
        else:
            flag_unabletoresolveshard = False
            break
    if flag_unabletoresolveshard:
        printusertext('ERROR 11: Unable to read data for org "%s"' % record.name)
        sys.exit(2)
        
    #get device inventory
    inventory = getinventory(arg_apikey, snmpinfo.host, orgid)
    if inventory[0].serial == 'null':
        printusertext('ERROR 12: Unable to read inventory via API')
        sys.exit(2)
        
    #poll device up/down status via SNMP
    if arg_authkey != '' and arg_privkey != '':
        if snmpinfo.v3enabled:
            updownstatus = snmppolldevicestatuses(snmpinfo.host, snmpinfo.usercommunity, arg_authkey, arg_privkey)
        else:
            printusertext('ERROR 13: Unable to poll via SNMPv3 (not enabled in org)')
            sys.exit(2)
    else:
        if snmpinfo.v2cenabled:
            updownstatus = snmppolldevicestatuses(snmpinfo.host, snmpinfo.usercommunity)
        else:
            printusertext('ERROR 14: Unable to poll via SNMPv2c (not enabled in org)')
            sys.exit(2)
                               
    for device in inventory:
        if device.networkId != '':
            if device.model[:2] == 'MV':
                device.status = 'n/a' #currently SNMP does not return up/down for MV cameras
            flag_devicelocated = False
            for state in updownstatus:
                if device.serial == state.serial:
                    device.status = state.status
                    flag_devicelocated = True
                    break 
            device.name = getdevicename(arg_apikey, snmpinfo.host, device.networkId, device.serial)
        else:
            device.status = "not in use"
            
    print ('DEVICE NAME                   MODEL          SERIAL              STATUS')     
    for device in inventory:
        print('%-30s%-15s%-20s%-10s' % (device.name, device.model, device.serial, device.status))
    
    
if __name__ == '__main__':
    main(sys.argv[1:])