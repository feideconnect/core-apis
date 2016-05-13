import json
import os
import time

import ldap3

from coreapis.utils import ValidationError, LogWrapper
from .connection_pool import RetryPool, ConnectionPool


def validate_query(string):
    for char in ('(', ')', '*', '\\'):
        if char in string:
            raise ValidationError('Bad character in request')


class LDAPController(object):
    def __init__(self, settings):
        timer = settings.get('timer')
        self.ldap_config = settings.get('ldap_config_file', 'ldap-config.json')
        self.ca_certs = settings.get('ldap_ca_certs', None)
        self.max_idle = int(settings.get('ldap_max_idle_connections', '4'))
        self.max_connections = int(settings.get('ldap_max_connections', '10'))
        self.timeouts = {
            'connect': int(settings.get('ldap_connect_timeout', '1')),
            'connection_wait': int(settings.get('ldap_max_connection_pool_wait', '1')),
        }
        self.t = timer
        self.log = LogWrapper('peoplesearch.LDAPController')
        statsd = settings.get('statsd_factory')()
        self.host_statsd = settings.get('statsd_host_factory')()
        self.config = None
        self.config_mtime = 0
        self.servers = {}
        self.orgpools = {}
        self.parse_ldap_config()
        self.health_check_interval = 10
        self.statsd = statsd
        settings.get('status_methods', {})['ldap'] = self.status

    def parse_ldap_config(self):
        mtime = os.stat(self.ldap_config).st_mtime
        if mtime == self.config_mtime:
            return False

        self.log.debug("Reading ldap config")
        with open(self.ldap_config) as fh:
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
                server_key = (host, port, user, password)
                if server_key in servers:
                    pass
                elif server_key in self.servers:
                    servers[server_key] = self.servers[server_key]
                else:
                    self.log.debug("Found new ldap server: {}:{} - {}".format(host, port, user))
                    cp = ConnectionPool(host, port, user, password,
                                        self.max_idle, self.max_connections,
                                        self.timeouts, self.ca_certs,
                                        self.host_statsd)
                    servers[server_key] = cp
                org_connection_pools.append(servers[server_key])
            if org in self.orgpools:
                orgpools[org] = self.orgpools[org]
                orgpools[org].servers = org_connection_pools
            else:
                orgpool = RetryPool(org_connection_pools, org, self.host_statsd)
                orgpools[org] = orgpool
        self.config = config
        self.config_mtime = mtime
        self.servers = servers
        self.orgpools = orgpools
        return True

    def get_ldap_config(self):
        return self.config

    def get_base_dn(self, org):
        return self.get_ldap_config()[org]['base_dn']

    def handle_exclude(self, org, search):
        exclude_filter = self.get_ldap_config()[org].get('exclude', None)
        if exclude_filter:
            search = "(&{}(!{}))".format(search, exclude_filter)
        return search

    def _org_statsd_key(self, org, key):
        return 'ldap.org.{org}.{key}'.format(org=org.replace('.', '_'), key=key)

    def search(self, org, base_dn, search_filter, scope, attributes, size_limit=None):
        with self.t.time(self._org_statsd_key(org, 'search_ms')):
            self.host_statsd.incr(self._org_statsd_key(org, 'searches'))
            return self.orgpools[org].search(base_dn, search_filter, scope, attributes=attributes,
                                             size_limit=size_limit)

    def ldap_search(self, org, search_filter, scope, attributes, size_limit=None):
        base_dn = self.get_base_dn(org)
        search_filter = self.handle_exclude(org, search_filter)
        return self.search(org, base_dn, search_filter, scope, attributes, size_limit)

    def lookup_feideid(self, feideid, attributes):
        if '@' not in feideid:
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

    def health_check_thread(self, parent=None):
        while True:
            servers = list(self.servers.values())
            sleeptime = self.health_check_interval / len(servers)
            for server in servers:
                if parent and not parent.is_alive():
                    return
                if self.parse_ldap_config():
                    break
                server.check_connection()
                time.sleep(sleeptime)
            orgpools = self.orgpools.items()
            for org, orgpool in orgpools:
                self.host_statsd.gauge(self._org_statsd_key(org, 'alive_servers'),
                                       len(orgpool.alive_servers()))

    def status(self):
        status = {}
        for org, orgpool in self.orgpools.items():
            status[org] = {
                'servers': len(orgpool.servers),
                'alive_servers': len(orgpool.alive_servers()),
            }
        return status
