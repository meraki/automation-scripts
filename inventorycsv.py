readMe = '''This is a script to list the inventory of a specific organization or all organizations
 accessible by an administrator to a CSV file.
 
Syntax:
 python inventorycsv.py -k <api key> [-o <org name> -f <file path>]
 
Mandatory parameters:
 -k <api key>       Your Meraki Dashboard API key. Requires org-level privilege
 
Optional parameters:
 -o <org name>      The name of the organization to list inventory for. Omit or use "/all" for all 
 -f <file path>     The file name or path of the file to be used for output. If omitted, default
                     is file name "inventory_[timestamp].csv" in the current directory. Use
                     "/print" to display on the monitor instead.
                     
Examples:
    python inventorycsv.py -k 1234
    python inventorycsv.py -k 1234 -o "My customer account" -f /print
    
Required Python 3 modules:
 Requests     : http://docs.python-requests.org
  
 After installing Python, you can install these additional modules using pip with the following commands:
    pip install requests   

Notes:
 * Depending on your operating system, the commands for python and pip may be "python3" and "pip3" instead
 * Use double quotes to enter names containing spaces in the Windows command line    
'''

import sys, getopt, requests, json, time, datetime


### SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR


#Used in merakiRequestThrottler() to avoid hitting dashboard API max request rate
API_EXEC_DELAY              = 0.21 

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90


### SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY


LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakiRequestThrottler()

#PATCH: MEGA PROXY IS DEPRECATED
API_BASE_URL                = 'https://api.meraki.com/api/v0'
API_BASE_URL_MEGA_PROXY     = 'https://api.meraki.com/api/v0'
API_BASE_URL_NO_MEGA        = 'https://api.meraki.com/api/v0'


### SECTION: GENERAL USE FUNCTIONS


def printHelpAndExit():
    print(readMe)
    sys.exit(0)


def killScript():
    print('ERROR 01: Execution interrupted.')
    sys.exit(2)
    
    
    
### SECTION: FUNCTIONS FOR MERAKI DASHBOARD COMMUNICATION


def merakiRequestThrottler():
    #prevents hitting max request rate shaper of the Meraki Dashboard API
    global LAST_MERAKI_REQUEST
    
    if (datetime.datetime.now()-LAST_MERAKI_REQUEST).total_seconds() < (API_EXEC_DELAY):
        time.sleep(API_EXEC_DELAY)
    
    LAST_MERAKI_REQUEST = datetime.datetime.now()
    
    
def getOrganizations(p_apiKey):
    #returns the organizations' list for a specified admin, with filters applied
        
    merakiRequestThrottler()
    try:
        r = requests.get(
            API_BASE_URL + '/organizations',
            headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'},
            timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT)
        )
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
        
    rjson = r.json()
    
    return rjson
    
    
def getOrgNetworks(p_apiKey, p_orgId):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    try:
        r = requests.get(
            API_BASE_URL + '/organizations/%s/networks' % (p_orgId),
            headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'},
            timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT)
        )
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
    
    return(r.json())
    
    
def getOrgInventory(p_apiKey, p_orgId):
    #returns a list of all networks in an organization
    
    merakiRequestThrottler()
    try:
        r = requests.get( 
            API_BASE_URL + '/organizations/%s/inventory' % p_orgId,
            headers={'X-Cisco-Meraki-API-Key': p_apiKey, 'Content-Type': 'application/json'},
            timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT) 
        )
    except:
        return None
    
    if r.status_code != requests.codes.ok:
        return None
    
    return(r.json())
    
    
### SECTION: MAIN


def main(argv):
    global API_BASE_URL
    
    #set default values for command line arguments
    arg_apikey          = None
    arg_orgname         = "/all"
    arg_file            = "/blank"
    arg_proxy           = "use-mega-proxy"
    
    try:
        opts, args = getopt.getopt(argv, 'hk:o:f:x:')
    except getopt.GetoptError:
        printHelpAndExit()
    
    for opt, arg in opts:
        if opt == '-h':
            printHelpAndExit()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-o':
            arg_orgname = arg
        elif opt == '-f':
            arg_file    = arg
        elif opt == '-x':
            arg_proxy   = arg
            
    #check if all required parameters have been given
    if arg_apikey is None:
        printHelpAndExit()
        
    flag_singleOrgMode  =       arg_orgname != "/all"
    flag_printToScreen  =       arg_file    == "/print"
    flag_useDefaultFile =       arg_file    == "/blank"
    
    API_BASE_URL = API_BASE_URL_MEGA_PROXY
    if arg_proxy == 'do-not-use-mega-proxy':
        API_BASE_URL = API_BASE_URL_NO_MEGA
        
    
    #form organization invenotory tree structure in memory
    print("Fetching organizations' list...")
    orgsList = getOrganizations(arg_apikey)
    if orgsList is None:
        print("ERROR 02: Unable to fetch organizations' list")
        killScript()
        
    if flag_singleOrgMode:
        matchingOrg = None
        for org in orgsList:
            if org["name"] == arg_orgname:
                matchingOrg = org
                break
        if not matchingOrg is None:
            orgsList = [matchingOrg]
        else:
            print("ERROR 03: No organization found with that name")
            killScript()
            
    for org in orgsList:
        print('Fetching inventory for org "%s"...' % org["name"])
        org["inventory"] = getOrgInventory(arg_apikey, org["id"])
        if not org["inventory"] is None and len(org["inventory"]) > 0:
            print('Fetching networks for org "%s"...' % org["name"])
            networks = getOrgNetworks(arg_apikey, org["id"])
            if not networks is None:
                for device in org["inventory"]:
                    device["networkName"] = ""
                    device["networkTags"] = ""
                    if not device["networkId"] is None:
                        for net in networks:
                            if net["id"] == device["networkId"]:
                                device["networkName"] = net["name"]
                                if not net["tags"] is None:
                                    device["networkTags"] = net["tags"]
            else:
                for device in org["inventory"]:
                    device["networkName"] = ""
                    device["networkTags"] = ""
                print('WARNING: Unable to fetch networks for org "%s"' % org["name"])
        else:
            if org["inventory"] is None:
                print('WARNING: Inventory is none for org "%s"' % org["name"])
            else:
                print("Inventory is empty")            
                    
    #print tree structure to desired output destination
    
    if flag_printToScreen:
        for org in orgsList:
            if not org["inventory"] is None and len(org["inventory"]) > 0:
                print('\nInventory for organization: %s' % org["name"])
                print( "%-20s %-12s %-32s %s" % ("Serial", "Model", "Device name", "Network name") )
                for device in org["inventory"]:
                    print( "%-20s %-12s %-32s %s" % (device["serial"],device["model"], device["name"], device["networkName"]) )
    else:
        if flag_useDefaultFile:
            filepath = "inventory_" + str(datetime.datetime.now()).replace(" ", "_").replace(":", ".") +".csv"
        else:
            filepath = arg_file
            
        print('Writing file "%s"...' % filepath)
        
        try:
            f = open(filepath, 'w')
            f.write("serial,model,name,mac,publicIp,orgId,orgName,networkId,networkName,networkTags\n")
        except:
            print("ERROR 04: Unable to open file for writing")
            killScript()
            
        for org in orgsList:
            if not org["inventory"] is None:
                for device in org["inventory"]:
                    elements = [
                        device["serial"],
                        device["model"],
                        device["name"],
                        device["mac"],
                        device["publicIp"],
                        str(org["id"]),
                        org["name"],
                        device["networkId"],
                        device["networkName"],
                        device["networkTags"]
                    ]
                    line = ','.join(map(str, elements))
                    try:
                        f.write(line + '\n')
                    except:
                        print("ERROR 05: Unable to write to file")
                        killScript()
                        
        try:
            f.close()
        except:
            print ('ERROR 06: Unable to close file')
            killScript()
        
    print('End of script.')

if __name__ == '__main__':
    main(sys.argv[1:])
