#!/usr/bin/python3

"""
=== PREREQUISITES ===
Run in Python 3.6+

Install Meraki Python library: pip[3] install --upgrade meraki

=== DESCRIPTION ===
This script reports the org-wide appliances' uplink and devices's statuses.

=== USAGE ===
python[3] report_statuses.py -k <api_key> -o <org_id>

Use "-o /all" to iterate through all organizations
"""


import argparse
import csv
import meraki


def parse_arguments(parser):
    parser.add_argument('-k', '--key', help='Dashboard API key')
    parser.add_argument('-o', '--org', help='Organization ID. Use "-o /all" to iterate through all organizations')
    parser.exit
    args = parser.parse_args()
    return args.key, args.org


def main():
    # Check if all required parameters have been specified
    parser = argparse.ArgumentParser()
    api_key, arg_org_id = parse_arguments(parser)

    if not(api_key and arg_org_id):
        parser.exit(2, parser.print_help())

    # Make API calls to retrieve data
    dashboard = meraki.DashboardAPI(api_key)
    
    org_id_list = []
    flag_multi_org = False
    if arg_org_id == '/all':
        flag_multi_org = True
        orgs_result = dashboard.organizations.getOrganizations()
        for org in orgs_result:
            org_id_list.append(org['id'])
    else:
        org_id_list.append(arg_org_id)
    
    for org_id in org_id_list:
        try:
            appliance_statuses = dashboard.appliance.getOrganizationApplianceUplinkStatuses(org_id, total_pages='all')
            device_statuses = dashboard.organizations.getOrganizationDevicesStatuses(org_id, total_pages='all')
            networks = dashboard.organizations.getOrganizationNetworks(org_id, total_pages='all')
        except Exception as e:
            print(str(e))
            continue
        devices_by_serial = {d['serial']: d['name'] for d in device_statuses}
        networks_by_id = {n['id']: n['name'] for n in networks}

        # Output appliance statuses file
        output_file = 'appliance_statuses'
        if flag_multi_org:
            output_file += '_' + org_id
        output_file += '.csv'
        field_names = ['name', 'serial', 'model', 'network', 'networkId', 'lastReportedAt',
                       'wan1_status', 'wan1_ip', 'wan1_gateway', 'wan1_publicIp', 'wan1_primaryDns', 'wan1_secondaryDns',
                       'wan1_ipAssignedBy', 'wan2_status', 'wan2_ip', 'wan2_gateway', 'wan2_publicIp', 'wan2_primaryDns', 
                       'wan2_secondaryDns', 'wan2_ipAssignedBy', 'cellular_status', 'cellular_ip', 'cellular_provider', 
                       'cellular_publicIp', 'cellular_model', 'cellular_signalStat', 'cellular_connectionType', 'cellular_apn']
        with open(output_file, mode='w', newline='\n') as fp:
            csv_writer = csv.DictWriter(fp, field_names, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
            csv_writer.writeheader()
            for status in appliance_statuses:
                status.update(
                    {
                        'name': devices_by_serial[status['serial']],
                        'network': networks_by_id[status['networkId']]
                    }
                )

                # Flatten objects/dictionaries, without requiring a third-party library
                interfaces = [uplink['interface'] for uplink in status['uplinks']]
                if 'wan1' in interfaces:
                    wan1 = status['uplinks'][interfaces.index('wan1')]
                    status.update(
                        {
                            'wan1_status': wan1['status'],
                            'wan1_ip': wan1['ip'],
                            'wan1_gateway': wan1['gateway'],
                            'wan1_publicIp': wan1['publicIp'],
                            'wan1_primaryDns': wan1['primaryDns'],
                            'wan1_secondaryDns': wan1['secondaryDns'],
                            'wan1_ipAssignedBy': wan1['ipAssignedBy']
                        }
                    )
                if 'wan2' in interfaces:
                    wan2 = status['uplinks'][interfaces.index('wan2')]
                    status.update(
                        {
                            'wan2_status': wan2['status'],
                            'wan2_ip': wan2['ip'],
                            'wan2_gateway': wan2['gateway'],
                            'wan2_publicIp': wan2['publicIp'],
                            'wan2_primaryDns': wan2['primaryDns'],
                            'wan2_secondaryDns': wan2['secondaryDns'],
                            'wan2_ipAssignedBy': wan2['ipAssignedBy']
                        }
                    )
                if 'cellular' in interfaces:
                    cellular = status['uplinks'][interfaces.index('cellular')]
                    status.update(
                        {
                            'cellular_status': cellular['status'],
                            'cellular_ip': cellular['ip'],
                            'cellular_provider': cellular['provider'],
                            'cellular_publicIp': cellular['publicIp'],
                            'cellular_model': cellular['model'],
                            'cellular_signalStat': cellular['signalStat'],
                            'cellular_connectionType': cellular['connectionType'],
                            'cellular_apn': cellular['apn']
                        }
                    )
                status.pop('uplinks')
                #print(status)
                csv_writer.writerow(status)

        # Output device statuses file
        output_file = 'device_statuses'
        if flag_multi_org:
            output_file += '_' + org_id
        output_file += '.csv'
        field_names = ['name', 'serial', 'network', 'networkId', 'mac', 'publicIp', 'status', 'lastReportedAt', 'lanIp', 'gateway', 'ipType', 'primaryDns', 'secondaryDns',
                       'usingCellularFailover', 'wan1Ip', 'wan1Gateway', 'wan1IpType', 'wan1PrimaryDns', 'wan1SecondaryDns', 'wan2Ip', 'wan2Gateway', 'wan2IpType', 'wan2PrimaryDns', 'wan2SecondaryDns']
        with open(output_file, mode='w', newline='\n') as fp:
            csv_writer = csv.DictWriter(fp, field_names, delimiter=',', quotechar='"', quoting=csv.QUOTE_ALL)
            csv_writer.writeheader()
            for status in device_statuses:
                status.update({'network': networks_by_id[status['networkId']]})
                csv_writer.writerow(status)


if __name__ == '__main__':
    main()
