import json
import time

import ldap3

from coreapis.utils import ValidationError, LogWrapper
from .connection_pool import RetryPool, ConnectionPool


def validate_query(string):
    for char in ('(', ')', '*', '\\'):
        if char in string:
            raise ValidationError('Bad character in request')


def parse_ldap_config(filename, ca_certs, max_idle, max_connections, timeouts):
    with open(filename) as fh:
        config = json.load(fh)
    servers = {}
    orgpools = {}
    for org in config:
        orgconf = config[org]
        org_connection_pools = []
        for server in orgconf['servers']:
            if 'bind_user' in orgconf:
                user = orgconf['bind_user']['dn']
                password = orgconf['bind_user']['password']
            else:
                user = None
                password = None
            if ':' in server:
                host, port = server.split(':', 1)
                port = int(port)
            else:
                host, port = server, None
            if not (host, port, user) in servers:
                cp = ConnectionPool(host, port, user, password,
                                    max_idle, max_connections, timeouts, ca_certs)
                servers[(host, port, user)] = cp
            org_connection_pools.append(servers[(host, port, user)])
        orgpool = RetryPool(org_connection_pools)
        orgpools[org] = orgpool
    return config, servers, orgpools


class LDAPController(object):
    def __init__(self, settings):
        timer = settings.get('timer')
        ldap_config = settings.get('ldap_config_file', 'ldap-config.json')
        ca_certs = settings.get('ldap_ca_certs', None)
        max_idle = int(settings.get('ldap_max_idle_connections', '4'))
        max_connections = int(settings.get('ldap_max_connections', '10'))
        timeouts = {
            'connect': int(settings.get('ldap_connect_timeout', '1')),
            'connection_wait': int(settings.get('ldap_max_connection_pool_wait', '1')),
        }
        self.t = timer
        self.log = LogWrapper('peoplesearch.LDAPController')
        statsd = settings.get('statsd_factory')()
        self.config, self.servers, self.orgpools = parse_ldap_config(ldap_config, ca_certs,
                                                                     max_idle, max_connections,
                                                                     timeouts)
        self.health_check_interval = 10
        self.statsd = statsd
        self.statsd_hostid = settings.get('statsd_hostid')

    def get_ldap_config(self):
        return self.config

    def get_base_dn(self, org):
        return self.get_ldap_config()[org]['base_dn']

    def handle_exclude(self, org, search):
        exclude_filter = self.get_ldap_config()[org].get('exclude', None)
        if exclude_filter:
            search = "(&{}(!{}))".format(search, exclude_filter)
        return search

    def _org_statsd_key(self, org, key, with_hostid):
        if with_hostid:
            key = '{}.{}'.format(self.statsd_hostid, key)
        return 'ldap.org.{}.{}'.format(org.replace('.', '_'), key)

    def search(self, org, base_dn, search_filter, scope, attributes, size_limit=None):
        with self.t.time(self._org_statsd_key(org, 'search_ms', False)):
            self.statsd.incr(self._org_statsd_key(org, 'searches', True))
            return self.orgpools[org].search(base_dn, search_filter, scope, attributes=attributes,
                                             size_limit=size_limit)

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

    def health_check_thread(self):
        while True:
            servers = list(self.servers.values())
            sleeptime = self.health_check_interval / len(servers)
            for server in servers:
                server.check_connection()
                time.sleep(sleeptime)
            for org, orgpool in self.orgpools.items():
                self.statsd.gauge(self._org_statsd_key(org, 'alive_servers', True),
                                  len(orgpool.alive_servers()))
