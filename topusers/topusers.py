# This is a Python 3 script to get the top 10 heaviest bandwidth users of an MX security appliance for
#  the last 10, 30 and 60 minutes. The script creates a web interface, which can be accessed with a web
#  browser via HTTP or HTTPS.
#
# Usage:
#  python topusers.py -k <api key> [-o <org name>] [-m <mode>]
#
# Command line parameters:
#  -k <api key> : Your Meraki Dashboard API key. The key needs to have at least org-wide read access.
#  -o <org name>: Optional. Use this to pull the networks list only from a specific organization.
#  -m <mode>    : Optional. Defines server security level. Either "http" or "https". Default is "https". 
#
# Example:
#  python topusers.py -k 1234 -o "Big Industries Inc"
#
# Notes:
#  * In Windows, use double quotes ("") to enter command line parameters containing spaces.
#  * This script was built for Python 3.7.1.
#  * Depending on your operating system, the command to start python can be either "python" or "python3". 
# 
# Required Python modules:
#  Requests     : http://docs.python-requests.org
#  Flask        : http://flask.pocoo.org/  
#  Flask WTF    : https://flask-wtf.readthedocs.io
#
# After installing Python, you can install these additional modules using pip with the following commands:
#  pip install requests
#  pip install flask
#  pip install flask-wtf
#
# Depending on your operating system, the command can be "pip3" instead of "pip".
#
# To run the server in HTTPS mode, you will need a certificate. Here is how to create the needed "cert.pem" 
#  and "key.pem" files as a self-signed certificate using OpenSSL:
#  https://stackoverflow.com/questions/10175812/how-to-create-a-self-signed-certificate-with-openssl

import sys, getopt, requests, json, time, datetime, os, sqlite3
from flask import Flask, jsonify, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import SelectField, SubmitField

#SECTION: GLOBAL VARIABLES: MODIFY TO CHANGE SCRIPT BEHAVIOUR

API_EXEC_DELAY              = 0.21 #Used in merakirequestthrottler() to avoid hitting dashboard API max request rate

#connect and read timeouts for the Requests module in seconds
REQUESTS_CONNECT_TIMEOUT    = 90
REQUESTS_READ_TIMEOUT       = 90

SERVER_HTTP_PORT            = '80'  #modify this to set TCP port used in HTTP mode
SERVER_HTTPS_PORT           = '443' #modify this to set TCP port used in HTTPS mode

ORGLIST_STALE_MINUTES       = 30 #minimum time between scanning for new MXs in minutes. Used by refreshOrgList2()

#Time range definitions. Run reports for these intervals
TIMERANGE_SHORT_MINUTES     = 10
TIMERANGE_MEDIUM_MINUTES    = 30
TIMERANGE_LONG_MINUTES      = 60

#SECTION: GLOBAL VARIABLES AND CLASSES: DO NOT MODIFY

LAST_MERAKI_REQUEST         = datetime.datetime.now()   #used by merakirequestthrottler()
LAST_ORGLIST_REFRESH        = datetime.datetime.now() - datetime.timedelta(minutes=ORGLIST_STALE_MINUTES+1) #for refreshOrgList2()
ARG_APIKEY                  = '' #DO NOT STATICALLY SET YOUR API KEY HERE
ARG_ORGNAME                 = '' #DO NOT STATICALLY SET YOUR ORGANIZATION NAME HERE
ORG_LIST                    = None #list of organizations, networks and MXs the used API key has access to

class c_OutRecord:
    def __init__(self):
        user        = ''
        hostname    = ''
        mac         = ''
        ip          = ''
        vlan        = ''
        
class c_Output:
    def __init__(self):
        #lists of c_OutRecord()
        short       = []
        mid         = []
        long        = []
        timestamp   = ''
        
class c_Net:
    def __init__(self):
        id          = ''
        name        = ''
        shard       = 'api.meraki.com'
        mxsn1       = ''
        mxsn2       = ''
        
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
    print('This is a Python 3 script to get the top 10 heaviest bandwidth users of an MX security appliance for')
    print(' the last 10, 30 and 60 minutes. The script creates a web interface, which can be accessed with a web')
    print(' browser via HTTP or HTTPS.')
    print('')
    print('Usage:')
    print(' python topusers.py -k <api key> [-o <org name>] [-m <mode>]')
    print('')
    print('Command line parameters:')
    print(' -k <api key> : Your Meraki Dashboard API key. The key needs to have at least org-wide read access.')
    print(' -o <org name>: Optional. Use this to pull the networks list only from a specific organization.')
    print(' -m <mode>    : Optional. Defines server security level. Either "http" or "https". Default is "https".')
    print('')
    print('Example:')
    print(' python topusers.py -k 1234 -o "Big Industries Inc"')
    print('')
    print('Notes:')
    print(' * In Windows, use double quotes ("") to enter command line parameters containing spaces.')
    
    
#SECTION: Meraki Dashboard API communication functions

def getInventory(p_org):
    #returns a list of all networks in an organization
    #on failure returns a single record with 'null' name and id
    
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
    #on failure returns a single record with 'null' name and id
    
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
    #patch
    return("api-mp.meraki.com")
  
    
def refreshOrgList2():
    global LAST_ORGLIST_REFRESH
    global ORG_LIST
    
    if (datetime.datetime.now()-LAST_ORGLIST_REFRESH).total_seconds() >= ORGLIST_STALE_MINUTES * 60:
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
                            if device['model'][:2] == 'MX' or device['model'][0] == 'Z':
                                dbcursor.execute('''INSERT INTO devices VALUES (?,?)''', (device['serial'],device['networkId']))
                    db.commit()   
                                                    
                    flag_firstnet = True
                    
                    for net in netlist:
                        if net['type'] == 'combined' or net['type'] == 'appliance': #ignore nets with no potential for MX
                            dbcursor.execute('''SELECT serial FROM devices WHERE networkId = ?''', (net['id'],))
                            
                            mxofnet = dbcursor.fetchall()
                            
                            if len(mxofnet) > 0: #network has mxes
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
                                ORG_LIST[lastorg].nets[lastnet].id    = net['id']
                                ORG_LIST[lastorg].nets[lastnet].name  = net['name']
                                ORG_LIST[lastorg].nets[lastnet].shard = org.shard
                                ORG_LIST[lastorg].nets[lastnet].mxsn1 = mxofnet[0][0]
                                ORG_LIST[lastorg].nets[lastnet].mxsn2 = None
                                if len(mxofnet) > 1:
                                    ORG_LIST[lastorg].nets[lastnet].mxsn2 = mxofnet[1][0]
                                                        
                    db.close()
                    
        LAST_ORGLIST_REFRESH = datetime.datetime.now()      
        print('INFO: Refresh complete at %s' % LAST_ORGLIST_REFRESH)
        return('Scan complete')
                     
    return ('Scan skipped. You can rescan maximum once per %i minutes' % ORGLIST_STALE_MINUTES)

    
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
    
    
def getUsageReport(p_netparams, p_minutes):
    orgid       = p_netparams[0]
    orgshard    = p_netparams[1]
    netid       = p_netparams[2]
    mxserial1   = p_netparams[3]
    mxserial2   = p_netparams[4]
    
    print('INFO: Running report for net "%s": MX1 "%s", MX2 "%s"' % (netid, mxserial1, mxserial2))
    
    clientlists = []
        
    clist = getclientlist(orgshard, mxserial1, p_minutes*60)
    if not clist is None:
        clientlists.append(clist)
    
    if not mxserial2 is None:
        clist = getclientlist(orgshard, mxserial2, p_minutes*60)
        if not clist is None:
            clientlists.append(clist)
                
    db = sqlite3.connect(':memory:')
    
    dbcursor = db.cursor()
    
    dbcursor.execute('''CREATE TABLE clients
             (UsageSent real, UsageRecv real, UsageTotal real, id text, description text, dhcpHostName text, 
              mac text, ip text, vlan text)''')
              
    db.commit()
    
    for cl in clientlists:
        for client in cl:            
            dbcursor.execute('''INSERT INTO clients VALUES (?,?,?,?,?,?,?,?,?)''', 
                (client['usage']['sent'],
                client['usage']['recv'],
                client['usage']['sent']  + client['usage']['recv'],
                client['id'],
                client['description'],
                client['dhcpHostname'],
                client['mac'],
                client['ip'],
                client['vlan']))
            
    db.commit()
    
    dbcursor = db.cursor()
    dbcursor.execute('''SELECT UsageTotal, 
                        UsageSent, 
                        UsageRecv, 
                        description, 
                        dhcpHostName, 
                        mac, 
                        ip, 
                        vlan 
                        FROM clients ORDER BY UsageTotal DESC LIMIT 10''')
    
    retvalue = dbcursor.fetchall()
        
    db.close()
    
    return(retvalue)
    

    
#SECTION: Flask web server definitions and functions  

class c_NetSelectForm(FlaskForm):
    netname     = SelectField('Select network', choices=[(1,'none')])
    submit      = SubmitField('Run report')
    
app = Flask(__name__)
app.config['SECRET_KEY'] = 'top-users-reporting-script' 

@app.route("/", methods=['GET', 'POST']) 

@app.route("/index/", methods=['GET', 'POST'])
def index():
    form = c_NetSelectForm()
    output = None
    
    form.netname.choices = []
    for org in ORG_LIST:
        for net in org.nets:
            form.netname.choices.append(('%s|%s|%s|%s|%s' % (org.id, org.shard, net.id, net.mxsn1, net.mxsn2), '%s [%s]' % (net.name, org.name) ))
    
    if request.method == 'POST':
        output          = c_Output()
        netparams       = form.netname.data.split('|')
        output.short    = getUsageReport(netparams, TIMERANGE_SHORT_MINUTES)
        output.mid      = getUsageReport(netparams, TIMERANGE_MEDIUM_MINUTES)
        output.long     = getUsageReport(netparams, TIMERANGE_LONG_MINUTES)
        output.timestamp= str(datetime.datetime.now())
        
    return render_template('index.html', form=form, tshort=TIMERANGE_SHORT_MINUTES, tmid=TIMERANGE_MEDIUM_MINUTES, tlong=TIMERANGE_LONG_MINUTES, output=output)
    
@app.route("/rescan/", methods=['GET'])
def rescan():
    flashmsg = refreshOrgList2()
    flash(flashmsg)
    return redirect(url_for('index'))

    
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
    if arg_mode == '':
        arg_mode = 'https'
    
    
    refreshOrgList2()
    
    if ORG_LIST is None:
        print('ERROR 03: No MX organizations for the specified API key')
        sys.exit(2) 
        
    if arg_mode.lower() == 'http':
        print('WARNING: Using HTTP mode (No encryption)')
        app.run(host='0.0.0.0', port=SERVER_HTTP_PORT)
    elif arg_mode.lower() == 'https':
        if os.path.exists('cert.pem') and os.path.exists('key.pem'):
            app.run(host='0.0.0.0', port=SERVER_HTTPS_PORT, ssl_context=('cert.pem', 'key.pem'), threaded=True)
        else:
            print ('ERROR 04: Cannot find "cert.pem", "key.pem". Create them or run HTTP mode with cli option "-m http"')
    else:
        print('ERROR 05: Invalid operating mode: -m %s' % arg_mode)
    
    
if __name__ == '__main__':
    main(sys.argv[1:])