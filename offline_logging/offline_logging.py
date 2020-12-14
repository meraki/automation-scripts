read_me = """Python 3 script that logs data from the Meraki dashboard into a MongoDB database.
You will need to have MongoDB installed and supply a configuration file for this script to run.
You can get the MongoDB Community Server here: https://www.mongodb.com/try/download/community
You can find a sample configuration file here: **INSERT GITHUB LINK**

Script syntax:
    python offline_logging.py -c <config_file>

Required Python 3 modules:
    meraki
    pyyaml
    pymongo
    
To install these Python 3 modules via pip you can use the following commands:
    pip install meraki
    pip install pyyaml
    pip install pymongo
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
 
View the created database with a MongoDB viewing tool such as MongoDB Compass: 
 https://www.mongodb.com/products/compass
 A version of MongoDB Compass can be installed with the MongoDB Community Server. 
"""

import sys, getopt, yaml, time, datetime, meraki, pymongo

def kill_script():
    print(read_me)
    sys.exit(2)


def load_config(p_file):

    config = None

    with open(p_file) as file:
        config = yaml.load(file, Loader=yaml.FullLoader)

    return config
    
    
def filter_networks(config_sources, networks):
    result = []
    
    if config_sources['include_all_networks']:
        return networks
    
    for net in networks:
        found_match = False
        if not config_sources['network_names'] is None:
            if net['name'] in config_sources['network_names']:
                result.append(net)
                found_match = True
                print ('match name ' + net['name'])
        if not found_match:
            if not config_sources['network_ids'] is None:
                if net['id'] in config_sources['network_ids']:
                    result.append(net)
                    found_match = True
                    print ('match id ' + net['id'])
            if not found_match:
                if not config_sources['network_tags'] is None:
                    for tag in config_sources['network_tags']:
                        if tag in net['tags']:
                            result.append(net)
                            break
    return result
    
    
def log_to_database(db, document, collection, mode):
    dbc = db[collection]
    try:
        dbc.insert_one(document)
    except:
        print("ERROR: Could not create document in database")
      
    
def perform_scan(config, api):
    print(str(datetime.datetime.now()) + " -- Starting scan")
    
    all_networks = api.organizations.getOrganizationNetworks(config['meraki_dashboard_api']['organization_id'])    
    filtered_networks = filter_networks(config['sources'], all_networks)
    
    mongo_client = pymongo.MongoClient("mongodb://" + config['mongodb']['host'] + ":" + str(config['mongodb']['port']) + "/")    
    db = mongo_client[config['mongodb']['database_name']]
    
    clients = None
    
    for network in filtered_networks:    
        if 'getNetworkClients' in config['endpoints'] and config['endpoints']['getNetworkClients']['enabled']:
            try:
                clients = api.networks.getNetworkClients(network['id'], 
                        timespan=config['scan_interval_minutes']*60)
            except:
                print("ERROR: Cloud not fetch clients for net %s" % network['id'])
                continue
            scan_time = datetime.datetime.now()
            for client in clients:
                document = client
                document['scanTime'] = scan_time
                document['scanIntervalMinutes'] = config['scan_interval_minutes']
                document['networkId'] = network['id']
                document['networkName'] = network['name']
                log_to_database(db, document, config['endpoints']['getNetworkClients']['collection'],
                    config['endpoints']['getNetworkClients']['mode'])
        if 'getNetworkClientsApplicationUsage' in config['endpoints'] and config['endpoints']['getNetworkClientsApplicationUsage']['enabled']:
            if clients is None:
                print("ERROR: Client getNetworkClients must be enabled for getNetworkClientsApplicationUsage")
            else:
                client_list = ""
                for client in clients:
                    if client_list != "":
                        client_list += ","
                    client_list += client['id']
                
                try:
                    usage = api.networks.getNetworkClientsApplicationUsage(network['id'], client_list, 
                            timespan=config['scan_interval_minutes']*60)
                except:
                    print("ERROR: Cloud not fetch clients' usage for net %s" % network['id'])
                    continue
                
                scan_time = datetime.datetime.now()                
                for item in usage:
                    document = item
                    document['scanTime'] = scan_time
                    document['scanIntervalMinutes'] = config['scan_interval_minutes']
                    document['networkId'] = network['id']
                    document['networkName'] = network['name']
                    log_to_database(db, document, config['endpoints']['getNetworkClientsApplicationUsage']['collection'],
                        config['endpoints']['getNetworkClientsApplicationUsage']['mode'])
                            
    print(str(datetime.datetime.now()) + " -- Scan complete")


def main(argv):
    arg_config_file = None
    
    try:
        opts, args = getopt.getopt(argv, 'c:')
    except getopt.GetoptError:
        sys.exit(2)
        
    for opt, arg in opts:
        if opt == '-c':
            arg_config_file = arg
            
    if arg_config_file is None:
        kill_script()
    
    try:
        config = load_config(arg_config_file)
        print(str(datetime.datetime.now()) + " -- Initializing script with configuration:")
        print(config)
    except:
        kill_script()
            
    dashboard = meraki.DashboardAPI(config['meraki_dashboard_api']['api_key'], output_log=False)
    
    while(True):
        perform_scan(config, dashboard)
        print(str(datetime.datetime.now()) + " -- Next scan in " + str(config['scan_interval_minutes']) + " minutes")
        time.sleep(config['scan_interval_minutes']*60)

if __name__ == '__main__':
    main(sys.argv[1:])