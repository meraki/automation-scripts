# Meraki Secure Connect Private Applications Import Script

This Python script helps you to import Meraki Secure Connect private applications from a CSV file into your Meraki Dashboard. It automates the process of creating private applications with various configurations.

## Features

- Imports private applications from a CSV file into your Meraki Dashboard
- Validates CSV file format and content
- Skips unnecessary fields if they have no value in the CSV file
- Aborts the script and provides an error message if required fields are missing

## Requirements

- Python 3.x
- `requests` library
- `colorama` library

To install required libraries, run:

```bash
pip3 install requests colorama
```

## Usage

1. Clone or download the repository.
2. Prepare a CSV file containing private application data following the format specified below.
3. Run the script:

```bash
python3 meraki_private_app_import.py
```

4. Follow the prompts to enter your Meraki API key and organization ID.
5. The script will validate the CSV file and import the private applications into your Meraki Dashboard.

## CSV File Format

The CSV file should have the following columns:

- `name` (required): Name of the private application
- `description`: Description of the private application
- `destinationAddr1` (required): First destination IP address or subnet
- `destinationAddr2`: Second destination IP address or subnet (optional)
- `protocol` (required): Protocol for the private application (TCP or UDP)
- `ports`: Ports for the private application
- `accessType` (required): Access type for the private application (Allowed or Denied)
- `appProtocol`: Application protocol
- `externalFQDN`: External FQDN for the private application
- `sni`: SNI for the private application
- `sslVerificationEnabled`: Enable SSL verification (True or False)
- `applicationGroupIds`: Comma-separated list of application group IDs

Example CSV file:

```
name,description,destinationAddr1,destinationAddr2,protocol,ports,accessType,appProtocol,sni,externalFQDN,sslVerificationEnabled,applicationGroupIds
Jira TEST-1,Jira App For My Org.1,142.6.0.0/32,192.168.1.10/32,TCP,80-82,browser,https,xyz123.jira1.com,https://jira1-5001.ztna.ciscoplus.com,TRUE,"83, 114"
Jira TEST-2,Jira App For My Org.2,152.6.0.0/32,192.168.1.20/32,TCP,80-82,browser,https,xyz123.jira2.com,https://jira2-5001.ztna.ciscoplus.com,TRUE,"83, 114"
Jira TEST-3,Jira App For My Org.3,162.6.0.0/32,192.168.1.30/32,TCP,80-82,browser,https,xyz123.jira3.com,https://jira3-5001.ztna.ciscoplus.com,TRUE,"83, 114"
Jira TEST-4,Jira App For My Org.4,172.6.0.0/32,192.168.1.40/32,UDP,80-82,network,https,xyz123.jira4.com,https://jira4-5001.ztna.ciscoplus.com,FALSE,"83, 114"
Jira TEST-5,Jira App For My Org.5,182.6.0.0/32,192.168.1.50/32,UDP,80-82,network,https,xyz123.jira5.com,https://jira5-5001.ztna.ciscoplus.com,FALSE,"83, 114"
Jira TEST-6,,192.6.0.0/32,,TCP,80,network,,,,,
```

## Maintainers & Contributors

[Yossi Meloch](mailto:ymeloch@cisco.com)

## Acknowledgements

- [Cisco Meraki](https://www.meraki.com/) for providing a robust and easy-to-use API

Please note that this script is provided "as is" without warranty of any kind, either expressed or implied, including limitation warranties of merchantability, fitness for a particular purpose, and noninfringement. Use at your own risk.