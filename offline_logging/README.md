# offline_logging.py
A Python 3 script to log data from the Meraki dashboard into an external database periodically.

# The use case
This script is an example of how to cover use cases such as:
* A policy requiring data to be stored in a particular physical location, outside of the Meraki cloud
* A need for longer storage interval than what the Meraki cloud provides
* A need for storing regular timestamped snapshots of particular data

# Project overview
The project consists of a Python 3 script that interacts with a MongoDB database. While other types of deployment are also possible, the instructions in this document focus on how to install and integrate the script with a MongoDB Community Server running on the same server as the script. 

# Components
To use this project, you will need the following:
* A Meraki organization with API access enabled and a Dashboard API key: https://documentation.meraki.com/General_Administration/Other_Topics/Cisco_Meraki_Dashboard_API
* Python 3: https://www.python.org/downloads/
* The Python 3 Requests module: https://requests.readthedocs.io
* MongoDB. You can get the Community Server edition for free here: https://www.mongodb.com/try/download/community
* A tool to view your database. You can install MongoDB Compass along with the MongoDB Community Server

# Installation and startup
* Install Python 3. If installing on Windows, it is recommended to select the "Add to PATH" option during installation
* Install the Python 3 Requests module. The easiest way to do this is to run:
```
Windows:
pip install requests

Linux/Mac:
pip3 install requests
```
* Install MongoDB and MongoDB Compass
* Copy **offline_logging.py** and **config.yaml** into a folder on your server
* Open **config.yaml** with a text editor...
* ...find the **meraki_dashboard_api** section and modify the values for **api_key** and **organization_id** to match your environment. If you do not know your organizationId, you can use the interactive tools on this page to find it: https://developer.cisco.com/meraki/api-v1/#!get-organizations
* ...find the **sources** section and define which networks to include in scans. Networks can be included by name, id, network tag, or you can set the **include_all_networks** boolean flag to scan everything. Refer to the examples in the config file for the correct format
* ...find the **endpoints** section and see which items can be logged. Every item has a boolean attribute named **enabled** which can be used to turn the item on or off. To find out more about what exactly each item logs, search for its name on the Meraki Dashboard API documentation page: https://developer.cisco.com/meraki/api-v1/#!overview
* Save your changes to **config.yaml**
* Run the script:
```
Windows:
python offline_logging.py -c config.yaml

Linux/Mac:
python3 offline_logging.py -c config.yaml
```

# Verifying results
Use MongoDB Compass to view the contents of your database.

# Useful links
The official Meraki API developer page: https://developer.cisco.com/meraki
