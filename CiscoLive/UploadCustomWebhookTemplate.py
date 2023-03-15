# this script, for a given
# - API key
# - NetworkID
# - Webhook Template Name
# creates a new custom webhook template
# API information available here: https://developer.cisco.com/meraki/webhooks/#!custom-payload-templates-overview
# precreated templates available here: https://github.com/meraki/webhook-payload-templates
# further training available here: https://developer.cisco.com/learning/labs/meraki-webhook-template-editor-intro/create-your-custom-webhook-template/
# postman collection: https://www.postman.com/meraki-api/workspace/cisco-meraki-s-public-workspace/collection/897512-c65299ed-39a5-4b02-bb4e-933c738bfcdf?action=share&creator=897512&ctx=documentation

import sys, requests, json, getopt


def main(argv):
    ARG_APIKEY = ''
    ARG_NAME = ''
    ARG_NETWORKID = ''

    try:
        opts, args = getopt.getopt(argv, 'hk:n:i:')
    except getopt.GetoptError:
        printhelp()
        sys.exit(2)

    for opt, arg in opts:
        if opt == '-h':
            printhelp()
            sys.exit()
        elif opt == '-k':
            ARG_APIKEY = arg
        elif opt == '-n':
            ARG_NETWORKID = arg
        elif opt == '-i':
            ARG_NAME = arg

        # check that all mandatory arguments have been given
    if ARG_APIKEY == '' or ARG_NETWORKID == '' or ARG_NAME == '':
        printhelp()
        sys.exit(2)

    webhookTemplatePayload = "{\n\"version\": \"0.1\",\n\"sharedSecret\": \"{{sharedSecret}}\",\n\"sentAt\": \"{{sentAt}}\",\n\"organizationId\": \"{{organizationId}}\",\n\"organizationName\": \"{{organizationName}}\",\n\"organizationUrl\": \"{{organizationUrl}}\",\n\"networkId\": \"{{networkId}}\",\n\"networkName\": \"{{networkName}}\",\n\"networkUrl\": \"{{networkUrl}}\",\n\"networkTags\": {{ networkTags | jsonify }},\n\"deviceSerial\": \"{{deviceSerial}}\",\n\"deviceMac\": \"{{deviceMac}}\",\n\"deviceName\": \"{{deviceName}}\",\n\"deviceUrl\": \"{{deviceUrl}}\",\n\"deviceTags\": {{ deviceTags | jsonify }},\n\"deviceModel\": \"{{deviceModel}}\",\n\"alertId\": \"{{alertId}}\",\n\"alertType\": \"{{alertType}}\",\n\"alertTypeId\": \"{{alertTypeId}}\",\n\"alertLevel\": \"{{alertLevel}}\",\n\"occurredAt\": \"{{occurredAt}}\",\n\"alertData\": {{ alertData | jsonify }}\n}\n"

    url = "https://api.meraki.com/api/v1/networks/" + ARG_NETWORKID + "/webhooks/payloadTemplates"

    payload = json.dumps({
        "name": ARG_NAME,
        "body": webhookTemplatePayload
    })

    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "X-Cisco-Meraki-API-Key": ARG_APIKEY
    }

    response = requests.request("POST", url, headers=headers, data=payload)

    print(response.status_code)
    print(response.text)


def printhelp():
    print("this script, for a given")
    print("-k API key")
    print("-n NetworkID")
    print("-i Webhook Template Name")
    print("creates a new custom webhook template")
    print("The only editing it needs is the webhook template payload")
    print("")
    print("API information available here: https://developer.cisco.com/meraki/webhooks/#!custom-payload-templates-overview")
    print("precreated templates available here: https://github.com/meraki/webhook-payload-templates")
    print("further training available here: https://developer.cisco.com/learning/labs/meraki-webhook-template-editor-intro/create-your-custom-webhook-template/")
    print("postman collection: https://www.postman.com/meraki-api/workspace/cisco-meraki-s-public-workspace/collection/897512-c65299ed-39a5-4b02-bb4e-933c738bfcdf?action=share&creator=897512&ctx=documentation")


if __name__ == '__main__':
    main(sys.argv[1:])
