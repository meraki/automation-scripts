# This script, for a given API key, and network ID, does a survey of devices that has the
# radius.meraki.com cert and flags devices that have an out of date cert (the date of which)
# is requested from the user

# please ensure that you also have created the RadiusCertSurvey.csv file
#
# Mandatory arguments:
# -k <API KEY>      : Your Meraki Dashboard API Key
# -n networkID      : Your Meraki network ID
# optional arguments:
# -v                : turn on verbose mode

# Pre requisites:
# Meraki library : pip install meraki : https://developer.cisco.com/meraki/api/#/python/getting-started

import meraki
from datetime import datetime
import logging, sys, getopt

def main(argv):

    print("Meraki Library version: ")
    print(meraki.__version__)

    arg_apikey = False

    fileForResults = "RadiusCertSurveyResults.csv"

    loggingEnabled = False
    verbose = False

    try:
        opts, args = getopt.getopt(argv, 'k:n:vl')
    except getopt.GetOptError:
        printhelp(argv)
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-k':
            arg_apikey = arg
        elif opt == '-n':
            arg_networkId = arg
        elif opt == '-v':
            verbose = True
        elif opt == '-l':
            loggingEnabled = True

    while True:
        try:
            # Note: Python 2.x users should use raw_input, the equivalent of 3.x's input
            print("Please enter the expected radius.meraki.com expiration date")
            rawDateInput = input("in the format of YYYY-MM-DD : ")
            expirationDate = datetime.strptime(rawDateInput, "%Y-%m-%d").date()

        except ValueError:
            print("The date really does need to be in the format of YYYY-MM-DD.")
            # better try again... Return to the start of the loop
            continue
        else:
            # input successfully converted to a date
            break

    # Create Meraki Client Object and initialise
    client = meraki.DashboardAPI(api_key=arg_apikey)

    # the URL parameter gives us a shortcut directly into Meraki Dashboard
    devices = client.sm.getNetworkSmDevices(networkId=arg_networkId, fields=["url"])

    for device in devices:
        deviceId = device["id"]
        deviceInfo = "***********************************************************************************************\n"
        deviceInfo = deviceInfo + device["name"] + " serial : " + device["serialNumber"] + "\n"
        deviceInfo = deviceInfo + "URL to device : " + device["url"]

        certs = client.sm.getNetworkSmDeviceCerts(networkId=arg_networkId, deviceId=deviceId)
        if len(certs) > 0:
            updatedCert = False

            certsArray = [] # we'll add the certs to this just in case the user has verbose turned on
            for cert in certs:
                if cert["name"] == "radius.meraki.com":
                    certExpDate = datetime.strptime(cert["notValidAfter"], "%Y-%m-%dT%H:%M:%S.%f%z").date()
                    certsArray += str(certExpDate) + " "
                    if certExpDate > expirationDate:
                        updatedCert = True
            if updatedCert:
                if verbose:
                    print(deviceInfo)
                    writeToFile(fileForResults, deviceInfo)
                    writeToFile(fileForResults, certsArray)
                    print(certsArray)
                    writeToFile(fileForResults, "we've got an updated cert\n")
                    print("we've got an updated cert\n")
            else:
                print(deviceInfo)
                writeToFile(fileForResults, deviceInfo)
                writeToFile(fileForResults, certsArray)
                print(certsArray)
                writeToFile(fileForResults, "bad news, no updated cert\n")
                print("bad news, no updated cert\n")


def printhelp():
    # prints help information
    print('This is a script that, for a given network and API key')
    print('Asks the user for a radius.meraki.com certificate expiration date')
    print('For every managed device, it then gets all of the radius.meraki.com certs for that device')
    print('And highlights any devices that do NOT have the update cert')
    print('Its probably best that you use a cert date of EXPECTED-1, so...')
    print('If the radius.meraki.com cert expiration date is 2023-11-30, input 2023-11-29')
    print('')
    print('Mandatory arguments:')
    print(' -k <api key>         : Your Meraki Dashboard API key')
    print(' -n network ID        : Your Meraki Dashboard Network ID that has your managed devices in')
    print('Optional arguments:')
    print(' -v                   :Turn on Verbose mode')


def writeToLog(MessageToLog, toLog):
    if toLog:
        logging.warning(MessageToLog)


def writeToFile(passedFile, messagetoWrite):
    openFileForRead = open(passedFile, 'r')
    fileContents = openFileForRead.read()
    openFileForRead.close()
    openedFile = open(passedFile, 'w')
    openedFile.writelines(fileContents)
    openedFile.writelines('\n')
    openedFile.writelines(messagetoWrite)
    openedFile.close()


if __name__ == '__main__':
    main(sys.argv[1:])
