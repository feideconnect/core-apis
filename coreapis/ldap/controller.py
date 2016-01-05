from functools import partial
import json
import ssl

import ldap3

from coreapis.utils import ValidationError, LogWrapper, ResourcePool


def validate_query(string):
    for char in ('(', ')', '*', '\\'):
        if char in string:
            raise ValidationError('Bad character in request')


def parse_ldap_config(filename, ca_certs):
    config = json.load(open(filename))
    servers = {}
    tls = ldap3.Tls(validate=ssl.CERT_REQUIRED,
                    ca_certs_file=ca_certs)
    for org in config:
        orgconf = config[org]
        server_pool = ldap3.ServerPool(None, ldap3.POOLING_STRATEGY_ROUND_ROBIN,
                                       active=True, exhaust=True)
        for server in orgconf['servers']:
            if ':' in server:
                host, port = server.split(':', 1)
                port = int(port)
            else:
                host, port = server, None
            server = ldap3.Server(host, port=port, use_ssl=True, connect_timeout=1, tls=tls)
            server_pool.add(server)
        servers[org] = server_pool
    return config, servers


class LDAPController(object):
    def __init__(self, settings, pool=ResourcePool):
        timer = settings.get('timer')
        ldap_config = settings.get('ldap_config_file', 'ldap-config.json')
        ca_certs = settings.get('ldap_ca_certs', None)
        self.t = timer
        self.log = LogWrapper('peoplesearch.LDAPController')
        self.config, self.servers = parse_ldap_config(ldap_config, ca_certs)
        self.conpools = {org: pool(create=partial(self.get_connection, org)) for org in self.config}

    def get_ldap_config(self):
        return self.config

    def get_connection(self, org):
        orgconf = self.config[org]
        if 'bind_user' in orgconf:
            user = orgconf['bind_user']['dn']
            password = orgconf['bind_user']['password']
        else:
            user = None
            password = None
        con = ldap3.Connection(self.servers[org], auto_bind=True,
                               user=user, password=password,
                               client_strategy=ldap3.STRATEGY_SYNC_RESTARTABLE,
                               check_names=True)
        return con

    def get_base_dn(self, org):
        return self.get_ldap_config()[org]['base_dn']

    def handle_exclude(self, org, search):
        exclude_filter = self.get_ldap_config()[org].get('exclude', None)
        if exclude_filter:
            search = "(&{}(!{}))".format(search, exclude_filter)
        return search

    def search(self, org, base_dn, search_filter, scope, attributes, size_limit=None):
        with self.conpools[org].item() as con:
            with self.t.time('ps.ldap_search'):
                con.search(base_dn, search_filter, scope, attributes=attributes,
                           size_limit=size_limit)
            return con.response

    def ldap_search(self, org, search_filter, scope, attributes, size_limit=None):
        base_dn = self.get_base_dn(org)
        search_filter = self.handle_exclude(org, search_filter)
        return self.search(org, base_dn, search_filter, scope, attributes, size_limit)

    def lookup_feideid(self, feideid, attributes):
        if not '@' in feideid:
            raise ValidationError('feide id must contain @')
        _, realm = feideid.split('@', 1)
        validate_query(feideid)
        search_filter = '(eduPersonPrincipalName={})'.format(feideid)
        res = self.ldap_search(realm, search_filter,
                               ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                               attributes=attributes, size_limit=1)
        if len(res) == 0:
            self.log.debug('Could not find user for %s' % feideid)
            raise KeyError('User not found')
        if len(res) > 1:
            self.log.warn('Multiple matches to eduPersonPrincipalName')
        return res[0]['attributes']
