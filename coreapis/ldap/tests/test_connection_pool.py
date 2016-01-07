from collections import defaultdict
from unittest import TestCase
import threading
import time

import ldap3
#import ldap3.core
#import ldap3.core.exceptions
import mock
import pytest

from coreapis.ldap.connection_pool import (
    ConnectionPool,
    HealthCheckResult,
    RetryPool,
    TooManyConnectionsException
)


class TestConnectionPool(TestCase):

    def setUp(self):
        self.pool = ConnectionPool("ldap.example.org", 636, None, None,
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
    def test_create_connection_failure(self, mock_connection):
        mock_connection.side_effect = RuntimeError
        with pytest.raises(RuntimeError):
            self.pool._create()
        assert self.pool.create_semaphore._value == 5

    @mock.patch('ldap3.Connection')
    def test_get_max_connections(self, mock_connection):
        assert self.pool._get()
        assert self.pool._get()
        assert self.pool._get()
        assert self.pool._get()
        assert self.pool._get()
        with pytest.raises(TooManyConnectionsException):
            self.pool._get()

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

    def test_context_connection_failure(self):
        self.pool._get = mock.Mock(return_value=None)
        self.pool._release = mock.Mock()
        with self.pool.connection():
            pass
        assert not self.pool._release.called

    @mock.patch('ldap3.Connection')
    def test_try_connection(self, connection):
        assert self.pool._try_connection() == HealthCheckResult.ok
        connection.return_value.search.side_effect = RuntimeError
        assert self.pool._try_connection() == HealthCheckResult.fail

    def test_check_connection(self):
        cp = self.pool
        cp._try_connection = mock.MagicMock(return_value=HealthCheckResult.ok)
        assert cp.alive
        assert cp.last_result == HealthCheckResult.ok
        assert cp.result_count == 2
        cp.check_connection()
        assert cp.last_result == HealthCheckResult.ok
        assert cp.result_count == 3

        cp._try_connection.return_value = HealthCheckResult.fail
        cp.check_connection()
        assert cp.last_result == HealthCheckResult.fail
        assert cp.result_count == 1
        assert cp.alive
        cp.check_connection()
        assert cp.last_result == HealthCheckResult.fail
        assert cp.result_count == 2
        assert cp.alive
        cp.check_connection()
        assert cp.last_result == HealthCheckResult.fail
        assert cp.result_count == 3
        assert not cp.alive

        cp._try_connection.return_value = HealthCheckResult.ok
        cp.check_connection()
        assert cp.last_result == HealthCheckResult.ok
        assert cp.result_count == 1
        assert not cp.alive
        cp.check_connection()
        assert cp.last_result == HealthCheckResult.ok
        assert cp.result_count == 2
        assert cp.alive


class TestRetryPool(TestCase):
    def setUp(self):
        self.cp1 = mock.MagicMock(name="cp1")
        self.cp2 = mock.MagicMock(name="cp2")
        self.cp3 = mock.MagicMock(name="cp3")
        self.sp = RetryPool([self.cp1, self.cp2, self.cp3])

    def tearDown(self):
        pass

    def test_do_health_checks(self):
        self.sp.do_health_checks()
        self.cp1._check_connection.assert_any_calls()
        self.cp2._check_connection.assert_any_calls()
        self.cp3._check_connection.assert_any_calls()

    @mock.patch('random.sample')
    def test_search(self, sample):
        sample.side_effect = lambda x, y: sorted(x, key=str)
        self.cp1.connection().__enter__.return_value.search.side_effect = ldap3.LDAPExceptionError
        self.cp2.connection().__enter__.return_value.response = "token"
        self.cp3.connection().__enter__.return_value.response = "token2"
        assert self.sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1) == "token"
        assert self.cp1.connection().__enter__.return_value.search.called

        self.cp2.alive = False
        assert self.sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1) == "token2"

        self.cp1.alive = False
        self.cp3.alive = False
        assert self.sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1) == "token"

        self.cp1.alive = True
        with pytest.raises(ldap3.LDAPExceptionError):
            self.sp.search("dc=example,dc=org", "uid=1000", "BASE", ["uid"], 1)