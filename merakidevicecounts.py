# This is a script to count device types in multiple orgs.
#
# Usage:
#  python merakidevicecounts.py -k <key> -f <file>
#
# Arguments:
#  -k <key>  : Your Meraki Dashboard API key
#  -f <file> : File with list of organizations to be counted. Use "-f /all" to count all organizations
#
# Examples:
#  python merakidevicecounts.py -k 1234 -f /all
#  python merakidevicecounts.py -k 1234 -f orglist.txt
#
# Creating an input file:
#  Use a text editor to create a text file, where organization names are listed one per line
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-10-24

import sys, getopt, requests, json, time

class c_devicedata:
    def __init__(self):
        self.serial    = ''
        self.model     = ''
#end class   

class c_organizationdata:
    def __init__(self):
        self.name      = ''
        self.id        = ''
        self.shardhost = ''
        self.devices   = []
#end class   

#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

def printhelp():
    #prints help text

    printusertext('This is a script to count device types in multiple orgs.')
    printusertext('')
    printusertext('Usage:')
    printusertext(' python merakidevicecounts.py -k <key> -f <file>')
    printusertext('')
    printusertext('Arguments:')
    printusertext(' -k <key>  : Your Meraki Dashboard API key')
    printusertext(' -f <file> : File with list of organizations to be counted. Use "-f /all" to count all organizations')
    printusertext('')
    printusertext('Examples:')
    printusertext(' python merakidevicecounts.py -k 1234 -f /all')
    printusertext(' python merakidevicecounts.py -k 1234 -f orglist.txt')
    printusertext('')
    printusertext('Creating an input file:')
    printusertext(' Use a text editor to create a text file, where organization names are listed one per line')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')
    
def getorglist(p_apikey):
    #returns the organizations' list for a specified admin
    #DEBUG unfinished untested
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 00: Unable to contact Meraki cloud')
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
        printusertext('ERROR 01: Unable to contact Meraki cloud')
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
        printusertext('ERROR 02: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
        
    rjson = r.json()
    
    return(rjson['hostname'])
    
def getnwid(p_apikey, p_shardhost, p_orgid, p_nwname):
    #looks up network id for a network name
    #on failure returns 'null'

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
        
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_nwname:
            return record['id']
    return('null') 
    
    
def getorginventory(p_apikey, p_shardhost, p_orgid):
    #returns full org inventory

    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 04: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        return(returnvalue) #return empty table
    
    rjson = r.json()
    
    return (rjson)
    
def main(argv):
    #python mxfirewallcontrol -k <key> -o <org> [-f <filter>] [-c <command>] [-m <mode>]

    #set default values for command line arguments
    arg_apikey  = ''
    arg_file    = ''
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:f:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-f':
            arg_file    = arg
                      
    #check if all parameters are required parameters have been given
    if arg_apikey == '' or arg_file == '':
        printhelp()
        sys.exit(2)
       
    #set flags
    flag_processall = False
    if arg_file == '/all':
        flag_processall = True
        
    #compile list of organizations to be processed
    orglist = []
    if flag_processall:
        orgjson = getorglist(arg_apikey)
              
        i = 0
        for record in orgjson:
            orglist.append(c_organizationdata())
            orglist[i].name = record['name']
            orglist[i].id   = record['id']
            i += 1
        
    else:
        #open input file file for reading
        try:
            f = open(arg_file, 'r')
        except:
            printusertext('ERROR 05: Unable to open file for reading')
            sys.exit(2)
        #read org names info from file
        for line in f:
            stripped = line.strip()
            if len(stripped) > 0:
                orglist.append(c_organizationdata())
                orglist[len(orglist)-1].name = stripped
                orgid = getorgid(arg_apikey, stripped)
                if orgid != 'null':
                    orglist[len(orglist)-1].id = orgid
                else:
                    printusertext('ERROR 06: Unable to resolve org ID for org name "%s"' % stripped)
                    sys.exit(2)
        f.close()
                        
    #get shard host/FQDN where destination org is stored
    #this call sometimes fails. implementing a try-verify-wait-repeat loop
    MAX_SHARD_RESOLVE_TRIES = 5
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
            printusertext('ERROR 07: Unable to read data for org "%s"' % record.name)
            sys.exit(2)
        else:
            record.shardhost = shardhost

        
    for orgrecord in orglist:
        orginventory = getorginventory(arg_apikey, orgrecord.shardhost, orgrecord.id)
        for returnitem in orginventory:
            orgrecord.devices.append(c_devicedata())
            orgrecord.devices[len(orgrecord.devices)-1].serial = returnitem['serial']
            orgrecord.devices[len(orgrecord.devices)-1].model  = returnitem['model']
        
    for item in orglist:
        print ('')
        print ('Devices in org "%s"' % item.name)
        for device in item.devices:
            print('%s %s' % (device.serial, device.model))
            
            
    
    #calculate + print device counts
    print('')
            
    total_count_mr = 0
    total_count_ms = 0
    total_count_mx = 0
    total_count_z  = 0        
            
    for item in orglist:
        count_mr = 0
        count_ms = 0
        count_mx = 0
        count_z  = 0
        print ('Device counts for org "%s"' % item.name)
        for device in item.devices:
            if device.model[:2]   == 'MR':
                count_mr += 1
            elif device.model[:2] == 'MS':
                count_ms += 1
            elif device.model[:2] == 'MX':
                count_mx += 1
            elif device.model[:1] == 'Z' :
                count_z  += 1
        total_count_mr += count_mr
        total_count_ms += count_ms
        total_count_mx += count_mx
        total_count_z  += count_z 
        print('MR: %d' % count_mr)
        print('MS: %d' % count_ms)
        print('MX: %d' % count_mx)
        print('Z : %d' % count_z)
    
    #print total device counts for all orgs
    
    print('')
    print('Total device counts for all orgs in "%s"' % arg_file)
    print('MR: %d' % total_count_mr)
    print('MS: %d' % total_count_ms)
    print('MX: %d' % total_count_mx)
    print('Z : %d' % total_count_z)
    
                
    printusertext('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])