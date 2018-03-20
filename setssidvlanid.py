# This is a script to set the VLAN on an SSID. Usage:
#  python setssidvlanid.py -k <api_key> -o <org_name> -n <ssid_name> -v <vlan_id>
#
# Example:
#  python setssidvlanid.py -k 1234 -o "Meraki Inc" -n "Meraki corp" -v 10
#
# The script requires the Requests module. To install it via pip:
#  pip install requests
#
# To pass parameters containing spaces in Windows, use double quotes "".
#
# This file was last modified on 2018-03-20

import sys, getopt, requests, json, time
from datetime import datetime

#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

#connect and read timeouts for the Requests module
REQUESTS_CONNECT_TIMEOUT = 30
REQUESTS_READ_TIMEOUT    = 30

#used by merakirequestthrottler(). DO NOT MODIFY
LAST_MERAKI_REQUEST = datetime.now()

def merakirequestthrottler(p_requestcount=1):
    #makes sure there is enough time between API requests to Dashboard not to hit shaper
    global LAST_MERAKI_REQUEST
    
    if (datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY*p_requestcount):
        time.sleep(API_EXEC_DELAY*p_requestcount)
    
    LAST_MERAKI_REQUEST = datetime.now()
    return 
    
    
def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)
    
    
def printhelp():
    #prints help text

    printusertext('This is a script to set the VLAN on an SSID. Usage:')
    printusertext('    python setssidvlanid.py -k <api_key> -o <org_name> -n <ssid_name> -v <vlan_id>')
    printusertext('')
    printusertext('Example:')
    printusertext('    python setssidvlanid.py -k 1234 -o "Meraki Inc" -n "Meraki corp" -v 10')
    printusertext('')
    printusertext('To pass parameters containing spaces in Windows, use double quotes "".')
    
    
def getorgid(p_apikey, p_orgname):
    #looks up org id for a specific org name
    #on failure returns 'null'
    
    merakirequestthrottler()
    try:
        r = requests.get('https://api.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
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
    
    
def getnwlist(p_apikey, p_shardhost, p_orgid):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 02: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'name': 'null', 'id': 'null'})
        return(returnvalue)
    
    return(r.json())
    
    
def getssids(p_apikey, p_shardhost, p_netid):
    #returns a list of all MR SSIDs in a network
    
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/networks/%s/ssids' % (p_shardhost, p_netid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'number': 'null'})
        return(returnvalue)
    
    return(r.json())
    
    
def setssidattribute(p_apikey, p_shardhost, p_netid, p_ssidnum, p_attribute, p_value):
    #writes one attribute to one SSID
    
    merakirequestthrottler()
    
    try:
        r = requests.put('https://%s/api/v0/networks/%s/ssids/%s' % (p_shardhost, p_netid, p_ssidnum), data=json.dumps({p_attribute: p_value}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) )
    except:
        printusertext('ERROR 04: Unable to contact Meraki cloud')
        sys.exit(2)
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')
    
    
def main(argv):
    printusertext('INFO: Script started at %s' % datetime.now())
    
    #   python setssidvlanid.py -k <api_key> -o <org_name> -n <ssid_name> -v <vlan_id>

    #initialize variables for command line arguments
    arg_apikey      = ''
    arg_orgname     = ''
    arg_ssidname    = ''
    arg_vlanid      = ''
    
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:o:n:v:')
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
        elif opt == '-n':
            arg_ssidname = arg
        elif opt == '-v':
            arg_vlanid  = arg
            
    #check if all required parameters have been given
    if arg_apikey == '' or arg_orgname == '' or arg_ssidname == '' or arg_vlanid == '':
        printhelp()
        sys.exit(2)
        
    #resolve orgid    
    orgid = getorgid(arg_apikey, arg_orgname) 
    if orgid == 'null':
        printusertext('ERROR 05: Unable to find org named "%s"' % arg_orgname)
        sys.exit(2)
      
    #get networks' list for orgid
    netlist = getnwlist(arg_apikey, 'api.meraki.com', orgid)
    
    if netlist[0]['id'] == 'null':
        printusertext('ERROR 06: Error retrieving net list for org id "%s"' % orgid)
        sys.exit(2)
        
    for net in netlist:
    
        #get SSID list
        ssidlist = getssids(arg_apikey, 'api.meraki.com', net['id'])
        
        if ssidlist[0]['number'] == 'null':
            printusertext('WARNING: Skipping network "%s": contains no MRs' % net['name'])
        else:
            #get SSID number corresponding to SSID name
            for ssid in ssidlist:
                if ssid['name'] == arg_ssidname:
                    printusertext('INFO: Setting VLAN ID "%s" for net "%s", SSID %s "%s"' % (arg_vlanid, net['name'], ssid['number'], ssid['name']))
                    
                    #set VLAN for correct SSID number
                    if ssid['ipAssignmentMode'] in ['Layer 3 roaming with a concentrator', 'VPN']:
                        setssidattribute(arg_apikey, 'api.meraki.com', net['id'], ssid['number'], 'vlanId', arg_vlanid)
                    
                    break #SSID name is unique, so no need to check the rest
    
    
if __name__ == '__main__':
    main(sys.argv[1:])