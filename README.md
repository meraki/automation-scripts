# meraki-python
Meraki Dashboard API scripts in Python
--------------------------------------

Here you can find Meraki Dashboard API scripts written for Python 3.

Files contained in this repository:

**Installing Python on Windows.txt:** General info for installing Python 3 on Windows

**copymxvlans.py:** This script can be used to export MX VLAN configuration of a source org to a file and import it to a destination org. The script will look for the exact same network names as they were in the source org. Use copynetworks.py and movedevices.py to migrate networks and devices if needed.

**copynetworks.py:** Copies networks and their base attributes from one organization to another. Does not move devices over or copy individual device configuration. Combined networks will be copied as "wireless switch appliance".

**copyswitchcfg.py:** This script can be used to export switchport configuration of a source org to a file and import it to a destination org. The script will look for the exact same network names and device serial numbers, as they were in the source org. Use copynetworks.py and movedevices.py to migrate networks and devices if needed.

**deployappliance.py:** This script claims a single Security Appliance or Teleworker Gateway into an organization, creates a new network for it and binds that network to an existing template.

**deploydevices.py:** This script claims multiple devices and licenses into an organization, creates a new network for them and binds that network to an existing template. Initial config, including hostnames and street address/map markers are set for the devices.

**invlist.py:** Creates a list of all serial numbers and models of devices that are part of a Meraki network for an organization with a given name. Can print to Stdout or file.

**listip.py:** Almost exactly the same as invlist.py, but also prints the "lanIp" of the device. If the device has no "lanIp", it prints "None" for that field instead.

**movedevices.py:** This script that can be used to move all devices from one organization to another. The script will only process devices that are part of a network. The networks of the source org need to exist in the destination org too. Use copynetworks.py if needed to create them.

**setlocation.py:** Sets the street address and optionally the map marker of all devices in a network or organization. To be more easily clickable, devices will be placed in a spiral around a seed location. There is an option to preserve marker location for MR access points, to avoid breaking wireless map layout.

**setlocation_legacy.py:** Sets the street address of all devices in a given network to a given value. The intent of this script is to quickly fix address misconfigurations on large networks. The script has been updated from its initial version to use the Google Geocoding API to calculate a reasonable new positions for device map markers. This is a legacy script that is preserved as an example of integrating the Meraki Dashboard API with info extracted from a Google API. Please see setlocation.py for an improved version of the script that does not require a Google API key.

More info about the scripts can be found inline as comments.
