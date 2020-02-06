readMe = '''
This is a script to count device types in multiple orgs.

Usage:
  python merakidevicecounts.py -k <key> -f <file>

Arguments:
  -k <key>  : Your Meraki Dashboard API key
  -f <file> : File with list of organizations to be counted. Use "-f /all" to count all organizations

Examples:
  python merakidevicecounts.py -k 1234 -f /all
  python merakidevicecounts.py -k 1234 -f orglist.txt

Creating an input file:
  Use a text editor to create a text file, where organization names are listed one per line
'''

import sys, getopt, requests, json, time, datetime

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
        self.skipMe    = False
#end class   

API_EXEC_DELAY              = 0.21 #Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 60
REQUESTS_READ_TIMEOUT       = 60

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()

def printhelp():
    #prints help text

    print(readMe)
    sys.exit(0)
    
def merakiRequestThrottler():
    #prevents hitting max request rate shaper of the Meraki Dashboard API
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    return
    
def getorglist(p_apikey):
    #returns the organizations' list for a specified admin
    #DEBUG unfinished untested
    
    merakiRequestThrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', 
            headers={'X-Cisco-Meraki-API-Key': p_apikey, 
            'Content-Type': 'application/json'},
            timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        print('ERROR 00: Unable to contact Meraki cloud')
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
    
    merakiRequestThrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', 
            headers={'X-Cisco-Meraki-API-Key': p_apikey, 
            'Content-Type': 'application/json'},
            timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        print('ERROR 01: Unable to contact Meraki cloud')
        sys.exit(2)
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_orgname:
            return record['id']
    return('null')
        
    
def getorginventory(p_apikey, p_orgid):
    #returns full org inventory

    merakiRequestThrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations/%s/inventory' % p_orgid, 
            headers={'X-Cisco-Meraki-API-Key': p_apikey, 
            'Content-Type': 'application/json'},
            timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        print('ERROR 04: Unable to contact Meraki cloud')
        return None
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        return None
    
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
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-f':
            arg_file    = arg
                      
    #check if all parameters are required parameters have been given
    if arg_apikey == '' or arg_file == '':
        printhelp()
       
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
            print('ERROR 05: Unable to open file for reading')
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
                    print('ERROR 06: Unable to resolve org ID for org name "%s"' % stripped)
        f.close()
                                
    for orgrecord in orglist:
        orginventory = getorginventory(arg_apikey, orgrecord.id)
        if not orginventory is None:
            for returnitem in orginventory:
                orgrecord.devices.append(c_devicedata())
                orgrecord.devices[len(orgrecord.devices)-1].serial = returnitem['serial']
                orgrecord.devices[len(orgrecord.devices)-1].model  = returnitem['model']
        else:
            print('Skipping org "%s": unable to fetch inventory' % orgrecord.name)
            orgrecord.skipMe = True
            
        
    for item in orglist:
        if not item.skipMe:
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
        if not item.skipMe:
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
    
                
    print('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])
