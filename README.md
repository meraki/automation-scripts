# automation-scripts

Meraki Dashboard API automation/migration scripts in Python
--------------------------------------

Here you can find Meraki Dashboard API scripts written for Python 3.

**NOTE: These scripts will not run in Python 2. Make sure you are using Python 3 with the appropriate commands for your operating system. You can check your Python version with command "python --version" in Windows and "python3 --version" in Linux/Mac.**

**IMPORTANT NOTE: Some of the older scripts in this repository use the Meraki Dashboard API v0, which is end of life and unsupported. If you are using a script written for v0 and want it converted to v1, please raise an issue about it.**

Check back from time to time, as new scripts are added and existing ones are sometimes polished and improved after initial posting. Please note that since the Meraki APIs are expanded constantly, there may be more efficient ways to complete a task than what was available when these scripts were created. For the latest info on Meraki APIs, visit: https://developer.cisco.com/meraki/whats-new/

Files contained in this repository:

**Installing Python on Windows.txt:** General info for installing Python 3 on Windows

**addroutes/addroutes.py:** Script to add static routes to a non-template network from a CSV file.

**android_patch_audit:** Script to check the date of the last security patch of Android devices managed by Meraki Systems Manager. It can generate a report of violating devices and trigger enforcement actions by applying tags to them.

**asa_cryptomap_converter/cryptomap_converter.py:** A Python 3 script to migrate crypto map based site-to-site VPN configuration to a Meraki MX security appliance. The VPN configuration will be ported as third-party VPN tunnels in the target Meraki Dashboard organization and associated with the chosen network tag.

**audit_client_tracking.py:** A script to check if the client tracking method in any of a set of networks is set to a value other than the one required.

**auto-cycle-port:** Checks if devices of a particular model are offline. If offline devices are found, specific switchports in the same network are cycled.

**auto_reboot:** Reboots devices with matching device tag once a week.

**autovpn_tunnel_count.py:** Counts how many VPN tunnels are consumed per network for establishing Auto VPN connectivity to peers.

**bssid.py:** Pulls the BSSID of the enabled SSID in a specified network, and puts them in a CSV.

**checksubnets.py:** This is a script to check if the LAN IPs (management addresses) of all access points in one or more organizations belong to specific IPv4 subnets. The purpose of the script is to find access points with misconfigured management addresses or VLANs, which may cause issues with 802.1x authentications. The output can be displayed on screen or sent as an email report.

**clientcount.py:** Script to count the total unique client MAC addresses connected to MR access points for an organization during the last month. Can be used as guidance when sizing systems that have per-user licensing, like the Cisco Identity Services Engine.

**clients_in_ip_range.py:** Prints a list of all clients in one or more organizations that belong to the specified IPv4 subnet or IPv4 address range. Can be used to check if a subnet is in use somewhere or to assess which clients will be affected by a proposed firewall rule change.

**cloneprovision.py:** Mass-provisions MX security appliances as individually managed networks, without using templates.

**copymxvlans.py:** This script can be used to export MX VLAN configuration of a source org to a file and import it to a destination org. The script will look for the exact same network names as they were in the source org. Use copynetworks.py and movedevices.py to migrate networks and devices if needed.

**copynetworks.py:** Copies networks and their base attributes from one organization to another. Does not move devices over or copy individual device configuration. Combined networks will be copied as "wireless switch appliance".

**copyswitchcfg.py:** This script can be used to export switchport configuration of a source org to a file and import it to a destination org. The script will look for the exact same network names and device serial numbers, as they were in the source org. Use copynetworks.py and movedevices.py to migrate networks and devices if needed.

**deployappliance.py:** This script claims a single Security Appliance or Teleworker Gateway into an organization, creates a new network for it and binds that network to an existing template.

**deploycustomer.py:** The intent of this script is to automate customer account/organization creation for service providers. The script needs a source organization that will be used for cloning (a "customer template"). This source organization needs to have a network configuration template, which will be used to configure devices. The script will optionally set street addresses for devices, network administration tags, as well as network timezone if provided with a Google Maps API key.

**deploydevices.py:** This script claims multiple devices and licenses into an organization, creates a new network for them and binds that network to an existing template. Initial config, including hostnames and street address/map markers are set for the devices. Will set network timezone to match street address if provided with a Google Maps API key.

**deviceupdownstatus.py:** Hybrid Dashboard API/SNMP script that prints a list of all devices in an organization's inventory, along with their current up/down status. Requires the Requests and PySNMP modules. Supports SNMPv2c and SNMPv3.

**find_clients.py:** Python 3 script that finds all clients with descriptions, MAC addresses or IP addresses including a query string and prints their basic statistics.

**find_ports.py:** This script finds all MS switchports that match the input search parameter, searching either by clients from a file listing MAC addresses (one per line), a specific tag in Dashboard currently applied to ports, or the specific access policy currently configured.

**firmware_lock/firmware_lock.py:** A Python 3 script to lock firmware for devices in an organization to desired builds or release trains. The script works by checking for scheduled firmware updates at defined intervals and delaying any that do not meet the desired criteria by a week if there is less than one week remaining before the update is scheduled to happen.

**getbeacons.py:** This script prints a list of all bluetooth beacons in an organization to terminal/sdtout or a file (Devices which are part of a network are considered in-use).

**get_license_info.py** Prints the license info summary for a specific organization or all organizations an admin has access to.

**googletimezonetest.py:** Example script that gets the time zone that corresponds to a street address by using Google Maps APIs. You can use this code to set network timezones dynamically in your Meraki Dashboard API scripts.

**inventorycsv.py:** Creates a list of all Meraki devices in one or all organizations accessible by an administrator. The primary purpose of the script is to create a CSV file, which can be opened and filtered with a spreadsheet editor, like Excel. The list can also be printed on screen instead.

**invlist.py:** Creates a list of all serial numbers and models of devices that are part of a Meraki network for an organization with a given name. Can print to Stdout or file. See inventorycsv.py for an improved solution for this use case.

**listip.py:** Almost exactly the same as invlist.py, but also prints the "lanIp" of the device. If the device has no "lanIp", it prints "None" for that field instead.

**manageadmins.py:** Add, delete, find and list administrators across organizations.

**merakidevicecounts.py:** Print total device counts per device family for all organizations accessed by your admin account, or a specific subset of organizations, as defined in a simple input file.

**merakilicensealert.py:** Script to send an email alert if the remaining license time in any org an admin has access to is less than X days, or if its license capacity is not sufficient for its current device count. The alert is sent using an SMTP server; by default Gmail. Use an automation platform like Zapier to read this email and trigger further actions. The intent of the script is to get email alerts earlier than 30 days before license expiration.

**mi_bom_tool.py:** Script that counts the numbers and sizes of Meraki Insight licenses needed to cover a set of networks in an organization. The intent is to make assessment of potential upgrade investments easier.

**migrate_cat3k:** Proof of concept script to migrate switchport configuration from Catalyst 3750-X switches to Meraki MS switches. Uses action batches for better scalability.

**migratecomware.py:** Proof of concept script that migrates legacy switch infrastructure based on Comware (HPE A-series) to Meraki MS switches. Comware switch configurations can be provided as files, or by entering the IP address and SSH credentials of the source device. A valid initialization configuration file must be provided, where source devices are mapped to target Meraki serial numbers. Please see migration_init_file.txt in this repository for an example of such a file. This version of the script only supports Comware-based switches and a limited set of Layer 2 switchport commands. The script could be expanded to cover more commands and other CLI-based switch families.

**migration_init_file.txt:** Example init config file for migratecomware.py.

**movedevices.py:** This script that can be used to move all devices from one organization to another. The script will only process devices that are part of a network. The networks of the source org need to exist in the destination org too. Use copynetworks.py if needed to create them.

**mx_fwrules_to_csv.py:** A simple example showing how to use the Meraki Dashboard API library to GET MX L3 firewall rules from a provided network and output to CSV.

**mx_firewall_control/mxfirewallcontrol.py:** Script to display, modify and create backups of MX Layer 3 firewall rulesets. Can be used as a command line utility or a backend process for a custom management portal. See also mxfirewallcontrol_manual.pdf and mxfirewallcontrol_example_input_file.txt in this directory.

**mx_firewall_control/mxfirewallcontrol_example_input_file.txt:** Example input file for mxfirewallcontrol.py.

**nodejs_sdk_builder:** Python 3 script that builds a NodeJS SDK for the Meraki Dashboard API by calling the current OpenAPI specification and combining two code template files. 

**offline_logging:** A Python 3 script to log data from the Meraki dashboard to a MongoDB database. Currently focused on logging client activity.

**orgclientscsv.py:** A script to create a CSV file with all of the client devices in an organization. The CSV file will be created in the same folder where this script is located. The script makes no attempt to remove or combine duplicate entries. If you see the same client being reported several times, this is typically an indication of a client that has been moving.

**org_subnets.py:** Prints a list of all subnets configured to MX security appliances as VLANs, static routes or VPN advertisements.

**postman_collection_generator.py:** A script to create a Postman collection for the Meraki Dashboard API v1. The collection is created by fetching the OpenAPI 2.0 specification of a Meraki dashboard organization. Items will created for all endpoints available to that organization, including possible alpha/beta ones.

**provision_sites:** A Python 3 script to provision template-based networks with manually defined VLAN subnets to Meraki dashboard. The script can also claim devices and update their location on the world map.

**removetemplate.py:** This is script to create a copy of a template-based network that preserves as many of the network's settings as possible, while not relying on a configuration template. The initial focus of the script is converting MX appliance networks.

**set_client_tracking.py:** A script to set the client tracking method of a group of networks to a desired value.

**setlocation.py:** Sets the street address and optionally the map marker of all devices in a network or organization. To be more easily clickable, devices will be placed in a spiral around a seed location. There is an option to preserve marker location for MR access points, to avoid breaking wireless map layout.

**setlocation_legacy.py:** Sets the street address of all devices in a given network to a given value. The intent of this script is to quickly fix address misconfigurations on large networks. The script has been updated from its initial version to use the Google Geocoding API to calculate a reasonable new positions for device map markers. This is a legacy script that is preserved as an example of integrating the Meraki Dashboard API with info extracted from a Google API. Please see setlocation.py for an improved version of the script that does not require a Google API key.

**setssidvlanid.py:** Sets the VLAN ID of SSIDs in 'Layer 3 with concentrator' or 'VPN' mode to a value.

**setSwitchPortOnMacOui.py:** This is a script to set attributes of a switch port, if a client with a matching MAC OUI is found connected to it. This script uses two endpoints that were in Beta at time of writing: "List the clients that have used this network in the timespan" and "Action batches". The use case is to provision easily provision switchport settings for IP phones of the same vendor. The script has a protective lock to only attempt to configure ports on MS1xx, MS2xx and MS3xx switches.

**tag_all_ports.py:** Tags all MS switch ports in an organization with a user-defined tag.

**topusers:** Finds bandwidth hoggers in a network through a web UI.

**update_ports.py:** This script finds all MS switchports that match the input search parameter, searching either by clients from a file listing MAC addresses (one per line), a specific tag in Dashboard currently applied to ports, or the specific access policy currently configured. It then changes the configuration of the port by applying the new access policy specified.

**uplink.py:** Iterates through all devices, and exports to two CSV files: one for appliance (MX, Z1, Z3, vMX100) networks to collect WAN uplink information, and the other for all other devices (MR, MS, MC, MV) with local uplink info.
Possible statuses:
- Active: active and working WAN port
- Ready: standby but working WAN port, not the preferred WAN port
- Failed: was working at some point but not anymore
- Not connected: nothing was ever connected, no cable plugged in
- (For load balancing, both WAN links would show active.)

**usagestats.py:** Produces reports on per user group network usage. User groups are identified by subnet, VLAN ID or VLAN name. The script combines the Meraki Dashboard API with a SQLite3 database and sending HTML-formatted emails. See also usagestats_initconfig.txt and usagestats_manual.pdf in this folder.

**usagestats_initconfig.txt:** Example initial configuration file for usagestats.py

**usagestats_manual.pdf:** Manual for usagestats.py


More info about the scripts can be found inline as comments.
