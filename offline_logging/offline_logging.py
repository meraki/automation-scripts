read_me = """Python 3 script that logs data from the Meraki dashboard into a MongoDB database.
You will need to have MongoDB installed and supply a configuration file for this script to run.
You can get the MongoDB Community Server here: https://www.mongodb.com/try/download/community
You can find a sample configuration file here: 
  https://github.com/meraki/automation-scripts/blob/master/offline_logging/config.yaml

Script syntax:
    python offline_logging.py -c <config_file>

Required Python 3 modules:
    requests
    pyyaml
    pymongo
    
To install these Python 3 modules via pip you can use the following commands:
    pip install requests
    pip install pyyaml
    pip install pymongo
    
Depending on your operating system and Python environment, you may need to use commands 
 "python3" and "pip3" instead of "python" and "pip".
 
View the created database with a MongoDB viewing tool such as MongoDB Compass: 
 https://www.mongodb.com/products/compass
 A version of MongoDB Compass can be installed with the MongoDB Community Server. 
"""

import sys, getopt, yaml, time, datetime, pymongo

from urllib.parse import urlencode
from requests import Session, utils

class NoRebuildAuthSession(Session):
    def rebuild_auth(self, prepared_request, response):
        """
        This method is intentionally empty. Needed to prevent auth header stripping on redirect. More info:
        https://stackoverflow.com/questions/60358216/python-requests-post-request-dropping-authorization-header
        """

API_MAX_RETRIES         = 3
API_CONNECT_TIMEOUT     = 60
API_TRANSMIT_TIMEOUT    = 60
API_STATUS_RATE_LIMIT   = 429

#Set to True or False to enable/disable console logging of sent API requests
FLAG_REQUEST_VERBOSE    = True

#change this to "https://api.meraki.com/api/v1" to disable mega proxy
API_BASE_URL            = "https://api-mp.meraki.com/api/v1"


def merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders=None, p_queryItems=None, 
        p_requestBody=None, p_verbose=False, p_retry=0):
    #returns success, errors, responseHeaders, responseBody
    
    if p_retry > API_MAX_RETRIES:
        if(p_verbose):
            print("ERROR: Reached max retries")
        return False, None, None, None

    bearerString = "Bearer " + p_apiKey
    headers = {"Authorization": bearerString}
    if not p_additionalHeaders is None:
        headers.update(p_additionalHeaders)
        
    query = ""
    if not p_queryItems is None:
        query = "?" + urlencode(p_queryItems)
    url = API_BASE_URL + p_endpoint + query
    
    verb = p_httpVerb.upper()
    
    session = NoRebuildAuthSession()

    try:
        if(p_verbose):
            print(verb, url)
        if verb == "GET":
            r = session.get(
                url,
                headers =   headers,
                timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
            )
        elif verb == "PUT":
            if not p_requestBody is None:
                if (p_verbose):
                    print("body", p_requestBody)
                r = session.put(
                    url,
                    headers =   headers,
                    json    =   p_requestBody,
                    timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
                )
        elif verb == "POST":
            if not p_requestBody is None:
                if (p_verbose):
                    print("body", p_requestBody)
                r = session.post(
                    url,
                    headers =   headers,
                    json    =   p_requestBody,
                    timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
                )
        elif verb == "DELETE":
            r = session.delete(
                url,
                headers =   headers,
                timeout =   (API_CONNECT_TIMEOUT, API_TRANSMIT_TIMEOUT)
            )
        else:
            return False, None, None, None
    except:
        return False, None, None, None
    
    if(p_verbose):
        print(r.status_code)
    
    success         = r.status_code in range (200, 299)
    errors          = None
    responseHeaders = None
    responseBody    = None
    
    if r.status_code == API_STATUS_RATE_LIMIT:
        if(p_verbose):
            print("INFO: Hit max request rate. Retrying %s after %s seconds" % (p_retry+1, r.headers["Retry-After"]))
        time.sleep(int(r.headers["Retry-After"]))
        success, errors, responseHeaders, responseBody = merakiRequest(p_apiKey, p_httpVerb, p_endpoint, p_additionalHeaders, 
            p_queryItems, p_requestBody, p_verbose, p_retry+1)
        return success, errors, responseHeaders, responseBody        
            
    try:
        rjson = r.json()
    except:
        rjson = None
        
    if not rjson is None:
        if "errors" in rjson:
            errors = rjson["errors"]
            if(p_verbose):
                print(errors)
        else:
            responseBody = rjson  

    if "Link" in r.headers:
        parsedLinks = utils.parse_header_links(r.headers["Link"])
        for link in parsedLinks:
            if link["rel"] == "next":
                if(p_verbose):
                    print("Next page:", link["url"])
                splitLink = link["url"].split("/api/v1")
                success, errors, responseHeaders, nextBody = merakiRequest(p_apiKey, p_httpVerb, splitLink[1], 
                    p_additionalHeaders=p_additionalHeaders, 
                    p_requestBody=p_requestBody, 
                    p_verbose=p_verbose)
                if success:
                    if not responseBody is None:
                        responseBody.append(nextBody)
                else:
                    responseBody = None
    
    return success, errors, responseHeaders, responseBody
    
    
def getNetworks(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/networks" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
   
def getClients(p_apiKey, p_networkId, p_timespan):
    endpoint = "/networks/%s/clients" % p_networkId
    query = {"timespan": p_timespan}
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getApplicationUsage(p_apiKey, p_networkId, p_clientsStr, p_timespan):
    endpoint = "/networks/%s/clients/applicationUsage" % p_networkId
    query = {"clients": p_clientsStr, "timespan": p_timespan}
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_queryItems=query, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getClientTrafficHistory(p_apiKey, p_networkId, p_clientId):
    endpoint = "/networks/%s/clients/%s/trafficHistory" % (p_networkId, p_clientId)
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getNetworkMerakiAuthUsers(p_apiKey, p_networkId):
    endpoint = "/networks/%s/merakiAuthUsers" % p_networkId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    
    
def getOrganizationAdmins(p_apiKey, p_organizationId):
    endpoint = "/organizations/%s/admins" % p_organizationId
    success, errors, headers, response = merakiRequest(p_apiKey, "GET", endpoint, p_verbose=FLAG_REQUEST_VERBOSE)    
    return success, errors, headers, response
    

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
    
    
def filter_admins(p_admins, p_networks, p_tags):
    # Return admin if they have org access, or net/tag access to an item matching filters
    
    result = []
    for admin in p_admins:
        include_admin = False
        if admin['orgAccess'] != 'none':
            include_admin = True
        else:
            for anet in admin['networks']:
                for onet in p_networks:
                    if anet['id'] == onet['id']:
                        include_admin = True
                        break
                if include_admin:
                    break
            if not include_admin:
                for atag in admin['tags']:
                    if atag['tag'] in p_tags:
                        include_admin = True
                        break                        
        if include_admin:
            result.append(admin)
    return result
    
    
def log_to_database(db, document, collection, mode, keyValuePair=None):
    dbc = db[collection]
    
    if mode == 'append':
        try:
            dbc.insert_one(document)
        except:
            print("ERROR: Could not create document in database")
    elif mode == 'update':
        try:
            dbc.update_one(keyValuePair, {"$set": document}, upsert=True)
        except:
            print("ERROR: Could not update document in database")
      
    
def perform_scan(config):
    print(str(datetime.datetime.now()) + " -- Starting scan")
    
    api_key         = config['meraki_dashboard_api']['api_key']
    org_id          = config['meraki_dashboard_api']['organization_id']
    scan_interval   = config['scan_interval_minutes']*60
    
    success, errors, headers, all_networks = getNetworks(api_key, org_id)
    
    if not success:
        print("ERROR: Unable to get networks' list")
    else:
        filtered_networks = filter_networks(config['sources'], all_networks)
        
        mongo_client = pymongo.MongoClient("mongodb://" + config['mongodb']['host'] + ":" + str(config['mongodb']['port']) + "/")    
        db = mongo_client[config['mongodb']['database_name']]
        
        clients = None
        
        if 'getOrganizationAdmins' in config['endpoints'] and config['endpoints']['getOrganizationAdmins']['enabled']:
            success, errors, headers, all_admins = getOrganizationAdmins(api_key, org_id)
            if not all_admins is None:
                admins = filter_admins(all_admins, filtered_networks, config['sources']['network_tags'])
                for admin in admins:
                    log_to_database(db, admin, config['endpoints']['getOrganizationAdmins']['collection'],
                            config['endpoints']['getOrganizationAdmins']['mode'], 
                            keyValuePair={'id': admin['id']})
        
        for network in filtered_networks:    
            if 'getNetworkClients' in config['endpoints'] and config['endpoints']['getNetworkClients']['enabled']:
                success, errors, headers, clients = getClients(api_key, network['id'], scan_interval)
                if clients is None:
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
                    
                    success, errors, headers, usage = getApplicationUsage(api_key, network['id'], client_list, scan_interval)
                    
                    if usage is None:
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
            if 'getNetworkClientTrafficHistory' in config['endpoints'] and config['endpoints']['getNetworkClientTrafficHistory']['enabled']:
                if clients is None:
                    print("ERROR: Client getNetworkClients must be enabled for getNetworkClientTrafficHistory")
                else:
                    for client in clients:
                        success, errors, headers, traffic_history = getClientTrafficHistory(api_key, network['id'], client['id'])
                        document = {
                            'clientId': client['id'],
                            'networkId': network['id'],
                            'networkName': network['name'],
                            'scanTime': scan_time,
                            'scanIntervalMinutes': config['scan_interval_minutes']
                        }
                        document['trafficHistory'] = traffic_history
                        log_to_database(db, document, config['endpoints']['getNetworkClientTrafficHistory']['collection'],
                            config['endpoints']['getNetworkClientTrafficHistory']['mode'], keyValuePair={'clientId': client['id']})   
            if 'getNetworkMerakiAuthUsers' in config['endpoints'] and config['endpoints']['getNetworkMerakiAuthUsers']['enabled']:
                success, errors, headers, auth_users = getNetworkMerakiAuthUsers(api_key, network['id'])
                if 'configTemplateId' in network and config['endpoints']['getNetworkMerakiAuthUsers']['include_template_users']:
                    success, errors, headers, template_users = getNetworkMerakiAuthUsers(api_key, network['configTemplateId'])
                    if not template_users is None:
                        if not auth_users is None:
                            auth_users += template_users
                        else:
                            auth_users = template_users
                if not auth_users is None:
                    for user in auth_users:
                        document = user 
                        document['networkId'] = network['id']
                        log_to_database(db, document, config['endpoints']['getNetworkMerakiAuthUsers']['collection'],
                            config['endpoints']['getNetworkMerakiAuthUsers']['mode'], 
                            keyValuePair={'id': user['id'], 'networkId': network['id']})
            
                    
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
        print(str(datetime.datetime.now()) + " -- Initializing script")
    except:
        kill_script()
                
    while(True):
        perform_scan(config)
        print(str(datetime.datetime.now()) + " -- Next scan in " + str(config['scan_interval_minutes']) + " minutes")
        time.sleep(config['scan_interval_minutes']*60)

if __name__ == '__main__':
    main(sys.argv[1:])