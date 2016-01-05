#! /usr/bin/env python3
from coreapis.ldap import controller as ldapcontroller
from coreapis.utils import Timer, ResourcePool
import argparse
import sys
import ldap3
import ldap3.core.exceptions
import json

DESCRIPTION = "Verify ldap-configs for connect"


def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('--config', default="/conf/ldap-config.json",
                        help="Config file to use")
    parser.add_argument('--ca-certs', default='/conf/ldap_certs.txt',
                        help='Ca certificate bundle to use')
    parser.add_argument('orgs', help="organizations to query. (default all)",
                        nargs='*')
    return parser.parse_args()


def parse_ldap_config(filename):
    config = json.load(open(filename))
    servers = {}
    for org in config:
        orgconf = config[org]
        server_pool = ldap3.ServerPool(None, ldap3.POOLING_STRATEGY_ROUND_ROBIN, active=True)
        for server in orgconf['servers']:
            if ':' in server:
                host, port = server.split(':', 1)
                port = int(port)
            else:
                host, port = server, None
            server = ldap3.Server(host, port=port, use_ssl=True)
            server_pool.add(server)
        servers[org] = server_pool
    return config, servers


def fail(message):
    print("Error: {}".format(message))
    sys.exit(1)


def verify_item_datatype(org, data, key, datatype):
    if not key in data:
        fail("{} misses key '{}'".format(org, key))
    if not isinstance(data[key], datatype):
        fail("{} key '{}' has wrong datatype {} should be {}".format(org, key,
                                                                     type(data[key]), datatype))


def sanity_check_config(config):
    for org, data in config.items():
        verify_item_datatype(org, data, 'base_dn', str)
        verify_item_datatype(org, data, 'display', str)
        verify_item_datatype(org, data, 'servers', list)
        if len(data['servers']) < 1:
            fail("{} has no servers".format(org))
        verify_item_datatype(org, data, 'peoplesearch', dict)
        peoplesearch = data['peoplesearch']
        for key in ('employees', 'others'):
            verify_item_datatype("{} peoplesearch".format(org), peoplesearch, key, str)
            if peoplesearch[key] not in ("none", "sameOrg", "all"):
                fail("{} has unhandled value {} for peoplesearch for {}".format(org, peoplesearch[key], key))
        if "bind_user" in data:
            verify_item_datatype(org, data, 'bind_user', dict)
            bind_user = data['bind_user']
            verify_item_datatype("{} bind_user".format(org), bind_user, "dn", str)
            verify_item_datatype("{} bind_user".format(org), bind_user, "password", str)
            for key in bind_user:
                if key not in ("dn", "password"):
                    fail("{} bind_user has unexpected key {}".format(org, key))
        if "exclude" in data:
            verify_item_datatype(org, data, "exclude", str)
        for key in data:
            if key not in ('base_dn', 'display', 'servers', 'bind_user', 'exclude', 'peoplesearch'):
                fail("{} has unexpected key {}".format(org, key))


def main():
    args = parse_args()
    config, servers = ldapcontroller.parse_ldap_config(args.config, args.ca_certs)
    sanity_check_config(config)
    print("config file looks good")
    for org, conf in config.items():
        print("{}: base_dn: {} servers: {}".format(org, conf['base_dn'], ", ".join(conf['servers'])))
    timer = Timer('localhost', 1234, 'ldap-verify', True, ResourcePool)
    settings = {
        'ldap_config_file': args.config,
        'ldap_ca_certs': args.ca_certs,
        'timer': timer,
    }
    ldap = ldapcontroller.LDAPController(settings)
    if args.orgs:
        orgs = args.orgs
    else:
        orgs = config.keys()
    for org in orgs:
        print("trying connection to {}: ".format(org), end='')
        search_filter = '(eduPersonPrincipalName=notfound@example.com)'
        try:
            ldap.ldap_search(org, search_filter,
                             ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                             attributes=['cn'], size_limit=1)
            print("OK")
        except ldap3.core.exceptions.LDAPServerPoolExhaustedError:
            print("Failed")

if __name__ == '__main__':
    main()
