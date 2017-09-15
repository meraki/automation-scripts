# This is an example script that gets the time zone that corresponds to a street address by using 
#  Google Maps APIs. You can use this code to set network timezones in your Meraki Dashboard API scripts.
#
# This file was last modified on 2017-09-15

import sys, getopt, requests, json, time

def printhelp():
    #prints help text

    print('Prints the time zone that corresponds to a street address by using Google Maps APIs')
    print('Syntax:')
    print(' python googletimezonetest -g <Google Key> -a <address>')
    print('')
    print('To successfully run this script you will need to have the following Google API services enabled:')
    print(' * Google Maps Geocoding API')
    print(' * Google Maps Time Zone API')
    print('')
    print('To enable Google API services visit: https://console.developers.google.com')

def getgoogletimezone(p_googlekey, p_address):
    r = requests.get('https://maps.googleapis.com/maps/api/geocode/json?address=%s&key=%s' % (p_address, p_googlekey) )
        
    rjson = r.json()
    
    if rjson['status'] != 'OK':
        return('null')

    glatitude  = rjson['results'][0]['geometry']['location']['lat']
    glongitude = rjson['results'][0]['geometry']['location']['lng']
    
    s = requests.get('https://maps.googleapis.com/maps/api/timezone/json?location=%s,%s&timestamp=%f&key=%s' % (glatitude, glongitude, time.time(), p_googlekey) )

    sjson = s.json()
    
    if sjson['status'] == 'OK':
        return(sjson['timeZoneId'])

    return('null')

def main(argv):

    #get command line arguments
    arg_address   = ''
    arg_googlekey = ''
        
    try:
        opts, args = getopt.getopt(argv, 'hg:a:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-g':
            arg_googlekey = arg
        elif opt == '-a':
            arg_address = arg
            
    if arg_googlekey == '' or arg_address == '':
        printhelp()
        sys.exit(2)

    gresponse = getgoogletimezone(arg_googlekey, arg_address)
    
    print(gresponse)
    
    
    
if __name__ == '__main__':
    main(sys.argv[1:])