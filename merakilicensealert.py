readMe= """This is a script to send an email alert if the remaining license time in an org an admin has 
 access to is less than X days, or if its license capacity is not enough for its current device 
 count. The alert is sent using an SMTP server; by  default Gmail. Use an automation platform
 like Zapier to read this email and trigger further actions.

Command line syntax:
 python merakilicensealert.py -k <key> [-u <user> -p <pass> -d <dest>] [-s <srv>] [-t <days>]
    [-m include_empty]

Mandatory argument:
 -k <key>             : Your Meraki Dashboard API key
Arguments to enable sending emails. All three must be given to send email:
 -u <user>            : The username (email address) that will be used to send the alert message
 -p <pass>            : Password for the email address where the message is sent from
 -d <dest>            : Recipient email address
Optional arguments:
 -s <server>          : Server to use for sending SMTP. If omitted, Gmail will be used
 -t <days>            : Alert threshold in days for generating alert. Default is 90
 -m include_empty     : Flag: Also send warnings for new orgs with no devices 

Example 1, send email for orgs with 180 or less days license remaining:
 python merakilicensealert.py -k 1234 -u source@gmail.com -p 4321 -d alerts@myserver.com -t 180
Example 2, print orgs with 360 or less days remaining to screen:
 python merakilicensealert.py -k 1234 -t 360"""


import sys, getopt, requests, json, time, smtplib
from datetime import datetime, date

class c_organizationdata:
    def __init__(self):
        self.name          = ''
        self.id            = ''
        self.shardhost     = ''
        self.licensestate  = ''
        self.timeremaining = 0
#end class  

#Used for time.sleep(API_EXEC_DELAY). Delay added to avoid hitting dashboard API max request rate
API_EXEC_DELAY = 0.21

#connect and read timeouts for the Requests module
REQUESTS_CONNECT_TIMEOUT = 30
REQUESTS_READ_TIMEOUT = 30


#used by merakirequestthrottler(). DO NOT MODIFY
LAST_MERAKI_REQUEST = datetime.now()   

    
def printhelp():
    print(readMe)
    
    
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
        r = requests.get('https://dashboard.meraki.com/api/v0/organizations', headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        print('ERROR 01: Unable to contact Meraki cloud')
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
   
    
def getlicensestate(p_apikey, p_shardhost, p_orgid):
    #returns the organizations' list for a specified admin
        
    merakirequestthrottler()
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/licenseState' % (p_shardhost, p_orgid) , headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'}, timeout=(REQUESTS_CONNECT_TIMEOUT, REQUESTS_READ_TIMEOUT))
    except:
        print('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        return None
    
    rjson = r.json()
    
    return(rjson)
    
def calcdaysremaining(p_merakidate):
    #calculates how many days remain between today and a date expressed in the Dashboard API license time format
    
    mdate = datetime.date(datetime.strptime(p_merakidate, '%b %d, %Y UTC'))
    today = date.today()
    
    #the first part (before space) of the date difference is number of days. rest is garbage
    retvalue = int(str(mdate - today).split(' ')[0])    
        
    return retvalue

def checklicensewarning(p_apikey, p_orglist, p_timethreshold, p_modeincludeempty = False):
    #checks org list for license violations and expiration warnings

    filterlist = []
    i = 0
    
    for org in p_orglist:
        print('INFO: Checking org %s "%s" ' % (org.id, org.name))
        licensestate  = getlicensestate(p_apikey, org.shardhost, org.id)
        if not licensestate is None:
            if licensestate['expirationDate'] == 'N/A':
                if p_modeincludeempty:
                    timeremaining = 0
                else:
                    if licensestate['status'] != 'License Required': 
                        timeremaining = p_timethreshold + 1
                    else:
                        timeremaining = 0
            else:
                timeremaining = calcdaysremaining(licensestate['expirationDate'])
            if licensestate['status'] != 'OK' or timeremaining <= p_timethreshold:
                if licensestate['status'] != 'N/A' or p_modeincludeempty:
                    filterlist.append(c_organizationdata())
                    filterlist[i].id = org.id
                    filterlist[i].name = org.name
                    filterlist[i].shardhost = org.shardhost
                    filterlist[i].licensestate = licensestate['status']
                    filterlist[i].timeremaining = timeremaining
                    i += 1
        else:
            print("WARNING: Unable to fetch license state")
    
    return(filterlist)

    
def main(argv):
    #python merakilicensealert.py -k <key> -u <username> -p <password> -d <destination> [-t <time in days>]

    #set default values for command line arguments
    arg_apikey  = ''
    arg_user    = ''
    arg_pass    = ''
    arg_target  = ''
    arg_time    = '90'
    arg_server  = 'smtp.gmail.com:587'
    arg_flag    = 'ignore_empty'
        
    #get command line arguments
    try:
        opts, args = getopt.getopt(argv, 'hk:u:p:d:t:s:m:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
    
    for opt, arg in opts:
        if   opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            arg_apikey = arg
        elif opt == '-u':
            arg_user   = arg
        elif opt == '-p':
            arg_pass   = arg
        elif opt == '-d':
            arg_target = arg
        elif opt == '-t':
            arg_time   = arg
        elif opt == '-s':
            arg_server = arg
        elif opt == '-m':
            arg_flag   = arg
                      
    #check if all parameters are required parameters have been given
    if arg_apikey == '':
        printhelp()
        sys.exit(2)
        
    #make sure that either all email parameters are given, or none:
    emailparams = 0
    if arg_user   != '':
        emailparams += 1
    if arg_pass   != '':
        emailparams += 1
    if arg_target != '':
        emailparams += 1
    if 0 < emailparams < 3:
        print('ERROR 04: -u <user> -p <pass> -d <dest> must be given to send email')
        sys.exit(2)
        
    #check and set flag
    if   arg_flag == 'ignore_empty':
        flag_includeempty = False
    elif arg_flag == 'include_empty':
        flag_includeempty = True
    else:
        print('ERROR 05: Invalid value for parameter -m <mode>')
        sys.exit(2)
    
    try:
        threshold = int(arg_time)
    except:
        print('ERROR 06: Value in parameter -t <days> must be an integer')
        sys.exit(2)
        
    print('INFO: Retrieving organization info')
        
    #compile list of organizations to be processed
    orglist = []
    orgjson = getorglist(arg_apikey)
    if orgjson[0]['id'] == 'null':
        print('ERROR 07: Unable to retrieve org list')
        sys.exit(2)
            
    i = 0
    for record in orgjson:
        orglist.append(c_organizationdata())
        orglist[i].name = record['name']
        orglist[i].id   = record['id']
        i += 1
        
        
    #get shard host/FQDN where destination org is stored
    #this call sometimes fails. implementing a try-verify-wait-repeat loop
    MAX_SHARD_RESOLVE_TRIES = 10
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
            print('ERROR 08: Unable to read data for org "%s"' % record.name)
            sys.exit(2)
        else:
            record.shardhost = shardhost 
            
    #find orgs in license incompliance state
    print('INFO: Checking orgs for license warnings')
    
    warninglist = []
    warninglist = checklicensewarning(arg_apikey, orglist, threshold, flag_includeempty)
                                     
    #send email with incompliant orgs
    if len(warninglist) > 0:
        print('INFO: Warnings found')
        if emailparams == 3:
            fromaddr = arg_user
            toaddrs  = arg_target
            msg = "\r\n".join([
                "From: %s" % fromaddr,
                "To: %s" % toaddrs,
                "Subject: Meraki organizations with license warnings",
                ""])
            for line in warninglist:
                msg = "\r\n".join([msg, 'Org name: "%s", License status: %s, Days remaining: %d' % (line.name, line.licensestate, line.timeremaining)])
            
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
                print('ERROR 09: Unable to send email')
                sys.exit(2)
            print('INFO: Email sent to %s' % toaddrs)
        else:
            for line in warninglist:
                print('Org name: "%s", License status: %s, Days remaining: %d' % (line.name, line.licensestate, line.timeremaining))
    else:
        print('INFO: No license warnings found')
    
                   
    print('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])