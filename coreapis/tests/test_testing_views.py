import unittest
from webtest import TestApp
import mock
from pyramid import testing
from coreapis import main, middleware


def parse_auth_params(params):
    items = params.split(", ")
    result = {}
    for item in items:
        k, v = item.split('=', 1)
        k = k.strip()
        v = v.strip()
        assert v[0] == '"'
        assert v[-1] == '"'
        v = v[1:-1]
        result[k] = v
    return result


class ViewTests(unittest.TestCase):
    @mock.patch('coreapis.peoplesearch.controller.LDAPController')
    def setUp(self, ldapcontroller):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
        }, enabled_components='testing')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_test_open(self):
        res = self.testapp.get('/test/open', status=200)
        out = res.json
        assert 'status' in out
        assert out['status'] == 'open'

    def test_test_client_unauthorized(self):
        res = self.testapp.get('/test/client', status=401)
        authtype, params = res.www_authenticate
        assert authtype == "Bearer"
        params = parse_auth_params(params)
        assert 'realm' in params
        assert params['realm'] == 'test realm'
        assert len(params) == 1
        assert 'message' in res.json

    def test_test_client_authenticated(self):
        headers = {'Authorization': 'Bearer client_token'}
        res = self.testapp.get('/test/client', status=200, headers=headers)
        out = res.json
        assert 'client' in out
        assert 'scopes' in out['client']

    def test_test_user_unauthorized(self):
        res = self.testapp.get('/test/user', status=401)
        authtype, params = res.www_authenticate
        assert authtype == "Bearer"
        params = parse_auth_params(params)
        assert 'realm' in params
        assert params['realm'] == 'test realm'
        assert len(params) == 1
        assert 'message' in res.json

    def test_test_user_authenticated(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/test/user', status=200, headers=headers)
        out = res.json
        assert 'user' in out
        assert 'email' in out['user']

    def test_test_scope_missing(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/test/scope', status=401, headers=headers)
        authtype, params = res.www_authenticate
        assert authtype == "Bearer"
        params = parse_auth_params(params)
        assert 'realm' in params
        assert params['realm'] == 'test realm'
        assert len(params) == 3
        assert 'error' in params
        assert params['error'] == 'invalid_scope'
        assert 'error_description' in params
        assert 'message' in res.json

    def test_test_scope_valid(self):
        headers = {'Authorization': 'Bearer client_token'}
        res = self.testapp.get('/test/scope', status=200, headers=headers)
        out = res.json
        assert 'scopes' in out
        assert 'test' in out['scopes']

    def test_bad_token(self):
        headers = {'Authorization': 'Bearer bad token!'}
        res = self.testapp.get('/test/scope', status=401, headers=headers)
        authtype, params = res.www_authenticate
        assert authtype == "Bearer"
        params = parse_auth_params(params)
        assert 'realm' in params
        assert params['realm'] == 'test realm'
        assert len(params) == 3
        assert 'error' in params
        assert params['error'] == 'invalid_token'
        assert 'error_description' in params
        assert 'message' in res.json

    def test_bad_path(self):
        res = self.testapp.get('/test/not_found', status=404)
        assert 'message' in res.json

    def test_exception_handler(self):
        res = self.testapp.get('/test/crash', status=500)
        assert 'message' in res.json
