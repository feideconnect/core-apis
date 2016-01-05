from collections import defaultdict
from unittest import TestCase
import threading
import time

import ldap3
import mock
import pytest

from coreapis.ldap.connection_pool import ConnectionPool


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

    @mock.patch('ldap3.Server')
    def test_create_no_port(self, mock_server):
        ConnectionPool("example.com", None, None, 1, 1, {'connect': 2}, None)
        mock_server.assert_called_with("example.com", port=None,
                                       use_ssl=True, connect_timeout=2, tls=mock.ANY)
