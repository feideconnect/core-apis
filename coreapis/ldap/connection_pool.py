import contextlib
import queue
import ssl
import threading

import ldap3


class ConnectionPool(object):
    def __init__(self, server, username, password, max_idle, max_total, timeouts, ca_certs):
        if ':' in server:
            host, port = server.split(':', 1)
            port = int(port)
        else:
            host, port = server, None
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
