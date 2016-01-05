from collections import defaultdict
from unittest import TestCase
import threading
import time

import ldap3
#import ldap3.core
#import ldap3.core.exceptions
import mock
import pytest

from coreapis.ldap.connection_pool import ConnectionPool, ServerPool, HealthCheckResult


class TestConnectionPool(TestCase):

    def setUp(self):
        self.pool = ConnectionPool("ldap.example.org:636", None, None,
                                   2, 5, defaultdict(lambda: 1), None)

    def tearDown(self):
        pass

    @mock.patch('ldap3.Connection')
    def test_get(self, mock_connection):
        self.pool._get()
        assert self.pool.idle.empty()
        mock_connection.assert_called_once_with(self.pool.server,
                                                auto_bind=True,
                                                user=None,
                                                password=None,
                                                client_strategy=ldap3.STRATEGY_SYNC,
                                                check_names=True)
        assert self.pool.create_semaphore._value == 4

    @mock.patch('ldap3.Connection')
    def test_create(self, mock_connection):
        assert self.pool._create()
        assert self.pool._create()
        assert self.pool._create()
        assert self.pool._create()
        assert self.pool._create()
        assert not self.pool._create()
        self.pool._destroy()
        assert self.pool._create()
        assert not self.pool._create()

    @mock.patch('ldap3.Connection')
    def test_get_max_connections(self, mock_connection):
        assert self.pool._get()
        assert self.pool._get()
        assert self.pool._get()
        assert self.pool._get()
        assert self.pool._get()
        assert not self.pool._get()

    @mock.patch('ldap3.Connection')
    def test_release_ok(self, mock_connection):
        instance = mock_connection.return_value
        instance.closed = False
        instance.bound = True
        self.pool._release(self.pool._get())
        assert self.pool.idle.qsize() == 1

    @mock.patch('ldap3.Connection')
    def test_release_bad(self, mock_connection):
        instance = mock_connection.return_value
        instance.closed = True
        instance.bound = True
        self.pool._release(self.pool._get())
        assert self.pool.idle.empty()
        instance.closed = True
        instance.bound = False
        self.pool._release(self.pool._get())
        assert self.pool.idle.empty()
        instance.closed = False
        instance.bound = False
        self.pool._release(self.pool._get())
        assert self.pool.idle.empty()

    @mock.patch('ldap3.Connection')
    def test_release_full(self, mock_connection):
        instance = mock_connection.return_value
        instance.closed = False
        instance.bound = True
        instances = [self.pool._get() for _ in range(5)]
        for i in instances:
            self.pool._release(i)
        assert self.pool.idle.full()
        assert self.pool.idle.qsize() == 2
        assert self.pool.create_semaphore._value == 3

    @mock.patch('ldap3.Connection')
    def test_get_idle(self, mock_connection):
        instance = mock_connection.return_value
        instance.closed = False
        instance.bound = True
        con = self.pool._get()
        self.pool._release(con)
        assert not self.pool.idle.empty()
        con = self.pool._get()
        assert self.pool.idle.empty()
        mock_connection.assert_called_once_with(self.pool.server,
                                                auto_bind=True, user=None, password=None,
                                                client_strategy=ldap3.STRATEGY_SYNC,
                                                check_names=True)
        assert self.pool.create_semaphore._value == 4

    @mock.patch('ldap3.Connection')
    def test_get_wait_for_idle(self, mock_connection):
        instance = mock_connection.return_value
        instance.closed = False
        instance.bound = True
        instances = [self.pool._get() for _ in range(5)]

        def releasethread():
            time.sleep(0.1)
            for i in instances:
                self.pool._release(i)
        threading.Thread(target=releasethread).start()
        assert self.pool._get()

    def test_context(self):
        self.pool._get = mock.Mock(return_value="token")
        self.pool._release = mock.Mock()
        with self.pool.connection() as con:
            assert con == "token"
        self.pool._release.assert_called_with("token")

    def test_context_exception(self):
        self.pool._get = mock.Mock(return_value="token")
        self.pool._release = mock.Mock()
        with pytest.raises(RuntimeError):
            with self.pool.connection():
                raise RuntimeError()
        self.pool._release.assert_called_with("token")

    @mock.patch('ldap3.Connection')
    def test_try_connection(self, connection):
        assert self.pool._try_connection() == HealthCheckResult.ok
        connection.return_value.search.side_effect = RuntimeError
        assert self.pool._try_connection() == HealthCheckResult.fail

    @mock.patch('ldap3.Server')
    def test_create_no_port(self, mock_server):
        ConnectionPool("example.com", None, None, 1, 1, {'connect': 2}, None)
        mock_server.assert_called_with("example.com", port=None,
                                       use_ssl=True, connect_timeout=2, tls=mock.ANY)


class TestServerPool(TestCase):
    def setUp(self):
        pass

    def tearDown(self):
        pass

    def test_check_connection(self):
        cp = mock.MagicMock()
        cp._try_connection.return_value = HealthCheckResult.ok
        sp = ServerPool([cp])
        assert cp in sp.alive_servers
        assert sp.last_result[0] == HealthCheckResult.ok
        assert sp.result_count[0] == 1
        sp._check_connection(0)
        assert sp.last_result[0] == HealthCheckResult.ok
        assert sp.result_count[0] == 2

        cp._try_connection.return_value = HealthCheckResult.fail
        sp._check_connection(0)
        assert sp.last_result[0] == HealthCheckResult.fail
        assert sp.result_count[0] == 1
        assert cp in sp.alive_servers
        sp._check_connection(0)
        assert sp.last_result[0] == HealthCheckResult.fail
        assert sp.result_count[0] == 2
        assert cp in sp.alive_servers
        sp._check_connection(0)
        assert sp.last_result[0] == HealthCheckResult.fail
        assert sp.result_count[0] == 3
        assert cp not in sp.alive_servers

        cp._try_connection.return_value = HealthCheckResult.ok
        sp._check_connection(0)
        assert sp.last_result[0] == HealthCheckResult.ok
        assert sp.result_count[0] == 1
        assert cp not in sp.alive_servers
        sp._check_connection(0)
        assert sp.last_result[0] == HealthCheckResult.ok
        assert sp.result_count[0] == 2
        assert cp in sp.alive_servers

    def test_do_health_checks(self):
        sp = ServerPool([mock.MagicMock()] * 3)
        sp._check_connection = mock.MagicMock()
        sp.do_health_checks()
        sp._check_connection.assert_any_calls(0)
        sp._check_connection.assert_any_calls(1)
        sp._check_connection.assert_any_calls(2)

    @mock.patch('random.sample')
    def test_search(self, sample):
        sample.side_effect = lambda x, y: sorted(x, key=str)
        cp1 = mock.MagicMock(name="cp1")
        cp2 = mock.MagicMock(name="cp2")
        cp3 = mock.MagicMock(name="cp3")
        sp = ServerPool([cp1, cp2, cp3])
        cp1.connection().__enter__.return_value.search.side_effect = ldap3.LDAPExceptionError
        cp2.connection().__enter__.return_value.search.return_value = "token"
        cp3.connection().__enter__.return_value.search.return_value = "token2"
        assert sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1) == "token"
        assert cp1.connection().__enter__.return_value.search.called

        sp.alive_servers = [cp1, cp3]
        assert sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1) == "token2"

        sp.alive_servers = []
        assert sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1) == "token"

        sp.alive_servers = [cp1]
        with pytest.raises(ldap3.LDAPExceptionError):
            sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1)
