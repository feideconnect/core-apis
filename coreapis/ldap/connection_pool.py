import contextlib
import enum
import queue
import random
import ssl
import threading

import ldap3


class ConnectionPool(object):
    def __init__(self, host, port, username, password, max_idle, max_total, timeouts, ca_certs):
        self.username = username
        self.password = password
        self.max_total = max_total
        self.timeouts = timeouts
        self.idle = queue.Queue(max_idle)
        self.tls = ldap3.Tls(validate=ssl.CERT_REQUIRED,
                             ca_certs_file=ca_certs)
        self.server = ldap3.Server(host, port=port, use_ssl=True,
                                   connect_timeout=self.timeouts['connect'], tls=self.tls)
        self.create_semaphore = threading.Semaphore(max_total)
        self.down_count = 3  # Based on haproxy "fall" option default
        self.up_count = 2  # Based on haproxy "rise" option default
        self.alive = True
        self.last_result = HealthCheckResult.ok
        self.result_count = self.up_count

    def _create(self):
        if self.create_semaphore.acquire(False):
            return ldap3.Connection(self.server, auto_bind=True,
                                    user=self.username, password=self.password,
                                    client_strategy=ldap3.STRATEGY_SYNC,
                                    check_names=True)
        return None

    def _destroy(self):
        self.create_semaphore.release()

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
            return None

    def _release(self, connection):
        try:
            if not connection.closed and connection.bound:
                self.idle.put(connection, False)
            else:
                self._destroy()
        except queue.Full:
            connection.unbind()
            self._destroy()

    @contextlib.contextmanager
    def connection(self):
        try:
            connection = self._get()
            yield connection
        finally:
            self._release(connection)

    def _try_connection(self):
        with self.connection() as connection:
            try:
                connection.search("dc=example,dc=org", "(&(uid>1000)(uid<1000))",
                                  ldap3.BASE, ['uid'], 1)
                return HealthCheckResult.ok
            except:
                return HealthCheckResult.fail

    def check_connection(self):
        result = self._try_connection()
        if result != self.last_result:
            self.last_result = result
            self.result_count = 1
        else:
            self.result_count += 1
        if result == HealthCheckResult.fail and self.result_count == self.down_count:
            self.alive = False
        elif result == HealthCheckResult.ok and self.result_count == self.up_count:
            self.alive = True


class HealthCheckResult(enum.Enum):
    ok = 1
    fail = 2


class RetryPool(object):
    def __init__(self, servers):
        self.servers = servers

    def search(self, base_dn, search_filter, scope, attributes, size_limit=None):
        exception = None
        alive_servers = {server for server in self.servers if server.alive}
        if not alive_servers:
            alive_servers = self.servers
        for server in random.sample(alive_servers, len(alive_servers)):
            with server.connection() as connection:
                try:
                    connection.search(base_dn, search_filter, scope, attributes=attributes,
                                      size_limit=size_limit)
                    return connection.response
                except ldap3.LDAPExceptionError as ex:
                    exception = ex
        raise exception

    def do_health_checks(self):
        for server in self.servers:
            server.check_connection()
