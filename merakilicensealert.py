# This is a script to send an email alert if the remaining license time in an org an admin has access to is
#  less than X days, or if its license capacity is not enough for its current device count. The alert is 
#  sent using an SMTP server; by  default Gmail. Use an automation platform like Zapier to read this email
#  and trigger further actions.
#
# To run the script, enter:
#  python merakilicensealert.py -k <key> [-u <user> -p <pass> -d <dest>] [-s <srv>] [-t <days>] [-m include_empty]
#
# Mandatory argument:
#  -k <key>             : Your Meraki Dashboard API key
# Arguments to enable sending emails. All three must be given to send email:
#  -u <user>            : The username (email address) that will be used to send the alert message
#  -p <pass>            : Password for the email address where the message is sent from
#  -d <dest>            : Recepient email address
# Optional arguments:
#  -s <server>          : Server to use for sending SMTP. If omitted, Gmail will be used
#  -t <days>            : Alert threshold in days for generating alert. Default is 90
#  -m include_empty     : Flag: Also send warnings for new orgs with no devices 
# 
# Example 1, send email for orgs with 180 or less days license remaining:
#  python merakilicensealert.py -k 1234 -u sourceaccount@gmail.com -p 4321 -d alerts@myserver.com -t 180
# Example 2, print orgs with 360 or less days remaining to screen:
#  python merakilicensealert.py -k 1234 -t 360
#
# To make script chaining easier, all lines containing informational messages to the user
#  start with the character @
#
# This file was last modified on 2017-11-23


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

def printusertext(p_message):
    #prints a line of text that is meant for the user to read
    #do not process these lines when chaining scripts
    print('@ %s' % p_message)

    
def printhelp():
    #prints help text

    printusertext('This is a script to send an email alert if the remaining license time in an org an admin has access to is')
    printusertext(' less than X days, or if its license capacity is not enough for its current device count. The alert is')
    printusertext(' sent using an SMTP server; by  default Gmail. Use an automation platform like Zapier to read this email')
    printusertext(' and trigger further actions.')
    printusertext('')
    printusertext('To run the script, enter:')
    printusertext(' python merakilicensealert.py -k <key> [-u <user> -p <pass> -d <dest>] [-s <srv>] [-t <days>] [-m include_empty]')
    printusertext('')
    printusertext('Mandatory argument:')
    printusertext(' -k <key>             : Your Meraki Dashboard API key')
    printusertext('Arguments to enable sending emails. All three must be given to send email:')
    printusertext(' -u <user>            : The username (email address) that will be used to send the alert message')
    printusertext(' -p <pass>            : Password for the email address where the message is sent from')
    printusertext(' -d <dest>            : Recepient email address')
    printusertext('Optional arguments:')
    printusertext(' -s <server>          : Server to use for sending SMTP. If omitted, Gmail will be used')
    printusertext(' -t <days>            : Alert threshold in days for generating alert. Default is 90')
    printusertext(' -m include_empty     : Flag: Also send warnings for new orgs with no devices ')
    printusertext('')
    printusertext('Example 1, send email for orgs with 180 or less days license remaining:')
    printusertext(' python merakilicensealert.py -k 1234 -u sourceaccount@gmail.com -p 4321 -d alerts@myserver.com -t 180')
    printusertext('Example 2, print orgs with 360 or less days remaining to screen:')
    printusertext(' python merakilicensealert.py -k 1234 -t 360')
    printusertext('')
    printusertext('Use double quotes ("") in Windows to pass arguments containing spaces. Names are case-sensitive.')
    
    
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
   
    
def getlicensestate(p_apikey, p_shardhost, p_orgid):
    #returns the organizations' list for a specified admin
        
    time.sleep(API_EXEC_DELAY)
    try:
        r = requests.get('https://%s/api/v0/organizations/%s/licenseState' % (p_shardhost, p_orgid) , headers={'X-Cisco-Meraki-API-Key': p_apikey, 'Content-Type': 'application/json'})
    except:
        printusertext('ERROR 03: Unable to contact Meraki cloud')
        sys.exit(2)
    
    returnvalue = []
    if r.status_code != requests.codes.ok:
        returnvalue.append({'status':'null'})
        return returnvalue
    
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
        licensestate  = getlicensestate(p_apikey, org.shardhost, org.id)
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
        printusertext('ERROR 04: -u <user> -p <pass> -d <dest> must be given to send email')
        sys.exit(2)
        
    #check and set flag
    if   arg_flag == 'ignore_empty':
        flag_includeempty = False
    elif arg_flag == 'include_empty':
        flag_includeempty = True
    else:
        printusertext('ERROR 05: Invalid value for parameter -m <mode>')
        sys.exit(2)
    
    try:
        threshold = int(arg_time)
    except:
        printusertext('ERROR 06: Value in parameter -t <days> must be an integer')
        sys.exit(2)
        
    printusertext('INFO: Retrieving organization info')
        
    #compile list of organizations to be processed
    orglist = []
    orgjson = getorglist(arg_apikey)
    if orgjson[0]['id'] == 'null':
        printusertext('ERROR 07: Unable to retrieve org list')
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
            printusertext('ERROR 08: Unable to read data for org "%s"' % record.name)
            sys.exit(2)
        else:
            record.shardhost = shardhost 
            
    #find orgs in license incompliance state
    printusertext('INFO: Checking orgs for license warnings')
    
    warninglist = []
    warninglist = checklicensewarning(arg_apikey, orglist, threshold, flag_includeempty)
                                     
    #send email with incompliant orgs
    if len(warninglist) > 0:
        printusertext('INFO: Warnings found')
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
                printusertext('ERROR 09: Unable to send email')
                sys.exit(2)
            printusertext('INFO: Email sent to %s' % toaddrs)
        else:
            for line in warninglist:
                print('Org name: "%s", License status: %s, Days remaining: %d' % (line.name, line.licensestate, line.timeremaining))
    else:
        printusertext('INFO: No license warnings found')
    
                   
    printusertext('INFO: End of script.')
            
if __name__ == '__main__':
    main(sys.argv[1:])