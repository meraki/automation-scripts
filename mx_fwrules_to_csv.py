import csv
# if the meraki library is installed via pip, use the import line below:
from meraki import meraki

api_key = 'insert api key here'
net_id = 'insert net id here'
org_id = 'insert org id here'

# Set the CSV output file and write a header row
output_file = open('mx_fw_rules.csv', mode='w')
csv_writer = csv.writer(output_file, escapechar=' ', quoting=csv.QUOTE_NONE)
header_row_text = "Comment, Policy, Protocol, Source Port, Source CIDR, Destination Port, Destination CIDR, Syslog Enabled ?"
csv_writer.writerow([header_row_text])

# use the getmxl3fwrules function in the meraki dashboard api library 
fw_rules = meraki.getmxl3fwrules(api_key,net_id)
print("^^^ Full output:", fw_rules)

# loop through each firewall rule, create a csv row and write to file
for rule in fw_rules:
    print("@@@ Print each rule from the GET response:", str(rule))
    csv_row = "{0},{1},{2},{3},{4},{5},{6},{7}".format(rule['comment'], rule['policy'], rule['protocol'], rule['srcPort'], rule['srcCidr'], rule['destPort'], rule['destCidr'], rule['syslogEnabled'])
    print("### Writing this row to CSV:", csv_row)
    csv_writer.writerow([csv_row])

output_file.close()
