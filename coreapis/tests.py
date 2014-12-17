import unittest
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
        out = json.loads(res.body)
        assert 'status' in out
        assert out['status'] == 'open'

    def test_test_client_unauthorized(self):
        res = self.testapp.get('/test/client', status=403)

    def test_test_user_unauthorized(self):
        res = self.testapp.get('/test/user', status=403)
