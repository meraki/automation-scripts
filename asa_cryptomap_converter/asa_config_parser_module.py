import sys, ipaddress

ASA_STANDARD_PORTS = {
    'aol'               : 5120,
    'bgp'               : 179,
    'chargen'           : 19,
    'cifs'              : 3020,
    'citrix-ica'        : 1494,
    'cmd'               : 514,
    'ctiqbe'            : 2748,
    'daytime'           : 13,
    'discard'           : 9,
    'domain'            : 53,
    'echo'              : 7,
    'exec'              : 512,
    'finger'            : 79,
    'ftp'               : 21,
    'ftp-data'          : 20,
    'gopher'            : 70,
    'h323'              : 1720,
    'hostname'          : 101,
    'http'              : 80,
    'https'             : 443,
    'ident'             : 113,
    'imap4'             : 143,
    'irc'               : 194,
    'kerberos'          : 88,
    'klogin'            : 543,
    'kshell'            : 544,
    'ldap'              : 389,
    'ldaps'             : 636,
    'login'             : 513,
    'lotusnotes'        : 1352,
    'lpd'               : 515,
    'netbios-ns'        : 137,
    'netbios-dgm'       : 138,
    'netbios-ssn'       : 139,
    'nfs'               : 2049,
    'nntp'              : 119,
    'pcanywhere-data'   : 5631,
    'pim-auto-rp'       : 496,
    'pop2'              : 109,
    'pop3'              : 110,
    'pptp'              : 1723,
    'radius'            : 1812,
    'radius-acct'       : 1813,
    'rsh'               : 514,
    'rtsp'              : 554,
    'sip'               : 5060,
    'smtp'              : 25,
    'sqlnet'            : 1522,
    'ssh'               : 22,
    'sunrpc'            : 111,
    'tacacs'            : 49,
    'talk'              : 517,
    'telnet'            : 23,
    'uucp'              : 540,
    'whois'             : 43,
    'www'               : 80
}

ASA_IKEV1_TRANSFORM_SETS = {
    # transform_set_label   : [ encapsulation,  encryption,     hashing ]
    'esp-3des'              : [ 'esp',          '3des',         None    ],
    'esp-aes'               : [ 'esp',          'aes',          None    ],
    'esp-aes-192'           : [ 'esp',          'aes-192',      None    ],
    'esp-aes-256'           : [ 'esp',          'aes-256',      None    ],
    'esp-des'               : [ 'esp',          'des',          None    ],
    'esp-md5-hmac'          : [ 'esp',          None,           'md5'   ],
    'esp-sha-hmac'          : [ 'esp',          None,           'sha'   ]    
}

CLI = {
    # flags for what lines the parser has read last, signifying current item being configured
    'scopeLevel'    : None,
    'scopeItem0'    : None,
    'scopeItem1'    : None,
    'scopeItem2'    : None,
    
    # mappings for command handler functions. trailing spaces in keys are important to avoid confusing
    # with possible unsupported commands without definitions
    'commands': {
        'aaa-server '                       : lambda x: handlerAaa_Server                       (x),
        'access-group '                     : lambda x: handlerAccess_Group                     (x),
        'access-list '                      : lambda x: handlerAccess_List                      (x),
        'clock timezone '                   : None,
        'crypto dynamic-map '               : lambda x: handlerCryptoDynamic_map                (x),
        'crypto ikev1 enable '              : None,
        'crypto ikev2 enable '              : None,
        'crypto ipsec ikev1 transform-set ' : lambda x: handlerCryptoIpsecIkev1Transform_Set    (x),
        'crypto ipsec ikev2 ipsec-proposal ': lambda x: handlerCryptoIpsecIkev2Ipsec_Proposal   (x),
        'crypto ipsec security-association ': lambda x: handlerCryptoIpsecSecurity_association  (x),
        'crypto map '                       : lambda x: handlerCryptoMap                        (x),
        'default-group-policy '             : lambda x: handlerDefault_group_policy             (x),
        'description '                      : lambda x: handlerDescription                      (x),
        'dns server-group '                 : None,
        'failover '                         : None,
        'flow-export '                      : None,
        'group-policy '                     : lambda x: handlerGroup_policy                     (x),
        'host '                             : lambda x: handlerHost                             (x),
        'hostname '                         : lambda x: handlerHostname                         (x),
        'icmp '                             : None,
        'ikev1 pre-shared-key '             : lambda x: handlerIkev1Pre_shared_key              (x),
        'ikev2 local-authentication '       : lambda x: handlerIkev2Local_authentication        (x),
        'ikev2 remote-authentication '      : lambda x: handlerIkev2Remote_authentication       (x),
        'interface '                        : lambda x: handlerInterface                        (x),
        'ip address '                       : lambda x: handlerIp_Address                       (x),
        'ip local pool '                    : None,
        'key '                              : lambda x: handlerKey                              (x),
        'logging '                          : None,
        'monitor-interface '                : None,
        'name '                             : None,
        'name-server '                      : None,
        'nameif '                           : lambda x: handlerNameif                           (x),
        'nat '                              : lambda x: handlerNat                              (x),
        'network-object '                   : lambda x: handlerNetwork_Object                   (x),
        'network-object object '            : lambda x: handlerNetwork_ObjectObject             (x),
        'no '                               : lambda x: handlerNo                               (x),
        'object network '                   : lambda x: handlerObjectNetwork                    (x),
        'object service '                   : lambda x: handlerObjectService                    (x),
        'object-group network '             : lambda x: handlerObject_GroupNetwork              (x),
        'object-group service '             : lambda x: handlerObject_GroupService              (x),
        'route outside '                    : None,
        'port-object '                      : lambda x: handlerPort_Object                      (x),
        'protocol '                         : lambda x: handlerProtocol                         (x),
        'radius-common-pw '                 : lambda x: handlerKey                              (x), # mismatch intentional 
        'security-level '                   : lambda x: handlerSecurity_Level                   (x), 
        'service '                          : lambda x: handlerService                          (x),
        'service-policy '                   : None,
        'service-object '                   : lambda x: handlerService_Object                   (x),
        'service-object object '            : lambda x: handlerService_ObjectObject             (x),
        'service-type '                     : None,
        'shutdown '                         : lambda x: handlerShutdown                         (x),
        'subnet '                           : lambda x: handlerSubnet                           (x),
        'tunnel-group '                     : lambda x: handlerTunnel_group                     (x),
        'vlan '                             : lambda x: handlerVlan                             (x),
        'vpn-tunnel-protocol '              : lambda x: handlerVpn_tunnel_protocol              (x)
    }
}

ASA_CFG={
    'acls'                  : {},
    'settings'              : {},
    'interfaces'            : {},
    'nat'                   : { 'twiceRules':[] },
    'networkObjects'        : {},
    'networkObjectGroups'   : {},
    'aaaServers'            : {},
    'serviceObjects'        : {},
    'serviceObjectGroups'   : {},
    'vpn'                   : {
        'cryptoDynamic-maps': {},
        'cryptoMaps': {},
        'group-policies': {},
        'ikev1': {
            'transformSets':{}
        },
        'ikev2': {
            'proposals':{}
        }, 
        'tunnel-groups': {} 
    }
}


def getCommandHandler(line):
    handlerFunction = None
    parameters = {}
    matchKey = None
    matchLength = 0
    stripLine = line.strip()
    
    for key in CLI['commands']:
        keyLen = len(key)
        if stripLine.startswith(key) and keyLen > matchLength:
            matchKey    = key
            matchLength = keyLen
            
    if not matchKey is None and not CLI['commands'][matchKey] is None:
        parameters['value']     = stripLine[matchLength:].strip()
        parameters['command']   = matchKey
        parameters['negated']   = False
        handlerFunction = CLI['commands'][matchKey]
    
    return handlerFunction, parameters
    
def resolvePortNumber(word):
    strWord = str(word)
    try:
        if strWord in ASA_STANDARD_PORTS:
            return ASA_STANDARD_PORTS[strWord]
        else:
            return int(strWord)
    except:
        print('Parser error: Unable to resolve port "%s"' % word)
        return None
    
def extractPortData(definitionString):
    strDefinitionString = str(definitionString)
    if len(strDefinitionString) > 0:
        splitStr = strDefinitionString.split(" ")
        
        wordCounter = 0
        for word in splitStr:
            if word in ["eq", "range"]:
                break
            wordCounter += 1
            
        if wordCounter < len(splitStr):
            label = splitStr[wordCounter]
            
            if label == "eq" and len(splitStr) >= wordCounter+1:     
                port = resolvePortNumber(splitStr[wordCounter+1])
                if not port is None:
                    return {"eq": port}
            elif label == "range" and len(splitStr) >= wordCounter+1 :
                lowPort     = resolvePortNumber(splitStr[wordCounter+1])
                highPort    = resolvePortNumber(splitStr[wordCounter+2])
                if (not lowPort is None) and (not highPort is None):
                    return {"range": {"low": lowPort, "high": highPort}}   
    return None
    
def aclHandlerAny(payload):
    popped  = payload.pop(0)
    return {"type": "any", "value": "any"}, payload
    
def aclHandlerHost(payload):
    hostIp  = ipaddress.IPv4Network("%s/32" % payload[1])        
    popped  = payload.pop(0)
    popped  = payload.pop(0)
    return {"type": "static", "value": hostIp}, payload
    
def aclHandlerObject(payload):
    name    = payload[1]      
    popped  = payload.pop(0)
    popped  = payload.pop(0)
    return {"type": "object", "value": name}, payload
    
def aclHandlerObject_Group(payload):
    name    = payload[1]      
    popped  = payload.pop(0)
    popped  = payload.pop(0)
    return {"type": "objectGroup", "value": name}, payload
    
def extractAclScopeItems(rawData):
    aclItemTypeHandlers = {
        "any"           : lambda x: aclHandlerAny           (x),
        "any4"          : lambda x: aclHandlerAny           (x),
        "host"          : lambda x: aclHandlerHost          (x),
        "object"        : lambda x: aclHandlerObject        (x),
        "object-group"  : lambda x: aclHandlerObject_Group  (x)
    }
        
    remainingData       = rawData
    items               = []
            
    while len(remainingData) > 0 and len(items) < 2:
        key = remainingData[0]
        if (not key in aclItemTypeHandlers) or (aclItemTypeHandlers[key] is None):
            return None, None
        
        item, remainingData = aclItemTypeHandlers[key](remainingData)             
        if item is None:
            return None, None
        items.append(item)
           
    return items, remainingData #remainingData possibly contains port number info 
    
def extractExtendedAclData(aclData):
    strAclLine  = str(aclData)
    words       = strAclLine.split(" ")
    
    if words[1] == "extended":
        action      = words[2]
        protocol    = words[3]
        
        items, remainingData = extractAclScopeItems(words[4:])
        if not items is None:
            result = {
                "action"        : action,
                "protocol"      : protocol,
                "port"          : "any",
                "source"        : items[0],
                "destination"   : items[1]
            }
            
            if len(remainingData) > 0: # optional port definition needs to be handled
                if remainingData[0] == "eq":
                    result["port"] = {"eq": resolvePortNumber(remainingData[1])}
                elif remainingData[0] == "object-group":
                    result["port"] = {"objectGroup": remainingData[1]}
                else:
                    return None                    
            return result            
    return None
    
def extractStandardAclData(aclData):
    strAclLine  = str(aclData)
    words       = strAclLine.split(" ")
    
    if words[1] == "standard":
        action      = words[2]
        try:
            hostIp  = ipaddress.IPv4Network("%s/%s" % (words[3], words[4]))
        except:
            return None
          
        result = {
            "action"        : action,
            "protocol"      : "any",
            "port"          : "any",
            "source"        : "any",
            "destination"   : {
                                "type"  : "static",
                                "value" : hostIp
                              }
        }
        return result
    return None
    
def handlerAaa_Server(parameters):
    if not parameters['negated']:
        words = parameters['value'].split(" ")
        if len(words) >= 3:
            aaaGroupName = words[0]
            if words[1] == "protocol":
                if words[2] == "radius":
                    CLI['scopeLevel']   = "aaaServer"
                    CLI['scopeItem0']   = aaaGroupName
                    CLI['scopeItem1']   = None
                    CLI['scopeItem2']   = None
                    if not aaaGroupName in ASA_CFG['aaaServers']:
                        ASA_CFG['aaaServers'][aaaGroupName] = {
                            'type':'radius', 
                            'nameifs': {}
                        }
            elif words[1].startswith("(") and words[1].endswith(")"):
                if aaaGroupName in ASA_CFG['aaaServers']:
                    if words[2] == "host" and len(words) >= 4:
                        nameif  = words[1][1:-1]
                        host    = words[3]
                        CLI['scopeLevel']   = "aaaServer"
                        CLI['scopeItem0']   = aaaGroupName
                        CLI['scopeItem1']   = nameif
                        CLI['scopeItem2']   = host
                        if not nameif in ASA_CFG['aaaServers'][aaaGroupName]['nameifs']:
                            ASA_CFG['aaaServers'][aaaGroupName]['nameifs'][nameif] = {}
                        if not host in ASA_CFG['aaaServers'][aaaGroupName]['nameifs'][nameif]:
                            ASA_CFG['aaaServers'][aaaGroupName]['nameifs'][nameif][host] = {}
                else:
                    # This is config for an unsupported AAA group type. Flag as "do not process"
                    CLI['scopeLevel']   = None
                    CLI['scopeItem0']   = None
                    CLI['scopeItem1']   = None
                    CLI['scopeItem2']   = None
                    
                    
                    
            
def handlerAccess_Group(parameters):
    if not parameters['negated']:
        words = parameters['value'].split(" ")
        if len(words) >= 4 and words[2] == 'interface':
            aclName         = words[0]
            interfaceNameif = words[3]
            if aclName in ASA_CFG['acls']:
                for interface in ASA_CFG['interfaces']:
                    if 'nameif' in ASA_CFG['interfaces'][interface] and (
                            ASA_CFG['interfaces'][interface]['nameif'] == interfaceNameif):                    
                        ASA_CFG['interfaces'][interface]['accessGroup'] = {
                            'aclName'   : aclName,
                            'direction' : words[1]
                        }
        else:
            print("Parser error: Unknown access-group format:\n%s" % parameters['value'])
    
def handlerAccess_List(parameters):
    CLI['scopeLevel'] = 'access_List'
    splitValue = str(parameters['value']).split(" ")
    if len(splitValue) >= 4:
        aclName = splitValue[0]
        lineType = splitValue[1]
        CLI['scopeItem0'] = aclName
        
        if not aclName in ASA_CFG['acls']:
            ASA_CFG['acls'][aclName] = {'inUse': False, 'rules':[]}
            
        if lineType == "extended":
            line = extractExtendedAclData(parameters['value'])
            if not line is None:
                ASA_CFG['acls'][aclName]['rules'].append(line)
            else:
                print("Parser error: Unknown data in ACL line:\n%s" % parameters['value'])
        elif lineType == "standard":
            line = extractStandardAclData(parameters['value'])
            if not line is None:
                ASA_CFG['acls'][aclName]['rules'].append(line)
            else:
                print("Parser error: Unknown data in ACL line:\n%s" % parameters['value'])
        #elif lineType == "remark":
        #    if len(ASA_CFG['acls'][aclName]) > 0:
        #        print("got remark for line %s" % (len(ASA_CFG['acls'][aclName]) - 1))
        #    else:
        #        print('Got remark for empty ACL "%s"' % aclName)
        
def handlerCryptoDynamic_map(parameters):
    if not parameters['negated']:
        splitValue  = parameters['value'].split(" ")
        label       = splitValue[0].strip()
        if not label in ASA_CFG['vpn']['cryptoDynamic-maps']:
            ASA_CFG['vpn']['cryptoDynamic-maps'][label] = {}
        command     = splitValue[2].strip()
        if command == "set":
            attribute = splitValue[3].strip()
            if attribute == "ikev1":
                if not 'ikev1' in ASA_CFG['vpn']['cryptoDynamic-maps'][label]:
                    ASA_CFG['vpn']['cryptoDynamic-maps'][label]['ikev1'] = {}
                if splitValue[4].strip() == "transform-set":
                    ASA_CFG['vpn']['cryptoDynamic-maps'][label]['ikev1']['transform-set'] = splitValue[5:]
            if attribute == "ikev2":
                if not 'ikev2' in ASA_CFG['vpn']['cryptoDynamic-maps'][label]:
                    ASA_CFG['vpn']['cryptoDynamic-maps'][label]['ikev2'] = {}
                if splitValue[4].strip() == "ipsec-proposal":
                    ASA_CFG['vpn']['cryptoDynamic-maps'][label]['ikev2']['ipsec-proposal'] = splitValue[5:]   
        
def handlerCryptoIpsecIkev1Transform_Set(parameters):
    words = parameters['value'].strip().split(" ")
    if len(words) >= 3:
        setName = words[0]
        if not setName in ASA_CFG['vpn']['ikev1']['transformSets']:
            ASA_CFG['vpn']['ikev1']['transformSets'][setName] = {
                'encapsulation' : None,
                'encryption'    : None,
                'integrity'     : None,
                'mode'          : None
            }
        if words[1] == 'mode':
            ASA_CFG['vpn']['ikev1']['transformSets'][setName]['mode'] = words[2]
        else:
            for word in words[1:]:
                if word in ASA_IKEV1_TRANSFORM_SETS:
                    data = {
                        'encapsulation' : ASA_IKEV1_TRANSFORM_SETS[word][0],
                        'encryption'    : ASA_IKEV1_TRANSFORM_SETS[word][1],
                        'integrity'     : ASA_IKEV1_TRANSFORM_SETS[word][2]
                    }
                    for attribute in data:
                        if not data[attribute] is None:
                            ASA_CFG['vpn']['ikev1']['transformSets'][setName][attribute] = data[attribute]
                            
def handlerCryptoIpsecIkev2Ipsec_Proposal(parameters):
    label = str(parameters["value"])
    if len(label) > 0:
        CLI['scopeLevel']   = 'cryptoIpsecIkev2IpsecProposal'
        CLI['scopeItem0']   = label
        if not label in ASA_CFG['vpn']['ikev2']['proposals']:
            ASA_CFG['vpn']['ikev2']['proposals'][label] = {
                'encapsulation' : None,
                'encryption'    : None,
                'integrity'     : None            
            }
    
def handlerCryptoIpsecSecurity_association(parameters):
    if not parameters['negated']:
        splitValue = parameters['value'].split(" ")
        if len(splitValue) == 3 and splitValue[0].strip() == 'lifetime' and splitValue[1].strip() == 'seconds':
            ASA_CFG['vpn']['defaultTunnelLifetimeSeconds'] = int(splitValue[2].strip())

def handlerCryptoMap(parameters):
    if not parameters['negated']:
        splitValue = parameters['value'].split(" ")
        label = splitValue[0].strip()
        if not label in ASA_CFG['vpn']['cryptoMaps']:
            ASA_CFG['vpn']['cryptoMaps'][label] = { 'rules': {}, 'interface': None }
        index = splitValue[1].strip()
        if index == 'interface':
            ASA_CFG['vpn']['cryptoMaps'][label]['interface'] = splitValue[2].strip()
        else:
            if not index in ASA_CFG['vpn']['cryptoMaps'][label]['rules']:
                ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index] = {}
            command = splitValue[2].strip()
            if command == 'set':
                attribute = splitValue[3].strip()
                if      attribute == 'peer':
                    ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['peer'] = splitValue[4].strip()
                elif    attribute == 'ikev1':
                    if not 'ikev1' in ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]:
                        ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['ikev1'] = {}                    
                    subAttribute = splitValue[4].strip()
                    if subAttribute == 'transform-set':
                        ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['ikev1']['transform-set'] = splitValue[5:]
                elif    attribute == 'ikev2':
                    if not 'ikev2' in ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]:
                        ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['ikev2'] = {}  
                    subAttribute = splitValue[4].strip()
                    if subAttribute == 'ipsec-proposal':
                        ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['ikev2']['ipsec-proposal'] = splitValue[5]
                elif    attribute == 'pfs':
                    pfsGroup = 14
                    if len(splitValue) > 4:
                        pfsGroup = int(splitValue[4].strip()[5:])
                    ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['pfsGroup'] = pfsGroup
                elif    attribute == 'security-association':
                    if len(splitValue) == 7 and splitValue[4].strip() == 'lifetime' and splitValue[5].strip() == 'seconds':
                        ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['lifetime'] = int(splitValue[6].strip())
            elif command == 'match':
                if splitValue[3].strip() == 'address':
                    ASA_CFG['vpn']['cryptoMaps'][label]['rules'][index]['matchAddress'] = splitValue[4].strip()
            elif command == 'ipsec-isakmp':
                if not 'ipsec-isakmp' in ASA_CFG['vpn']['cryptoMaps'][label]:
                    ASA_CFG['vpn']['cryptoMaps'][label]['ipsec-isakmp'] = {'type': None}
                ASA_CFG['vpn']['cryptoMaps'][label]['ipsec-isakmp']['type']     = splitValue[3].strip()
                ASA_CFG['vpn']['cryptoMaps'][label]['ipsec-isakmp']['value']    = splitValue[4].strip()
                        
def handlerDefault_group_policy(parameters):
    if CLI['scopeLevel'] == 'tunnel-group' and CLI['scopeItem1'] == 'general-attributes':
        ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['general-attributes']['default-group-policy'] = parameters['value']        
                  
def handlerDescription(parameters):
    if CLI['scopeLevel'] == 'objectNetwork' and CLI['scopeItem0'] in ASA_CFG['networkObjects']:
        ASA_CFG['networkObjects'][CLI['scopeItem0']]['description'] = parameters['value']
    elif CLI['scopeLevel'] == 'object_GroupNetwork' and CLI['scopeItem0'] in ASA_CFG['networkObjectGroups']:
        ASA_CFG['networkObjectGroups'][CLI['scopeItem0']]['description'] = parameters['value']
    elif CLI['scopeLevel'] == 'interface' and CLI['scopeItem0'] in ASA_CFG['interfaces']:
        ASA_CFG['interfaces'][CLI['scopeItem0']]['description'] = parameters['value']
        
def handlerGroup_policy(parameters):
    if not parameters['negated']:
        splitValue  = parameters['value'].split(" ")
        label       = splitValue[0].strip()
        if not label in ASA_CFG['vpn']['group-policies']:
            ASA_CFG['vpn']['group-policies'][label] = { 'type': None, 'attributes': {} }        
        attribute   = splitValue[1].strip()
        if attribute == 'internal':
            ASA_CFG['vpn']['group-policies'][label]['type'] = 'internal'
        elif attribute == 'attributes':
            CLI['scopeLevel'] = 'group-policy'
            CLI['scopeItem0'] = label
            CLI['scopeItem1'] = 'attributes'  
        
def handlerHost(parameters):
    net = ipaddress.IPv4Network("%s/32" % parameters['value'])
    if CLI['scopeLevel'] == 'objectNetwork' and CLI['scopeItem0'] in ASA_CFG['networkObjects']:
        ASA_CFG['networkObjects'][CLI['scopeItem0']]['items'].append(net)
        
def handlerHostname(parameters):
    ASA_CFG['settings']['hostname'] = str(parameters['value']).strip()
    
def handlerIkev1Pre_shared_key(parameters):
    if CLI['scopeLevel'] == 'tunnel-group' and CLI['scopeItem1'] == 'ipsec-attributes':
        if not 'ikev1' in ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']:
             ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev1'] = {}
        ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev1']['pre-shared-key'] = parameters['value'].strip()
    
def handlerIkev2Local_authentication(parameters):
    if CLI['scopeLevel'] == 'tunnel-group' and CLI['scopeItem1'] == 'ipsec-attributes':
        splitValue  = parameters['value'].split(" ")
        if splitValue[0] == 'pre-shared-key' and len(splitValue) > 1:
            if not 'ikev2' in ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']:
                ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2'] = {}
            if not 'local-authentication' in ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']:
                ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['local-authentication'] = {}
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['local-authentication']['type'] = 'pre-shared-key'
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['local-authentication']['value'] = splitValue[1]
    
def handlerIkev2Remote_authentication(parameters):
    if CLI['scopeLevel'] == 'tunnel-group' and CLI['scopeItem1'] == 'ipsec-attributes':
        if not 'ikev2' in ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']:
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2'] = {}
        if not 'remote-authentication' in ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']:
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['remote-authentication'] = {}
        splitValue  = parameters['value'].split(" ")
        if splitValue[0] == 'pre-shared-key' and len(splitValue) > 1:
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['remote-authentication']['type'] = 'pre-shared-key'
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['remote-authentication']['value'] = splitValue[1]
        elif splitValue[0] == 'certificate':
            ASA_CFG['vpn']['tunnel-groups'][CLI['scopeItem0']]['ipsec-attributes']['ikev2']['remote-authentication']['type'] = 'certificate'
    
def handlerInterface(parameters):
    CLI['scopeLevel']    = 'interface'
    CLI['scopeItem0']     = parameters['value']
    splitValue                  = parameters['value'].split(".")    
    physicalInterface           = splitValue[0]
    subinterface                = None
    if len(splitValue) > 1:
        subinterface = splitValue[1]
        
    if not physicalInterface in ASA_CFG['interfaces']:
        ASA_CFG['interfaces'][physicalInterface] = {'enabled': True, 'subinterfaces': []}
        
    if not subinterface is None:        
        if not parameters['value'] in ASA_CFG['interfaces']:
            ASA_CFG['interfaces'][parameters['value']] = {}
        if not subinterface in ASA_CFG['interfaces'][physicalInterface]['subinterfaces']:
            ASA_CFG['interfaces'][physicalInterface]['subinterfaces'].append(subinterface)     

def handlerIp_Address(parameters):
    if CLI['scopeLevel'] == 'interface' and CLI['scopeItem0'] in ASA_CFG['interfaces']:
        if not parameters['negated']:
            words = parameters['value'].split(" ")
            deviceIp = words[0]
            try:
                subnet = ipaddress.IPv4Network("%s/%s" % (words[0], words[1]), strict=False)
            except:
                print("Parser error: Incorrect IP address")
                print(parameters['value'])
                return None
            ASA_CFG['interfaces'][CLI['scopeItem0']]['ip'] = deviceIp
            ASA_CFG['interfaces'][CLI['scopeItem0']]['network'] = subnet
            
def handlerKey(parameters):
    # !!! ALSO USED FOR radius-common-pw !!!
    aaaGroupName    = CLI['scopeItem0']
    nameif          = CLI['scopeItem1']
    host            = CLI['scopeItem2']
    if CLI['scopeLevel'] == 'aaaServer' and aaaGroupName in ASA_CFG['aaaServers'] and not (
            nameif is None or host is None):
        ASA_CFG['aaaServers'][aaaGroupName]['nameifs'][nameif][host][parameters['command'].strip()] = parameters['value']

def handlerNameif(parameters):
    if CLI['scopeLevel'] == 'interface' and CLI['scopeItem0'] in ASA_CFG['interfaces']:
        if not parameters['negated']:
            ASA_CFG['interfaces'][CLI['scopeItem0']]['nameif'] = parameters['value'] 

def resolveNatObjectLabel(label):
    result = None
    if label == "any":
        result = {"type": "any"}
    elif label in ASA_CFG["networkObjects"]:
        result = {
                "type": "object",
                "value": label
            }
    elif label in ASA_CFG["networkObjectGroups"]:
        result = {
                "type": "objectGroup",
                "value": label
            }
    return result
    

def extractNatItem(nameif, words):
    if len(words) < 2:
        return None

    result = {
        "nameif": nameif
    }
    result["type"] = words[0]
    
    realObject = resolveNatObjectLabel(words[1])
    if realObject is None:
        return None
    result["real"] = realObject
    
    if len(words) > 2:
        mappedObject = resolveNatObjectLabel(words[2])
        if mappedObject is None:
            return None
        result["mapped"] = mappedObject            
                
    return result

def handlerNat(parameters):
    # this may be object NAT or twice NAT. We need to check for keyword "source" to tell
    openParenthesisPtr  = parameters['value'].find('(')
    closeParenthesisPtr = parameters['value'].find(')')
    if openParenthesisPtr == -1 or closeParenthesisPtr == -1 or closeParenthesisPtr < openParenthesisPtr:
        return None
        
    nameifs = parameters['value'][openParenthesisPtr+1:closeParenthesisPtr].split(',')
    if len(nameifs) != 2 or len(parameters['value']) < closeParenthesisPtr+2:
        return None
        
    words = parameters['value'][closeParenthesisPtr+1:].strip().split(" ")
    if words[0] == "source":
        #this is twice NAT
        result = {
                "source": {},
                "destination": {},
                "description": ""
            }
        if not "destination" in words:
            return None
        destinationPtr  = words.index("destination")
        sourceWords     = words[1:destinationPtr]
        descriptionPtr  = None
        if "description" in words:
            descriptionPtr      = words.index("description")
            destinationWords    = words[destinationPtr+1:descriptionPtr]
            descriptionWords    = words[descriptionPtr+1:]
        else:
            destinationWords    = words[destinationPtr+1:]
            
        # raise flags for keywords, unless they are in the description
        result["enabled"]           = not "inactive" in destinationWords        
        result["unidirectional"]    = "unidirectional" in destinationWords                   
            
        # clean possible extra keywords out of destination words
        if "unidirectional" in destinationWords:
            destinationWords = destinationWords[:destinationWords.index("unidirectional")]
        if "no-proxy-arp" in destinationWords:
            destinationWords = destinationWords[:destinationWords.index("no-proxy-arp")]
        if "inactive" in destinationWords:
            destinationWords = destinationWords[:destinationWords.index("inactive")]
        if "route-lookup" in destinationWords:
            destinationWords = destinationWords[:destinationWords.index("route-lookup")]
            
        result['source']        = extractNatItem(nameifs[0], sourceWords)
        result['destination']   = extractNatItem(nameifs[1], destinationWords)
        if result['source'] is None or result['destination'] is None:
            return None   

        if not descriptionPtr is None:
            result["description"] = " ".join(descriptionWords)
            
        ASA_CFG['nat']['twiceRules'].append(result)
    else:
        print("Parser error: Object NAT not supported")

def handlerNetwork_Object(parameters):
    net = ipaddress.IPv4Network(parameters['value'].replace(" ", "/"))
    if CLI['scopeLevel'] == 'object_GroupNetwork' and CLI['scopeItem0'] in ASA_CFG['networkObjectGroups']:
        ASA_CFG['networkObjectGroups'][CLI['scopeItem0']]['items'].append({"type": "subnet", "value": net})
         
def handlerNetwork_ObjectObject(parameters):
    if CLI['scopeLevel'] == 'object_GroupNetwork' and CLI['scopeItem0'] in ASA_CFG['networkObjectGroups']:
        ASA_CFG['networkObjectGroups'][CLI['scopeItem0']]['items'].append({"type": "object", "value": parameters['value']})
    
def handlerNo(parameters):
    handler, param      = getCommandHandler(parameters['value'])
    param['negated']    = True
    result              = None    
    if not handler is None:
        handler(param)  
    
def handlerObjectNetwork(parameters):
    CLI['scopeLevel'] = 'objectNetwork'
    CLI['scopeItem0'] = parameters['value']
    if not parameters['value'] in ASA_CFG['networkObjects']:
        ASA_CFG['networkObjects'][parameters['value']] = {'description': '', 'inUse': False, 'items': []}
        
def handlerObject_GroupNetwork(parameters):
    CLI['scopeLevel'] = 'object_GroupNetwork'
    CLI['scopeItem0'] = parameters['value']
    if not parameters['value'] in ASA_CFG['networkObjectGroups']:
        ASA_CFG['networkObjectGroups'][parameters['value']] = {'description': '', 'inUse': False, 'items': []}
        
def handlerObjectService(parameters):
    CLI['scopeLevel'] = 'objectService'
    CLI['scopeItem0'] = parameters['value']
    if not parameters['value'] in ASA_CFG['serviceObjects']:
        ASA_CFG['serviceObjects'][parameters['value']] = {'description': '', 'items': []}
        
def handlerObject_GroupService(parameters):
    CLI['scopeLevel'] = 'object_GroupService'    
    splitValue = parameters['value'].split(" ")
    key = splitValue[0]
    CLI['scopeItem0'] = key
    protocol = None
    if len(splitValue) > 1:
        protocol = splitValue[1]
    
    if not key in ASA_CFG['serviceObjectGroups']:
        ASA_CFG['serviceObjectGroups'][key] = {'description': '', 'items': []}
        
    if not protocol is None:
        ASA_CFG['serviceObjectGroups'][key]['protocol'] = protocol
        
def handlerPort_Object(parameters):
    if CLI['scopeLevel'] == 'object_GroupService' and CLI['scopeItem0'] in ASA_CFG['serviceObjectGroups']:
        portData = extractPortData(parameters['value'])
        if (not portData is None) and ('protocol' in ASA_CFG['serviceObjectGroups'][CLI['scopeItem0']]):
            portData['protocol'] = ASA_CFG['serviceObjectGroups'][CLI['scopeItem0']]['protocol']
            ASA_CFG['serviceObjectGroups'][CLI['scopeItem0']]['items'].append({"type":"static", "value": portData})
        
def handlerProtocol(parameters):
    if CLI['scopeLevel'] == 'cryptoIpsecIkev2IpsecProposal' and CLI['scopeItem0'] in ASA_CFG['vpn']['ikev2']['proposals']:
        words = parameters["value"].strip().split(" ")
        if len(words) >= 3:
            label = CLI['scopeItem0']
            ASA_CFG['vpn']['ikev2']['proposals'][label]['encapsulation'] = words[0]
            attribute = words[1]
            if attribute in ['encryption','integrity']:
                ASA_CFG['vpn']['ikev2']['proposals'][label][attribute] = words[2]    
        
def handlerSecurity_Level(parameters):
    if CLI['scopeLevel'] == 'interface' and CLI['scopeItem0'] in ASA_CFG['interfaces']:
        if not parameters['negated']:
            ASA_CFG['interfaces'][CLI['scopeItem0']]['securityLevel'] = parameters['value']     
        
def handlerService(parameters):
    if CLI['scopeLevel'] == 'objectService' and CLI['scopeItem0'] in ASA_CFG['serviceObjects']:
        portData = extractPortData(parameters['value'])
        if not portData is None:
            portData['protocol'] = parameters['value'].split(" ")[0]
            ASA_CFG['serviceObjects'][CLI['scopeItem0']]['items'].append(portData)
            
def handlerService_Object(parameters):
    if CLI['scopeLevel'] == 'object_GroupService' and CLI['scopeItem0'] in ASA_CFG['serviceObjectGroups']:
        portData = extractPortData(parameters['value'])
        if not portData is None:
            portData['protocol'] = portData['protocol'] = parameters['value'].split(" ")[0]
            ASA_CFG['serviceObjectGroups'][CLI['scopeItem0']]['items'].append({"type":"static", "value": portData})
        
def handlerService_ObjectObject(parameters):
    if CLI['scopeLevel'] == 'object_GroupService' and CLI['scopeItem0'] in ASA_CFG['serviceObjectGroups']:
        ASA_CFG['serviceObjectGroups'][CLI['scopeItem0']]['items'].append({"type": "object", "value": parameters['value']})
        
def handlerShutdown(parameters):
    if CLI['scopeLevel'] == 'interface' and CLI['scopeItem0'] in ASA_CFG['interfaces']:
        if not parameters['negated']:
            ASA_CFG['interfaces'][CLI['scopeItem0']]['enabled'] = False
            
def handlerSubnet(parameters):
    net = ipaddress.IPv4Network(parameters['value'].replace(" ", "/"))
    if CLI['scopeLevel'] == 'objectNetwork' and CLI['scopeItem0'] in ASA_CFG['networkObjects']:
        ASA_CFG['networkObjects'][CLI['scopeItem0']]['items'].append(net)
        
def handlerTunnel_group(parameters):
    if not parameters['negated']:
        splitValue = parameters['value'].split(' ')
        label = splitValue[0]
        if not label in ASA_CFG['vpn']['tunnel-groups']:
            ASA_CFG['vpn']['tunnel-groups'][label] = {}
        if len(splitValue) > 2:
            if splitValue[1] == 'type':
                ASA_CFG['vpn']['tunnel-groups'][label]['type'] = splitValue[2]
        elif len(splitValue) > 1:
            attributeGroup = splitValue[1]
            ASA_CFG['vpn']['tunnel-groups'][label][attributeGroup] = {}
            CLI['scopeLevel'] = 'tunnel-group'
            CLI['scopeItem0'] = label
            CLI['scopeItem1'] = attributeGroup
            
def handlerVlan(parameters):
    if CLI['scopeLevel'] == 'interface' and CLI['scopeItem0'] in ASA_CFG['interfaces']:
        if not parameters['negated']:
            ASA_CFG['interfaces'][CLI['scopeItem0']]['vlan'] = parameters['value']   
    
def handlerVpn_tunnel_protocol(parameters):
    if not parameters['negated']: 
        if CLI['scopeLevel'] == 'group-policy' and CLI['scopeItem0'] in ASA_CFG['vpn']['group-policies'] and CLI['scopeItem1'] == 'attributes':
            ASA_CFG['vpn']['group-policies'][CLI['scopeItem0']]['attributes']['vpn-tunnel-protocol'] = parameters['value'].split(' ')
    
def parseAsaConfiguration(rawConfig):
    for line in rawConfig:
        handler, param = getCommandHandler(line)
        if not handler is None:
            handler(param)
            
def tagInUseAclsFromAccessGroups():
    for interface in ASA_CFG['interfaces']:
        if 'accessGroup' in ASA_CFG['interfaces'][interface]:
            aclName = ASA_CFG['interfaces'][interface]['accessGroup']['aclName']
            ASA_CFG['acls'][aclName]['inUse'] = True
        
    
def parse(rawConfig):
    config = rawConfig.split("\n")        
    parseAsaConfiguration(config)
    tagInUseAclsFromAccessGroups()
    return(ASA_CFG)
    
def main(argv):
    print('This is a module used by "cryptomap_converter.py". Please use that script instead.')
    
    
if __name__ == '__main__':
    main(sys.argv[1:])