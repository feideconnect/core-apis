from unittest import TestCase
import mock

from coreapis.gk import controller


class TestController(TestCase):
    basic_backend = {
        'id': 'testbackend',
        'endpoints': [
            'http://localhost:1234',
            'http://localhost:1235'],
        'expose': {},
        'requireuser': False,
        'trust': {
            "type": "basic",
            "username": "user",
            "password": "foobar",
        }
    }

    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.controller = controller.GkController([], 'keyspace')

    def basic_asserts(self, headers):
        assert 'endpoint' in headers
        assert headers['endpoint'] == 'http://localhost:1234' or \
            headers['endpoint'] == 'http://localhost:1235'
        assert 'Authorization' in headers

    def test_require_user(self):
        backend = self.basic_backend.copy()
        backend['requireuser'] = True
        self.session.get_gk_backend.return_value = backend
        headers = self.controller.info('testbackend', {}, None, [])
        assert headers is None

    def test_expose_nothing(self):
        self.session.get_gk_backend.return_value = self.basic_backend
        headers = self.controller.info('testbackend', {}, None, [])
        assert len(headers) == 2
        self.basic_asserts(headers)

    def test_expose_scopes(self):
        backend = self.basic_backend.copy()
        backend['expose']['scopes'] = True
        self.session.get_gk_backend.return_value = backend
        headers = self.controller.info('testbackend', {'scopes': ['danger', 'alert']},
                                       None, ['gk_testbackend_good', 'gk_testbackend_nice', 'secrit'])
        assert len(headers) == 3
        assert 'scopes' in headers
        assert headers['scopes'] == 'good,nice'


class TestAuthHeader(TestCase):
    def test_token(self):
        trust = {
            'type': 'token',
            'token': 'abc123'
        }
        header, value = controller.auth_header(trust)
        assert header == 'Auth'
        assert value == 'abc123'

    def test_basic(self):
        trust = {
            'type': 'basic',
            'username': 'username',
            'password': 'password',
        }
        header, value = controller.auth_header(trust)
        assert header == 'Authorization'
        assert value == 'Basic dXNlcm5hbWU6cGFzc3dvcmQ='
