# This is a script to migrate infrastructure from Comware-based switches, such as the
#  HPE A-series, to Meraki MS switches. The script reads an input file which defines which
#  Comware switch will be migrated to which MS. Configuration is read from Comware through SSH,
#  converted to Meraki form and uploaded to the Meraki cloud using the Dashboard API.
#
# Comware devices are referenced by IP address. Meraki devices are referenced by serial number.
#
# You need to have Python 3 and the Requests module installed. You
#  can download the module here: https://github.com/kennethreitz/requests
#  or install it using pip.
#
# The script also requires the Paramiko module for SSH functions. More info about installing Paramiko
#  can be found here: http://www.paramiko.org/installing.html
#
# This script uses spaces for indentation. Do not use the Tab character when modifying it.
#
# To run the script, enter:
#  python migratecomware.py -k <API key> -o <org name> -i <init file> [-u <default user>] [-p <default pass>] [-m <operating mode>]
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
#HOW TO CREATE AN INITIALIZATION FILE:
#An initialization file with device mappings is required for migratecomware.py
#
#For an example of a correct init config file, please see:
# https://github.com/meraki/automation-scripts/blob/master/migration_init_file.txt
#
#Initialization file #Syntax:
# * Blank lines and lines only containing whitespace will be ignored.
# * Use lines beginning with # as comments. These lines will be ignored.
# * Use "net=Network_name" to define a network. A network definition line must exist before any
#    device definition lines.
# * Device definition lines. These lines define the IP address of the original Comware switch, 
#    the Meraki MS switch serial number the configuration will be transferred to and optionally
#    a SSH username and password to log into the Comware device. If username and password are
#    omitted, default credentials will be used. These lines can have four forms:
#        <device_ip> <serial_number>
#        <device_ip> <serial_number> <username> <password>
#        file <filename> <serial_number>
#
#Examples of net definition and device definition lines, commented out:
#
#net=Migrated headquarters network 
#10.1.1.20 AAAA-BBBB-CCCC admin admin
#10.1.1.21 AAAA-BBBB-DDDD admin@system admin123
#file myconfig.cfg BBBB-CCCC-DDDD
#
#net=Migrated branch network
#192.168.10.10 AAAA-BBBB-EEEE
#
# This file was last modified on 2017-07-21

import sys, getopt, requests, json, paramiko, re

class c_portconfig:
    def __init__(self):
        self.name       = '' #WORD
        self.type       = 'null'    #copper speed or sfp
        self.number     = '0'       #number of this type of interface type+number must be a unique combination
        self.mode       = 'access'  #access or trunk
        self.vlan       = '1'       #access VLAN or trunk native VLAN
        self.allowedvlans = ''      #trunk allowed VLANs
        self.enabled    = 'true'        #values: true/false
        self.voicevlan  = ''        #voice VLAN
        self.poeenabled = ''        #values: true/false
        self.rstp       = ''
        self.isolation  = ''
        self.stpguard   = ''
        
#end class   
   
class c_merakidevice:
    def __init__(self):
        self.hostname= 'unnamed'#hostname for device
        self.serial  = ''       #serial number of destination device
        self.netname = ''       #network this device belongs to
        self.srcip   = ''       #source device IP address to pull config from. leave blank if file
        self.srcfile = ''       #source file to pull config from. leave blank if IP/SSH
        self.srcuser = ''       #source SSH username. leave blank if file
        self.srcpass = ''       #source SSH password. leave blank if file
        self.rawcfg  = []       #raw configuration as extracted from source. fields are strings
        self.portcfg = []       #port configuration of this device. fields are instances of c_portconfig()
#end class        

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

def printhelp():
    #prints help text

    printusertext('')
    printusertext('This is a script to migrate infrastructure from Comware-based switches, such as the')
    printusertext(' HPE A-series, to Meraki MS switches. The script reads an input file which defines which')
    printusertext(' Comware switch will be migrated to which MS. Configuration is read from Comware through SSH,')
    printusertext(' converted to Meraki form and uploaded to the Meraki cloud using the Dashboard API.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext('python migratecomware.py -k <API key> -o <org> -i <init file> [-u <default user>] [-p <default pass>] [-m <mode>]')
    printusertext('')
    printusertext('The script needs a valid initialization configuration file to run (parameter -i).')
    printusertext(" For syntax help please see the comment lines in the beginning of this script's code.")
    printusertext('')
    printusertext('Parameter "-m" has 3 valid forms:')
    printusertext(' * -m simulation : This is the default mode. The script will print to output a simulation')
    printusertext('     of what changes will be made to what switch. If the target devices are not part of the')
    printusertext('     organization defined in "-o", the script will fail.')
    printusertext(' * -m simulation+claim : The script will print to output a simulation')
    printusertext('     of what changes will be made to what switch. If the target devices are not part of the')
    printusertext('     organization defined in "-o", the script will attempt to claim it and read needed info.')
    printusertext(' * -m commit : The script will migrate Comware configuration to the Meraki cloud.')
    printusertext('')
    printusertext(' Example:')
    printusertext(' python migratecomware.py -k 1234 -o MyOrg -i initconfig.txt -u foo -p bar -m commit')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')

### SECTION: Functions for interacting with SSH and files    
    
def loadinitcfg(p_filename, p_defaultuser, p_defaultpass):
    #loads initial configuration from a file with network and device definitions
    
    configtable = [] #to be filled with c_merakidevice() instances
    
    networkdefined = False
    currentnet = ''
    dcount = 0
    
    linenum = 0
    try:
        f = open(p_filename, 'r')
    except:
        return(configtable)
    
    #iterate through file and parse lines
    for line in f:
        linenum += 1
        stripped = line.strip()
        #drop blank lines
        if len(stripped) > 0:
            #drop comments
            if stripped[0] != '#':
                #process network definition lines
                if stripped [:4] == 'net=':
                    if len(stripped[4:]) > 0:
                        currentnet = stripped[4:]
                        networkdefined = True
                    else:
                        printusertext('ERROR: Init config (line %d): Network name cannot be blank' % linenum)
                        sys.exit(2)            
                else:
                    #else process as a device record
                    if networkdefined:
                        splitline = stripped.split()
                        if len(splitline) > 1:
                            #look for file keyword and load config accordingly
                            if splitline[0] == 'file':
                                if len(splitline) > 2:
                                    configtable.append(c_merakidevice())
                                    configtable[dcount].netname = currentnet
                                    configtable[dcount].srcfile = splitline[1]
                                    configtable[dcount].serial  = splitline[2]
                                    dcount += 1
                                else:
                                    printusertext('ERROR: Init config (line %d): Invalid definition: %s' % (linenum, stripped))
                                    sys.exit(2)
                            else:
                                #not a source file definition. assume FQDN/IP
                                configtable.append(c_merakidevice())
                                configtable[dcount].netname = currentnet
                                configtable[dcount].srcip  = splitline[0]
                                configtable[dcount].serial = splitline[1]
                                
                                if len(splitline) > 3:
                                    #device-specific username and password defined
                                    configtable[dcount].srcuser = splitline[2]
                                    configtable[dcount].srcpass = splitline[3]
                                elif len(splitline) > 2:
                                    #got either username or password, but not both
                                    printusertext('ERROR: Init config (line %d): Invalid definition: %s' % (linenum, stripped))
                                    sys.exit(2)
                                else:
                                    #no device-specific username/password configuration. use defaults
                                
                                    #abort if default user/password are invalid
                                    if p_defaultuser == '\n' or p_defaultpass == '\n':
                                        printusertext('ERROR: Default SSH credentials needed, but not defined')
                                        sys.exit(2)
                                    configtable[dcount].srcuser = p_defaultuser
                                    configtable[dcount].srcpass = p_defaultpass
                                dcount += 1
                        else:
                            printusertext('ERROR: Init config (line %d): Invalid definition: %s' % (linenum, stripped))
                            sys.exit(2)
                    else:
                        printusertext('ERROR: Init config (line %d): Device with no network defined' % linenum)
                        sys.exit(2)
                    
                    dcount += 1
    f.close()
                        
    return (configtable)

def loadcomwareconfig (p_hostip, p_user, p_pass):
    #logs into a comware-based device using SSH and pulls its current configuration
    #returns a single line 'null' on SSH errors

    linetable = []
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    try:
        ssh.connect(p_hostip, username=p_user, password=p_pass)
        stdin, stdout, stderr = ssh.exec_command("display current")
        #THE LINE BELOW IS USED TO DISMISS "MORE" PROMPTS WHEN DISPLAYING CONFIG. ADJUST # OF SPACES IF NEEDED
        stdin.write('                                                                              \n')
        stdin.flush()
    except:
        printusertext('WARNING: Could not connect to source device: %s' % p_hostip)
        linetable.append('null')
        return (linetable)
        
    strippedline = []
    initiated = False
    for line in stdout.read().splitlines():
        if len(line) > 0:
            strippedline = line.strip().decode('ascii')
            # drop all lines before the first prompt (login banner, etc)
            # a login banner line starting with "<" and ending with ">" may cause the script to fail
            # check for sequence '<hostname>'
            if strippedline.startswith('<') and strippedline.endswith('>'):
                initiated = True
            if initiated and strippedline[0] != '<':
                # check all long lines to see if they start with "  ---- More ----"
                if len(strippedline) > 15:
                    # look for sequence "---"
                    if strippedline[:3] == '---':
                        # remove garbage from beginning of line
                        strippedline = strippedline[19:].lstrip()[5:].lstrip()
                # drop comments, check for character 35: "#"
                if strippedline[0] != '#':
                    # store ascii representations of received characters
                    linetable.append(strippedline)
    return (linetable)
    
def loadcomwarecfgfile(p_filename):
    #loads source device configuration from file
    
    linetable = []
    try:
        f = open(p_filename, 'r')
    except:
        linetable.append('null')
        printusertext('WARNING: Could not read source config file: %s' % p_filename)
        return(linetable)
        
    strippedline = ''
    
    for line in f:
        strippedline = line.strip()
        if len(strippedline) > 0:
            #ignore comments
            if strippedline[0] != '#':
                linetable.append(strippedline)
                
    f.close()
    
    return (linetable)
    
def extracthostname(p_rawcfg):
    #extract hostname form device config
    
    #command parser loop
    for cfgline in p_rawcfg:
        pieces = cfgline.split()
        
        if pieces[0] == 'sysname':
            return (pieces[1])
        
    return ('')
        
def extractportcfg(p_rawcfg):
    #extracts port (interface) configuration from a comware configuration table
        
    intcfg = []
    
    intcount = 0
    avlan = '' #string for building allowed VLAN value
    prevnum = 0 #used for keyword "to" in: port link-type trunk permit vlan
    stopnum = 0 #used for keyword "to" in: port link-type trunk permit vlan
    supportedinterface = False
    
    #command parser loop
    for cfgline in p_rawcfg:
        pieces = cfgline.split()
        
        if pieces[0] == 'description' and supportedinterface:
            #set int desc as port name. strip everything except alphanumerics and "_"
            intcfg[intcount-1].name = re.sub(r'\W+','', cfgline[12:])[:20]
        
        if pieces[0] == 'interface':
            #if interface is of a supported type, create new entry. otherwise ignore it
            #and lock int command parsing functions until a supported one comes up
            if pieces[1][:15] == 'GigabitEthernet':
                intcfg.append(c_portconfig())
                intcfg[intcount].type = 'GigabitEthernet'
                #WARNING: THE LINE BELOW ONLY WORKS PROPERLY FOR 1RU SWITCHES
                intcfg[intcount].number = pieces[1].split('/')[-1] #only take last number in string
                intcount += 1
                supportedinterface = True
            else:
                supportedinterface = False
                
                
        elif pieces[0] == 'port' and supportedinterface:
            if pieces[1] == 'access':
                if pieces[2] == 'vlan':
                    intcfg[intcount-1].vlan = pieces[3]
                    
            if pieces[1] == 'link-type':
                intcfg[intcount-1].mode = pieces[2]
                
            if pieces[1] == 'trunk':
                if pieces[2] == 'permit':
                #example Comware command: port link-type trunk permit vlan 10 50 to 60
                    if pieces[3] == 'vlan':
                        avlan = ''
                        for i in range(4, len(pieces)):
                            if pieces[i] == 'to':
                                avlan += '-'
                            else:
                                if len(avlan) == 0:
                                    avlan += pieces[i]
                                elif avlan[len(avlan)-1] == '-':   
                                    avlan += pieces[i]
                                else:
                                    avlan += ',%s' % pieces[i]
                        
                        intcfg[intcount-1].allowedvlans = avlan
                                
                if pieces[2] == 'pvid':
                    if pieces[3] == 'vlan':
                        intcfg[intcount-1].vlan = pieces[4]
                        
        #elif pieces[0] == 'port-security':
            #DEBUG: keep the line below commented, unless debugging this function
            #printusertext ('DEBUG: Port security: %s' % pieces[1])
        #    if intcount == 0:
            #still in global config
        #        if pieces[1] == 'enable':
                    #printusertext ('DEBUG: Enable port-security')
        #            continue
        
        if pieces[0] == 'shutdown' and supportedinterface:
            intcfg[intcount-1].enabled = 'false'
        
        #elif pieces[0] == 'undo' and supportedinterface:
            #DEBUG: keep the line below commented, unless debugging this function
            #printusertext ('DEBUG: Undo for int [%d]: %s' % (intcount, pieces[1]))
        #    if pieces[1] == 'dot1x':
                #printusertext ('DEBUG: Dot1x: %s' % pieces[2])
        #        continue
                
        #else:
            #DEBUG: keep the line below commented, unless debugging this function
            #print ('DEBUG: Invalid line')
    
    return(intcfg)
        
### SECTION: Functions for interacting with Dashboard          
        
def getorgid(p_apikey, p_orgname):
    #looks up org id for a specific org name
    #on failure returns 'null'
    
    r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_orgname:
            return record['id']
    return('null')
    
def getshardurl(p_apikey, p_orgid):
    #Looks up shard URL for a specific org. Use this URL instead of 'dashboard.meraki.com'
    # when making API calls with API accounts that can access multiple orgs.
    #On failure returns 'null'
    
    r = requests.get('https://dashboard.meraki.com/api/v0/organizations/%s/snmp' % p_orgid, headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
        
    rjson = r.json()

    return(rjson['hostname'])
    
def getnwid(p_apikey, p_shardurl, p_orgid, p_nwname):
    #looks up network id for a network name
    #on failure returns 'null'

    r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    if r.status_code != requests.codes.ok:
        return 'null'
    
    rjson = r.json()
    
    for record in rjson:
        if record['name'] == p_nwname:
            return record['id']
    return('null') 
    
def createnw(p_apikey, p_shardurl, p_dstorg, p_nwdata):
    #creates network if one does not already exist with the same name
    #example for p_nwdata:
    #nwparams = {'name': 'hi', 'timeZone': 'Europe/Helsinki', 'tags': 'mytag', 'organizationId': '123', 'type': 'switch appliance'}
    
    #check if network exists
    getnwresult = getnwid(p_apikey, p_shardurl, p_dstorg, p_nwdata['name'])
    if getnwresult != 'null':
        printusertext('WARNING: Skipping network "%s" (Already exists)' % p_nwdata['name'])
        return('null')
    
    if p_nwdata['type'] == 'combined':
        #find actual device types
        nwtype = 'wireless switch appliance'
    else:
        nwtype = p_nwdata['type']
    if nwtype != 'systems manager':
        r = requests.post('https://%s/api/v0/organizations/%s/networks' % (p_shardurl, p_dstorg), data=json.dumps({'timeZone': p_nwdata['timeZone'], 'tags': p_nwdata['tags'], 'name': p_nwdata['name'], 'organizationId': p_dstorg, 'type': nwtype}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    else:
        printusertext('WARNING: Skipping network "%s" (Cannot create SM networks)' % p_nwdata['name'])
        return('null')
        
    return('ok')
        
def claimdevice(p_apikey, p_shardurl, p_nwid, p_devserial):
    #claims a device into an org
    
    r = requests.post('https://%s/api/v0/networks/%s/devices/claim' % (p_shardurl, p_nwid), data=json.dumps({'serial': p_devserial}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    return(0)
    
def claimdeviceorg(p_apikey, p_shardurl, p_orgid, p_devserial):
    #claims a device into an org without adding to a network
    
    r = requests.post('https://%s/api/v0/organizations/%s/claim' % (p_shardurl, p_orgid), data=json.dumps({'serial': p_devserial}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    return(0)
    
def getorgdeviceinfo (p_apikey, p_shardurl, p_orgid, p_devserial):
    #gets basic device info from org inventory. device does not need to be part of a network
    
    r = requests.get('https://%s/api/v0/organizations/%s/inventory' % (p_shardurl, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    
    returnvalue = {}
    if r.status_code != requests.codes.ok:
        returnvalue = {'serial':'null', 'model':'null'}
        return(returnvalue)
    
    rjson = r.json()
    
    foundserial = False
    for record in rjson:
        if record['serial'] == p_devserial:
            foundserial = True
            returnvalue = {'mac': record['mac'], 'serial': record['serial'], 'networkId': record['networkId'], 'model': record['model'], 'claimedAt': record['claimedAt'], 'publicIp': record['publicIp']}
                
    if not foundserial:
        returnvalue = {'serial':'null', 'model':'null'}
    return(returnvalue) 
        
def setswportconfig(p_apikey, p_shardurl, p_devserial, p_portnum, p_portcfg):
    #sets switchport configuration to match table given as parameter
    
    validconfig = {}
    
    for key, value in p_portcfg.items():
        if value != '':
            validconfig[key] = value
            
    print(validconfig)        
            
    r = requests.put('https://%s/api/v0/devices/%s/switchPorts/%s' % (p_shardurl, p_devserial, p_portnum), data=json.dumps(validconfig), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
        
    print(r.status_code)    
        
    return (0)
    
def setdevicedata(p_apikey, p_shardurl, p_nwid, p_devserial, p_field, p_value, p_movemarker):
    #modifies value of device record. Returns the new value
    #on failure returns one device record, with all values 'null'
    #p_movemarker is boolean: True/False
    
    movevalue = "false"
    if p_movemarker:
        movevalue = "true"
    
    r = requests.put('https://%s/api/v0/networks/%s/devices/%s' % (p_shardurl, p_nwid, p_devserial), data=json.dumps({p_field: p_value, 'moveMapMarker': movevalue}), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
            
    if r.status_code != requests.codes.ok:
        return ('null')
    
    return('ok')
   
def migratedevices(p_apikey, p_shardurl, p_orgid, p_devt, p_mode):
    #migrates configuration according to device table p_devt. has three modes according to p_mode
    #p_mode = 'commit'    : uploads configuration to Meraki cloud
    #p_mode = 'simulation': prints intended changes to stdout without touching cloud. will fail if device not in inventory
    #p_mode = 'simulation+claim': prints intended changes to stdout without touching cloud. will attempt to claim devices if they are not in inventory to get info
    
    mode_commit = False
    mode_claim  = False
    nwid = ''
    portconfig = {}
    max_migrated_ports = 0
    
    if p_mode == 'commit':
        mode_commit = True
        mode_claim  = True
    elif p_mode == 'simulation+claim':
        mode_claim  = True
    
    for dev in p_devt:
        nwid = getnwid(p_apikey, p_shardurl, p_orgid, dev.netname)
        
        if nwid == 'null' and mode_commit:
            #if nw missing and commit mode, it needs to be created
            #nwid == 'null' is OK if running simulation
            #NOTE THAT TIMEZONE IS HARDCODED IN THE SCRIPT AT THIS POINT. THIS MAY CHANGE IN A LATER VERSION
            nwparams = {'name': dev.netname, 'timeZone': 'Europe/Helsinki', 'tags': 'migratecomwarepy', 'organizationId': p_orgid, 'type': 'switch'}
            createnw(p_apikey, p_shardurl, p_orgid, nwparams)
            
            nwid = getnwid(p_apikey, p_shardurl, p_orgid, dev.netname)
            
            #check if something went wrong
            if nwid == 'null':
                printusertext('ERROR: Unable to get ID for network %s' % dev.netname)
                sys.exit(2)   
            
        #get model of device to check that it is a switch
        devinfo = getorgdeviceinfo (p_apikey, p_shardurl, p_orgid, dev.serial)
        if devinfo['model'] == 'null':
            if mode_claim:
                claimdeviceorg(p_apikey, p_shardurl, p_orgid, dev.serial)
                
                devinfo = getorgdeviceinfo (p_apikey, p_shardurl, p_orgid, dev.serial)
                
                if devinfo['model'] == 'null':
                    printusertext('ERROR: Unable to claim device %s' % dev.serial)
                    sys.exit(2)  
                               
            else:
                printusertext('ERROR: Device %s not part of org %s' % (dev.serial, p_orgid))
                sys.exit(2)  
                
        if devinfo['model'][:2] != 'MS':
            printusertext('ERROR: Device %s is type "%s": Not a switch' % (dev.serial, devinfo['model']))
            sys.exit(2) 
            
        #at this stage we have nwid and device model
        
        #the switch may or may not be part of a network, so cannot read number of ports dynamically.
        #it will need to be done as part of a static configuration list
        #assumes model name convention of MXxxx-yyzz, where xxx: model series, yy:number of ports, zz:poe
        
        modelnumber = re.sub(r'[^0-9]','',devinfo['model'][:5])
        portnumber  = re.sub(r'[^0-9]','',devinfo['model'][6:])
        
        if   modelnumber == '220':
            if   portnumber == '8':
                max_migrated_ports = 10
            elif portnumber == '24':
                max_migrated_ports = 28
            elif portnumber == '48':
                max_migrated_ports = 52
                
        elif modelnumber == '225':
            if   portnumber == '24':
                max_migrated_ports = 28
            elif portnumber == '48':
                max_migrated_ports = 52
                
        elif modelnumber == '250':
            if   portnumber == '24':
                max_migrated_ports = 28
            elif portnumber == '48':
                max_migrated_ports = 52
                
        elif modelnumber == '350':
            if   portnumber == '24':
                max_migrated_ports = 28
            elif portnumber == '48':
                max_migrated_ports = 52
                
        elif modelnumber == '410':
            if   portnumber == '16':
                max_migrated_ports = 18
            elif portnumber == '32':
                max_migrated_ports = 34
                
        elif modelnumber == '425':
            if   portnumber == '16':
                max_migrated_ports = 18
            elif portnumber == '32':
                max_migrated_ports = 34
        else:
            #if unknown device model, assume 0 uplinks as failsafe, until the script is updated to support it
            intportnumber = int(portnumber)
                        
            #if Meraki switch nodel naming has changed from MSxxx-yy, the line below will fail
            if intportnumber <= 48:
                max_migrated_ports = intportnumber

        #deal with port number mismatches    
        if len(dev.portcfg) < max_migrated_ports:
            max_migrated_ports = len(dev.portcfg)
                  
        #now that we also know the MAC address of the device, we can also reset the hostname 
        #for devices that did not get a value by running extracthostname() previously
        if dev.hostname == '':
            dev.hostname = devinfo['mac']
                     
        #do preliminary stuff, like claiming device to nw or printing header
        if mode_commit:
            claimdevice(p_apikey, p_shardurl, nwid, dev.serial)        
            devinfo = getorgdeviceinfo (p_apikey, p_shardurl, p_orgid, dev.serial)
            if devinfo['networkId'] != nwid:
                printusertext('ERROR: Unable set network for device %s' % dev.serial)
                sys.exit(2)
                
            #set hostname. Don't worry if it fails
            setdevicedata(p_apikey, p_shardurl, nwid, dev.serial, 'name', dev.hostname, 'false')
            printusertext('INFO: Migrating device %s (name: %s), source %s%s' % (dev.serial, dev.hostname, dev.srcip, dev.srcfile))
            
        else:
            print('')
            print('Migration target device %s (name: %s, %s) in network "%s"' % (dev.serial, dev.hostname, devinfo['model'],dev.netname))
            print('Source: %s%s' % (dev.srcip, dev.srcfile))
            print('Num                  Name    Mode  Enabled   VLAN     PoE  VoiceVLAN  TrnkAllowVLAN')
     
        for i in range (0, max_migrated_ports):
            portconfig = {'isolationEnabled': dev.portcfg[i].isolation, 'rstpEnabled': dev.portcfg[i].rstp, 'enabled': dev.portcfg[i].enabled, 'stpGuard': dev.portcfg[i].stpguard, 'accessPolicyNumber': '', 'type': dev.portcfg[i].mode, 'allowedVlans': dev.portcfg[i].allowedvlans, 'poeEnabled': dev.portcfg[i].poeenabled, 'name': dev.portcfg[i].name, 'tags': 'migratecomwarepy', 'number': dev.portcfg[i].number, 'vlan': dev.portcfg[i].vlan, 'voiceVlan': dev.portcfg[i].voicevlan}
                                        
            if mode_commit:
                setswportconfig(p_apikey, p_shardurl, dev.serial, dev.portcfg[i].number, portconfig)  
            else:
                print('%s  %s %s   %s  %s %s %s       %s' % ("{:>3s}".format(portconfig['number']), "{:>20s}".format(portconfig['name']), "{:>7s}".format(portconfig['type']), "{:>6s}".format(portconfig['enabled']), "{:>5s}".format(portconfig['vlan']),  "{:>7s}".format(portconfig['poeEnabled']), "{:>5s}".format(portconfig['voiceVlan']), portconfig['allowedVlans']))
                        
    return() #migratedevices()
  
### SECTION: Main function    
  
def main(argv):
    #set default values for command line arguments
    arg_apikey = 'null'
    arg_orgname = 'null'
    arg_initfile = '????'   #a default value that is not a valid filename
    arg_defuser = '\n'      #a default value that is not a valid username
    arg_defpass = '\n'      #a default value that is not a valid password
    arg_mode = 'simulation'
        
    #get command line arguments
    #  python deployappliance.py -k <key> -o <org> -s <serial> -n <network name> -t <template>
    try:
        opts, args = getopt.getopt(argv, 'hk:o:i:u:p:m:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey = arg
        elif opt == '-o':
            arg_orgname = arg
        elif opt == '-i':
            arg_initfile = arg
        elif opt == '-u':
            arg_defuser = arg
        elif opt == '-p':
            arg_defpass = arg
        elif opt == '-m':
            arg_mode = arg
                
    #check if all required parameters have been given
    if arg_apikey == 'null' or arg_orgname == 'null' or arg_initfile == '????':
        printhelp()
        sys.exit(2)
        
    #get organization id corresponding to org name provided by user
    orgid = getorgid(arg_apikey, arg_orgname)
    if orgid == 'null':
        printusertext('ERROR: Fetching organization failed')
        sys.exit(2)
    
    #get shard URL where Org is stored
    shardurl = getshardurl(arg_apikey, orgid)
    if shardurl == 'null':
        printusertext('ERROR: Fetching Meraki cloud shard FQDN failed')
        sys.exit(2)
    
    #load configuration file
    devices = loadinitcfg(arg_initfile, arg_defuser, arg_defpass)
    
    if len(devices) == 0:
        printusertext('ERROR: No valid configuration in init file')
        sys.exit(2)
                
    #read configuration from source devices specified in init config
    for i in range(0, len(devices)):
        if devices[i].srcip != '':
            devices[i].rawcfg = loadcomwareconfig (devices[i].srcip, devices[i].srcuser, devices[i].srcpass)
        else:
            devices[i].rawcfg = loadcomwarecfgfile (devices[i].srcfile)
        
    #extract port configuration from source configuration
    for dev in devices:
        dev.hostname = extracthostname(dev.rawcfg)
        dev.portcfg = extractportcfg(dev.rawcfg)
        
    #run migration function in correct operating mode    
    if arg_mode == 'simulation':
        migratedevices(arg_apikey, shardurl, orgid, devices, 'simulation')
    elif arg_mode == 'commit':
        migratedevices(arg_apikey, shardurl, orgid, devices, 'commit')
    elif arg_mode == 'simulation+claim':
        migratedevices(arg_apikey, shardurl, orgid, devices, 'simulation+claim')
    else:
        printusertext('ERROR: Parameter -m: Operating mode not valid')
        sys.exit(2)
    
    printusertext('End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])