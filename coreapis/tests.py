import unittest
import mock
import uuid
import datetime
from webtest import TestApp
import json

from pyramid import testing
from . import main, middleware


class ViewTests(unittest.TestCase):
    def setUp(self):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
        })
        mw = middleware.MockAuthMiddleware(app)
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_test_open(self):
        res = self.testapp.get('/test/open', status=200)
        out = json.loads(str(res.body, 'UTF-8'))
        assert 'status' in out
        assert out['status'] == 'open'

    def test_test_client_unauthorized(self):
        res = self.testapp.get('/test/client', status=403)

    def test_test_user_unauthorized(self):
        res = self.testapp.get('/test/user', status=403)


class TokenValidationTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        from .middleware import CassandraMiddleware
        self.middleware = CassandraMiddleware(None, None, None, None)
        self.token = {
            'clientid': uuid.uuid4(),
            'userid': uuid.uuid4(),
            'access_token': uuid.uuid4(),
            'validuntil': datetime.datetime.now(),
        }

    def tearDown(self):
        pass

    def test_expired_token(self):
        self.token['validuntil'] -= datetime.timedelta(days=10)
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) == False
