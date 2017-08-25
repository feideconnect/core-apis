import contextlib
import enum
import queue
import random
import ssl
import threading

import ldap3
import ldap3.core.exceptions

from coreapis.utils import LogWrapper


class TooManyConnectionsException(ldap3.core.exceptions.LDAPExceptionError):
    pass


class ConnectionPool(object):
    def __init__(self, host, port, username, password, max_idle,
                 max_total, timeouts, ca_certs, statsd):
        self.username = username
        self.password = password
        self.max_total = max_total
        self.timeouts = timeouts
        self.idle = queue.Queue(max_idle)
        self.tls = ldap3.Tls(validate=ssl.CERT_REQUIRED,
                             ca_certs_file=ca_certs)
        self.host = host
        self.port = port
        if port:
            self.target = "{}:{}".format(host, port)
        else:
            self.target = host
        self.statsd_target = self.target.replace('.', '_').replace(':', '_').replace('/', '.')
        self.create_semaphore = threading.Semaphore(max_total)
        self.down_count = 3  # Based on haproxy "fall" option default
        self.up_count = 2  # Based on haproxy "rise" option default
        self.alive = True
        self.last_result = HealthCheckResult.ok
        self.result_count = self.up_count
        self.log = LogWrapper('ldap.ConnectionPool', target=self.target)
        self.statsd = statsd

    def _statsd_key(self, key):
        return 'ldap.servers.{target}.{key}'.format(target=self.statsd_target, key=key)

    def _create(self):
        if self.create_semaphore.acquire(False):
            try:
                self.log.debug("Creating new connection")
                server = ldap3.Server(self.host, port=self.port, use_ssl=True,
                                      connect_timeout=self.timeouts['connect'], tls=self.tls)
                conn = ldap3.Connection(server, auto_bind=True,
                                        user=self.username, password=self.password,
                                        client_strategy=ldap3.SYNC,
                                        check_names=True)
                self.statsd.gauge(self._statsd_key('connections'),
                                  self.max_total - self.create_semaphore._value)
                return conn
            except:
                self.create_semaphore.release()
                raise
        return None

    def _destroy(self):
        self.create_semaphore.release()
        self.log.debug("Connection destroyed")
        self.statsd.gauge(self._statsd_key('connections'),
                          self.max_total - self.create_semaphore._value)

    def _get(self):
        try:
            con = self.idle.get_nowait()
            return con
        except queue.Empty:
            pass
        con = self._create()
        if con:
            return con
        try:
            con = self.idle.get(timeout=self.timeouts['connection_wait'])
            return con
        except queue.Empty:
            raise TooManyConnectionsException()

    def _release(self, connection):
        try:
            if not connection.closed and connection.bound:
                self.idle.put(connection, False)
            else:
                self._destroy()
        except queue.Full:
            connection.unbind()
            self._destroy()

    def status(self):
        self.log.info("Connection pool status",
                      idle_connections=self.idle.qsize(),
                      remaining_connections=self.create_semaphore._value)

    @contextlib.contextmanager
    def connection(self):
        connection = None
        try:
            connection = self._get()
            yield connection
        except:
            if self.alive and connection:
                self.log.debug("Connection status after exception",
                               closed=connection.closed,
                               bound=connection.bound)
            if connection:
                connection.closed = True
            raise
        finally:
            if connection:
                self._release(connection)
            self.statsd.gauge(self._statsd_key('idle_connections'),
                              self.idle.qsize())

    def _try_connection(self):
        try:
            with self.connection() as connection:
                connection.search("", "(objectClass=*)", ldap3.BASE,
                                  attributes=['vendorversion'], size_limit=1)
                return HealthCheckResult.ok
        except TooManyConnectionsException:
            self.log.warn("Failed to get connection. Pool full?")
            self.status()
            return HealthCheckResult.ok
        except Exception as ex:
            if self.alive:
                self.log.warn("Failed health check", exception=str(ex),
                              exception_class=ex.__class__.__name__)
            return HealthCheckResult.fail

    def check_connection(self):
        result = self._try_connection()
        if result != self.last_result:
            self.last_result = result
            self.result_count = 1
        else:
            self.result_count += 1
        if result == HealthCheckResult.fail and self.result_count == self.down_count:
            self.log.info("Server marked as down")
            self.alive = False
        elif result == HealthCheckResult.ok and self.result_count == self.up_count:
            self.log.info("Server back up")
            self.alive = True


class HealthCheckResult(enum.Enum):
    ok = 1
    fail = 2


class RetryPool(object):
    def __init__(self, servers, org, statsd):
        self.servers = servers
        self.org = org
        self.statsd_org = org.replace('.', '_')
        self.statsd = statsd

    def search(self, base_dn, search_filter, scope, attributes, size_limit=None):
        exception = RuntimeError('No servers alive')
        candidate_servers = self.alive_servers()
        if not candidate_servers:
            candidate_servers = self.servers
        if len(candidate_servers) == 1:
            # If organization only has one server, retry operation on
            # the same server in case connection has failed since last
            # connection
            s = candidate_servers.pop()
            candidate_servers = [s, s]
        for server in random.sample(candidate_servers, len(candidate_servers)):
            try:
                with server.connection() as connection:
                    connection.search(base_dn, search_filter, scope, attributes=attributes,
                                      size_limit=size_limit)
                    self.statsd.incr('ldap.org.{org}.successes'.format(org=self.statsd_org))
                    return connection.response
            except ldap3.core.exceptions.LDAPExceptionError as ex:
                self.statsd.incr('ldap.org.{org}.failures'.format(org=self.statsd_org))
                exception = ex
        raise exception

    def alive_servers(self):
        return {server for server in self.servers if server.alive}

    def do_health_checks(self):
        for server in self.servers:
            server.check_connection()
