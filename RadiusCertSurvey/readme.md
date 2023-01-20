This script, for a given API key, and network ID, does a survey of devices that has the
radius.meraki.com cert and flags devices that have an out of date cert (the date of which)
is requested from the user

Mandatory arguments:

-k <API KEY>      : Your Meraki Dashboard API Key

-n networkID      : Your Meraki network ID

optional arguments:

-v                : turn on verbose mode

 Pre requisites:
 Meraki library : pip install meraki : https://developer.cisco.com/meraki/api/#/python/getting-started
 
Included files:

RadiusCertSurvey.csv    The output file

RadiusCertSurvey.py     The Python scrips

readme.md               This file
