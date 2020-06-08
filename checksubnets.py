# This is a script to send an email alert if APs are in invalid management subnets. The alert is 
#  sent using a SMTP server; by  default Gmail. Use an automation platform like Zapier to read this email
#  and trigger further actions.
#
# You will need Python 3 and the Requests module installed to run this script:
#   https://www.python.org/downloads/
#   http://docs.python-requests.org/en/master/user/install/#install
#
# To run the script, enter:
#  python checksubnets.py -k <key> -v <valid subs> [-u <user> -p <pass> -d <dest>] [-s <srv> -o <org>]
#
# Mandatory arguments:
#  -k <key>             : Your Meraki Dashboard API key
#  -v <valid subs>      : List of valid management subnets. Alert if management IP is not in these
# Arguments to enable sending emails. All three must be given to send email. If omitted, print to screen:
#  -u <user>            : The username (email address) that will be used to send the alert message
#  -p <pass>            : Password for the email address where the message is sent from
#  -d <dest>            : Recipient email address
# Optional arguments:
#  -s <server>          : Server to use for sending SMTP. If omitted, Gmail will be used
#  -o <org>             : Name of organization to be processed. If omitted, will process all organizations
# 
# Defining subnets:
#  Parameter "-v <valid subs>" can take subnets in the following forms:
#  <subnet>/<mask>,<subnet>/<mask>,<subnet>/<mask>      Example: -v 192.168.128.0/24,10.10.0.0/16
#  file:<filename>                                      Example: -v file:validsubs.txt
#   <filename> is the name of a text file that defines the valid subnets. Enter one subnet per line
#   in the form <subnet>/<mask>
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @


import sys, getopt, requests, json, time, ipaddress, smtplib


class c_organizationdata:
    def __init__(self):
        self.name       = ''
        self.id         = ''
        self.shardhost  = ''
#end class  


#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

    
def printhelp():
    #prints help text

    printusertext('This is a script to send an email alert if APs are in invalid management subnets. The alert is')
    printusertext(' sent using a SMTP server; by  default Gmail. Use an automation platform like Zapier to read this email')
    printusertext(' and trigger further actions.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext(' python checksubnets.py -k <key> -v <valid subs> [-u <user> -p <pass> -d <dest>] [-s <srv> -o <org>]')
    printusertext('')
    printusertext('Mandatory arguments:')
    printusertext(' -k <key>             : Your Meraki Dashboard API key')
    printusertext(' -v <valid subs>      : List of valid management subnets. Alert if management IP is not in these')
    printusertext('Arguments to enable sending emails. All three must be given to send email. If omitted, print to screen:')
    printusertext(' -u <user>            : The username (email address) that will be used to send the alert message')
    printusertext(' -p <pass>            : Password for the email address where the message is sent from')
    printusertext(' -d <dest>            : Recipient email address')
    printusertext('Optional arguments:')
    printusertext(' -s <server>          : Server to use for sending SMTP. If omitted, Gmail will be used')
    printusertext(' -o <org>             : Name of organization to be processed. If omitted, will process all organizations')
    printusertext('')
    printusertext('Defining subnets:')
    printusertext(' Parameter "-v <valid subs>" can take subnets in the following forms:')
    printusertext(' <subnet>/<mask>,<subnet>/<mask>,<subnet>/<mask>      Example: -v 192.168.128.0/24,10.10.0.0/16')
    printusertext(' file:<filename>                                      Example: -v file:validsubs.txt')
    printusertext('  <filename> is the name of a text file that defines the valid subnets. Enter one subnet per line')
    printusertext('  in the form <subnet>/<mask>')
    printusertext('')
    printusertext('To make script chaining easier, all lines containing informational messages to the user')
    printusertext(' start with the character @')
    printusertext('')
    printusertext('In Windows, use double quotes ("") to pass arguments containing spaces.')
    
    
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
      
    
def getshardhost(p_apikey, p_orgid):
    #quick-n-dirty patch            
    return("api-mp.meraki.com")
   
   
def getnwlist(p_apikey, p_shardhost, p_orgid):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/networks' % (p_shardhost, p_orgid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
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
    
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/networks/%s/devices' % (p_shardhost, p_nwid), headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 04: Unable to contact Meraki cloud')
        sys.exit(2)
        
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'serial': 'null', 'model': 'null'})
        return(returnvalue)
    
    return(r.json())
    
    
def loadsubsfile(p_filename):
    # load subnets' definition file
    returnstr = ''
    
    try:
        f = open(p_filename, 'r')
    except:
        printusertext('ERROR 05: Unable to open file "%s"' % p_filename)
        sys.exit(2)
        
    for line in f:
        stripped = line.strip()
        #drop blank lines
        if len(stripped) > 0:
            #drop comments
            if stripped[0] != '#':
                if len(returnstr) != 0:
                    returnstr += ','
                returnstr += stripped   
                
    f.close()

    return (returnstr)
    
    
def main(argv):
    #  python checksubnets.py -k <key> -v <valid subs> [-u <user> -p <pass> -d <dest>] [-s <srv> -o <org>]

    #initialize variables for command line arguments
    arg_apikey  = ''
    arg_subs    = ''
    arg_user    = ''
    arg_pass    = ''
    arg_dest    = ''
    arg_server  = ''
    arg_org     = ''
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:v:u:p:d:s:o:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey  = arg
        elif opt == '-v':
            arg_subs    = arg
        elif opt == '-u':
            arg_user    = arg
        elif opt == '-p':
            arg_pass    = arg
        elif opt == '-d':
            arg_dest    = arg
        elif opt == '-s':
            arg_server  = arg
        elif opt == '-o':
            arg_org     = arg
                      
    #check if all required parameters have been given
    if arg_apikey == '' or arg_subs == '':
        printhelp()
        sys.exit(2)
        
    #set flags and default parameters
    #NOTE: EDIT THESE LINES TO MODIFY DEFAULT BEHAVIOR
    emailoptcount = 0
    if arg_user != '':
        emailoptcount += 1
    if arg_pass != '':
        emailoptcount += 1
    if arg_dest != '':
        emailoptcount += 1
    if 0 < emailoptcount < 3:
        printusertext('ERROR 06: Source account, password and destination must be given to send email report')
        sys.exit(2)
    if arg_server == '':
        arg_server = 'smtp.gmail.com:587'
        
        
    #check if subs is file or list. load contents
    splitsubs = arg_subs.split(':')
    subsbuffer = ''
    if len(splitsubs) > 1:
        if(splitsubs[0].strip()) == 'file':
            subsbuffer = loadsubsfile(splitsubs[1].strip())
        else:
            printusertext('ERROR 07: Invalid format for subnet definitions')
            sys.exit(2)
    else:
        subsbuffer = arg_subs.strip()
        
    #create subnets' list
    subnetlist = []
    splitbuffer = subsbuffer.split(',')
    for item in splitbuffer:
        try:
            subnetlist.append(ipaddress.IPv4Network(item.strip()))
        except:
            printusertext('ERROR 08: Invalid format for subnet definitions')
            sys.exit(2)
            
            
    printusertext('INFO: Retrieving organization info')
    
    orgs = []
        
    #compile list of organizations to be processed
    orgjson = getorglist(arg_apikey)
    if orgjson[0]['id'] == 'null':
        printusertext('ERROR 09: Unable to retrieve org list')
        sys.exit(2)
            
    i = 0
    for record in orgjson:
        if arg_org == '' or record['name'] == arg_org:
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
            shardhost = getshardhost(arg_apikey, record.id)
            if shardhost == 'null':
                time.sleep(API_EXEC_DELAY*(i+1))
            else:
                flag_unabletoresolveshard = False
                break
        if flag_unabletoresolveshard:
            printusertext('ERROR 10: Unable to read data for org "%s"' % record.name)
            sys.exit(2)
        else:
            record.shardhost = shardhost 
    
    
    #compile list of incompliant devices
    outputstr = 'Devices not in subnets "%s":\r\n' % subsbuffer
    flag_gotdevice = False
    for org in orgs:
        flag_neworg = True
        netbuffer = getnwlist(arg_apikey, org.shardhost, org.id)
        if len(netbuffer) > 0:
            if netbuffer[0]['id'] != 'null':
                for net in netbuffer:
                    flag_newnet = True
                    devbuffer = getdevicelist(arg_apikey, org.shardhost, net['id'])
                    if len(devbuffer) > 0:
                        if devbuffer[0]['serial'] != 'null':
                            for dev in devbuffer:
                                if dev['model'][:2] == 'MR':
                                    foundsub = False
                                    if not dev['lanIp'] is None:
                                        for sub in subnetlist:
                                            if ipaddress.IPv4Address(dev['lanIp']) in sub:
                                                foundsub = True
                                                break
                                    if not foundsub:
                                        if flag_neworg:
                                            outputstr += '\r\n---\r\n\r\nOrganization: "%s"\r\n' % org.name
                                            flag_neworg = False
                                        if flag_newnet:
                                            outputstr += '\r\nNetwork: "%s"\r\n' % net['name']
                                            flag_newnet = False
                                        outputstr += '%s %s\r\n' % (dev['serial'], dev['lanIp'])
                                        flag_gotdevice = True
                        else:
                            printusertext('WARNING: Unable to read device data for network "%s"' % net['name'])
                    else:
                        printusertext('INFO: Network "%s" contains no devices' % net['name'])
                                  
            else:
                printusertext('WARNING: Unable to read network data for org "%s"' % org.name)
        else:
            printusertext('INFO: Organization "%s" contains no networks' % org.name)                        
           
    #print output or send email if there is something to report
    if flag_gotdevice:
        if arg_user != '':
            fromaddr = arg_user
            toaddrs  = arg_dest
            msg = "\r\n".join([
                "From: %s" % fromaddr,
                "To: %s" % toaddrs,
                "Subject: Meraki access points with incompliant management IPs",
                "", outputstr])
            
            username = arg_user
            password = arg_pass
            try:
                server = smtplib.SMTP(arg_server)
                server.ehlo()
                server.starttls()
                server.login(username,password)
                server.sendmail(fromaddr, toaddrs, msg)
                server.quit()
            except:
                printusertext('ERROR 11: Unable to send email')
                sys.exit(2)
            printusertext('INFO: Email sent to %s' % toaddrs)
        else:
            print(outputstr)
    else:
        printusertext('INFO: All devices found are in scope "%s"' % subsbuffer) 
                  
    printusertext('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])