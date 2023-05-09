import requests
import getpass
import csv
import json
import os
from colorama import Fore, Style, init

# Initialize colorama for Windows compatibility
init()

def print_welcome_message():
    print(f"\n{Fore.GREEN}Welcome to Meraki Secure Connect Private Applications Import Script{Style.RESET_ALL}")
    print(f"{Fore.GREEN}==================================================================={Style.RESET_ALL}\n")

def get_credentials():
    api_key = getpass.getpass('[1/2] Meraki API Key (MASKED): ')
    org_id = input('[2/2] Meraki Org ID: ')
    return api_key, org_id

# function `validate_csv_line` checks if the required fields "name", "destinationAddr1", "protocol", and "accessType" have values. 
# If any value is missing, the script will abort and print out an error message specifying the missing field and line number.

def validate_csv_line(line, line_number):
    required_fields = ["name", "destinationAddr1", "protocol", "accessType"]
    for field in required_fields:
        if not line[field]:
            print(f"{Fore.RED}Error: Missing value for '{field}' in line {line_number}.{Style.RESET_ALL}")
            return False
    return True

def read_csv_file(file_path):
    print("\n[x] Validating CSV file location")
    if not os.path.exists(file_path):
        print(f"{Fore.RED}Error: CSV file '{file_path}' does not exist.{Style.RESET_ALL}")
        return None

    print(f"{Fore.BLUE}[x] Executing Script{Style.RESET_ALL}")
    with open(file_path, mode='r') as csv_file:
        csv_reader = csv.DictReader(csv_file)
        payload_data_list = []
        for line_number, line in enumerate(csv_reader, start=1):
            if validate_csv_line(line, line_number):
                payload_data_list.append(line)
            else:
                return None
        return payload_data_list

def create_payload(payload_data):
    # Construct the payload from CSV data
    destinations = {
        "destinationAddr": [payload_data["destinationAddr1"]],
        "protocolPorts": [
            {
                "protocol": payload_data["protocol"],
                "ports": payload_data["ports"]
            }
        ],
        "accessType": payload_data["accessType"]
    }
    
    # This updates the `create_payload` function to conditionally include `payload_data["destinationAddr2"]` 
    # in the `destinationAddr` list only if it has a value. 
    # The script will ignore the "destinationAddr2" value if it has no value in the CSV file and process only the "destinationAddr1" value.
    # The same can be done with other values/keys.

    if payload_data["destinationAddr2"]:
        destinations["destinationAddr"].append(payload_data["destinationAddr2"])

    payload = {
        "name": payload_data["name"],
        "destinations": [destinations],
    }

    #  conditionally includes the fields "description", "appProtocol", "externalFQDN", "sni", "sslVerificationEnabled" and "applicationGroupIds"
    #  in the payload only if they have values in the CSV file. The script will ignore these values if they have no value in the CSV file.

    if payload_data["description"]:
        payload["description"] = payload_data["description"]

    if payload_data["appProtocol"]:
        payload["appProtocol"] = payload_data["appProtocol"]

    if payload_data["externalFQDN"]:
        payload["externalFQDN"] = payload_data["externalFQDN"]

    if payload_data["sni"]:
        payload["sni"] = payload_data["sni"]

    if payload_data["sslVerificationEnabled"]:
        payload["sslVerificationEnabled"] = payload_data["sslVerificationEnabled"].lower() == 'true'

    if payload_data["applicationGroupIds"]:
        payload["applicationGroupIds"] = [int(x) for x in payload_data["applicationGroupIds"].split(',')]

    return payload

def send_request(api_key, org_id, payload):
    # Send POST request to Meraki API and handle exceptions
    try:
        url = f"https://api.meraki.com/api/v1/organizations/{org_id}/secureConnect/privateApplications"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Cisco-Meraki-API-Key": api_key
        }
        response = requests.post(url, headers=headers, data=json.dumps(payload))
        response.raise_for_status()
        return response.json(), response.status_code
    except requests.exceptions.RequestException as e:
        print(f"{Fore.RED}Error: {e}{Style.RESET_ALL}")
        return None, None

def main():
    print_welcome_message()
    api_key, org_id = get_credentials()
    payload_data_list = read_csv_file('privateApplicationsImport.csv')

    if payload_data_list is None:
        print(f"{Fore.RED}Exiting the script.{Style.RESET_ALL}")
        return

    for index, payload_data in enumerate(payload_data_list, start=1):
        payload = create_payload(payload_data)
        output, status_code = send_request(api_key, org_id, payload)
        if output is not None and status_code is not None:
            print(f"\t{Fore.GREEN}[{index}] Success: Application '{output['name']}' with ID '{output['applicationId']}' created.{Style.RESET_ALL}")
        else:
            print(f"\t{Fore.YELLOW}[{index}] Skipping the current payload due to an error.{Style.RESET_ALL}")

if __name__ == "__main__":
    main()
