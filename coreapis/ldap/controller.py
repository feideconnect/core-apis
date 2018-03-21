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
        self.timer = timer
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
        self.last_health_check = 0
        self.last_health_check_exception = 0

    @staticmethod
    def get_server_key(server, orgconf):
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
        return (host, port, user, password)

    def get_key_servers(self, server_key):
        if server_key in self.servers:
            return self.servers[server_key]
        (host, port, user, password) = server_key
        self.log.debug("Found new ldap server: {}:{} - {}".format(host, port, user))
        return ConnectionPool(host, port, user, password,
                              self.max_idle, self.max_connections,
                              self.timeouts, self.ca_certs,
                              self.host_statsd)

    def parse_ldap_config(self):
        mtime = os.stat(self.ldap_config).st_mtime
        if mtime == self.config_mtime:
            return False

        with open(self.ldap_config) as fh:
            config = json.load(fh)
        servers = {}
        orgpools = {}
        for org in config:
            orgconf = config[org]
            org_connection_pools = []
            for server in orgconf['servers']:
                server_key = self.get_server_key(server, orgconf)
                if server_key not in servers:
                    servers[server_key] = self.get_key_servers(server_key)
                org_connection_pools.append(servers[server_key])
            if org in self.orgpools:
                orgpools[org] = self.orgpools[org]
                orgpools[org].servers = org_connection_pools
            else:
                self.log.debug("Adding connection pool for organization {}".format(org))
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
        with self.timer.time(self._org_statsd_key(org, 'search_ms')):
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
                               ldap3.SUBTREE,
                               attributes=attributes, size_limit=1)
        if not res:
            self.log.debug('Could not find user for %s' % feideid)
            raise KeyError('User not found')
        if len(res) > 1:
            self.log.warn('Multiple matches to eduPersonPrincipalName')
        return res[0]['attributes']

    def health_check_thread(self, parent=None):
        while True:
            try:
                servers = list(self.servers.values())
                sleeptime = self.health_check_interval / len(servers)
                for server in servers:
                    if parent and not parent.is_alive():
                        self.log.info("Parent is not alive any more, shutting down "
                                      "ldap health check thread")
                        return
                    if self.parse_ldap_config():
                        break
                    server.check_connection()
                    time.sleep(sleeptime)
                orgpools = self.orgpools.items()
                for org, orgpool in orgpools:
                    self.host_statsd.gauge(self._org_statsd_key(org, 'alive_servers'),
                                           len(orgpool.alive_servers()))
                self.last_health_check = time.time()
            except Exception as ex:  # pylint: disable=broad-except
                self.log.warn('Exception in health check thread', exception=str(ex))
                self.last_health_check_exception = time.time()
                time.sleep(1)

    def status(self):
        status = {}
        for org, orgpool in self.orgpools.items():
            status[org] = {
                'servers': len(orgpool.servers),
                'alive_servers': len(orgpool.alive_servers()),
                'last_health_check': self.last_health_check,
                'last_health_check_exception': self.last_health_check_exception,
            }
        return status
