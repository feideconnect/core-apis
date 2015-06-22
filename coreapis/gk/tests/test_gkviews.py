import unittest
import mock
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware


class GkViewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='gk')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_options_notfound(self):
        self.session.get_apigk.side_effect = KeyError
        self.testapp.get('/gk/info/no_tfound', params={'method': 'OPTIONS'}, status=404)

    def test_get_no_token(self):
        self.testapp.get('/gk/info/no_access', status=401)

    def test_get_no_access(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/gk/info/no_access', headers=headers, status=403)

    def test_get_not_found(self):
        self.session.get_apigk.side_effect = KeyError
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.get('/gk/info/unittest', headers=headers, status=404)
