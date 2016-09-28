import unittest
import mock
import webtest
from pyramid import testing
from coreapis import main, middleware


class GkViewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'dataporten.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='gk', gk_header_prefix='X-GK-Test-')
        mw = middleware.GKMockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = webtest.TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_options_notfound(self):
        self.session.get_apigk.side_effect = KeyError
        self.session.apigk_allowed_dn.return_value = True
        headers = {'Gate-Keeper-DN': '/C=NO/CN=foo.example.com'}
        self.testapp.get('/gk/info/no_tfound', params={'method': 'OPTIONS'},
                         headers=headers, status=404)

    def test_get_no_token(self):
        self.session.apigk_allowed_dn.return_value = True
        self.session.get_apigk.return_value = {
            'endpoints': ['ep.example.com'],
            'requireuser': False,
            'trust': {
                'type': 'bearer',
                'token': 'foo',
            },
        }
        headers = {'Gate-Keeper-DN': '/C=NO/CN=foo.example.com'}
        self.testapp.get('/gk/info/no_access', status=401, headers=headers)
        self.session.get_apigk.return_value = {
            'allow_unauthenticated': False,
            'endpoints': ['ep.example.com'],
            'requireuser': False,
            'trust': {
                'type': 'bearer',
                'token': 'foo',
            },
        }
        self.testapp.get('/gk/info/no_access', status=401, headers=headers)

    def test_get_public(self):
        self.session.apigk_allowed_dn.return_value = True
        self.session.get_apigk.return_value = {
            'allow_unauthenticated': True,
            'endpoints': ['ep.example.com'],
            'requireuser': False,
            'trust': {
                'type': 'bearer',
                'token': 'foo',
            },
        }
        headers = {'Gate-Keeper-DN': '/C=NO/CN=foo.example.com'}
        resp = self.testapp.get('/gk/info/no_access', status=200, headers=headers)
        assert resp.headers['X-Gk-Test-Endpoint'] == 'ep.example.com'
        assert 'X-Gk-Test-Authorization' not in resp.headers
        assert 'X-Gk-Test-Gatekeeper' not in resp.headers
        assert 'X-Gk-Test-Clientid' not in resp.headers

    def test_get_no_access(self):
        headers = {
            'Authorization': 'Bearer user_token',
            'Gate-Keeper-DN': '/C=NO/CN=foo.example.com',
        }
        self.session.apigk_allowed_dn.return_value = True
        self.session.get_apigk.return_value = {
            'endpoints': ['ep.example.com'],
            'requireuser': False,
            'trust': {
                'type': 'bearer',
                'token': 'foo',
            },
        }
        self.testapp.get('/gk/info/no_access', headers=headers, status=403)

    def test_get_ok(self):
        headers = {
            'Authorization': 'Bearer user_token',
            'Gate-Keeper-DN': '/C=NO/CN=foo.example.com',
        }
        self.session.apigk_allowed_dn.return_value = True
        self.session.get_apigk.return_value = {
            'endpoints': ['ep.example.com'],
            'requireuser': False,
            'trust': {
                'type': 'bearer',
                'token': 'foo',
            },
        }
        resp = self.testapp.get('/gk/info/nicegk', headers=headers, status=200)
        assert resp.headers['X-Gk-Test-Authorization'] == 'Bearer foo'
        assert resp.headers['X-Gk-Test-Gatekeeper'] == 'nicegk'
        assert resp.headers['X-Gk-Test-Endpoint'] == 'ep.example.com'
        assert resp.headers['X-Gk-Test-Clientid'] == '00000000-0000-0000-0000-000000000002'

    def test_get_not_found(self):
        self.session.get_apigk.side_effect = KeyError
        self.session.apigk_allowed_dn.return_value = True
        headers = {
            'Authorization': 'Bearer client_token',
            'Gate-Keeper-DN': '/C=NO/CN=foo.example.com',
        }
        self.testapp.get('/gk/info/unittest', headers=headers, status=404)

    def test_options_bad_dn(self):
        self.session.apigk_allowed_dn.return_value = False
        headers = {'Gate-Keeper-DN': '/C=NO/CN=foo.example.com'}
        self.testapp.get('/gk/info/no_tfound', params={'method': 'OPTIONS'},
                         headers=headers, status=401)

    def test_get_bad_dn(self):
        self.session.apigk_allowed_dn.return_value = False
        headers = {'Gate-Keeper-DN': '/C=NO/CN=foo.example.com'}
        self.testapp.get('/gk/info/nicegk', headers=headers, status=401)
