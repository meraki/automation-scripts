# ASA Cryptomap Converter

A tool to import cryptomap-based site-to-site VPN tunnel entries from an ASA configuration file to a Meraki dashboard organization.
--------------------------------------

# Important notes

* The script will only import VPN tunnel configuration as third-party VPN peers, not firewalling rules
* The script has been built as a MVP to convert a very specific ASA 9.8(4)20 configuration. Using it with other configurations may require modification of the script
* The script consists of two files, **cryptomap_converter.py** and **asa_config_parser_module.py**, which need to be in the same folder for the script to run. The one you run to initiate the script is **cryptomap_converter.py**

# Prerequisites

1. Install Python 3 and the requests module. You can find them here
* https://www.python.org/
* https://docs.python-requests.org
    
2. Enable site-to-site VPN in Meraki dashboard by making your MX security appliance a hub or a spoke: https://documentation.meraki.com/MX/Site-to-site_VPN/Site-to-Site_VPN_Settings    
3. If you want to limit availability of the converted tunnels to certain MXs in your organization, create a network tag and associate it with their networks: https://documentation.meraki.com/General_Administration/Organizations_and_Networks/Organization_Menu/Manage_Tags
    
    
# Usage instructions

Script syntax, Windows:
```
python cryptomap_converter.py [-k <api_key>] [-o <org_name>] [-f <file_name>] [-t <tag>]
```
 
Script syntax, Linux and Mac:
```
python3 cryptomap_converter.py [-k <api_key>] [-o <org_name>] [-f <file_name>] [-t <tag>]
```   
   
Optional arguments:
* `-k <api_key>`: Your Meraki Dashboard API key. If omitted, the script will try to use one stored in OS environment variable MERAKI_DASHBOARD_API_KEY
* `-o <org_name>`: The name of the organization to pull the OpenAPI spec from. This parameter can be omitted if your API key can only access one organization
* `-f <file_name>`: The name of the ASA configuration input file. If omitted, "asa.cfg" will be used as default
* `-t <tag>`: The name of the network tag you want to make the converted tunnels available to. If omitted, default availability is "All networks"
                        
Example, convert configuration stored in file "asa.cfg" into organization with name "Big Industries Inc" and
make it available to MXs in networks tagged "asa-vpn":
```
python cryptomap_converter.py -k 1234 -o "Big Industries Inc" -t asa-vpn
```
