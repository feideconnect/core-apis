from unittest import TestCase
import mock
import uuid

from coreapis.gk import controller


class TestController(TestCase):
    basic_backend = {
        'id': 'testbackend',
        'endpoints': [
            'http://localhost:1234',
            'http://localhost:1235'],
        'requireuser': False,
        'trust': {
            "type": "basic",
            "username": "user",
            "password": "foobar",
        }
    }
    user = {
        'userid': uuid.UUID('0186bdb5-5f68-436a-8453-6efe4a66cf1e'),
        'userid_sec': set(['feide:test@feide.no', 'mail:test.user@feide.no', 'nin:01234567890']),
    }
    client = {
        'id': uuid.UUID('b708800e-a9b9-4a2e-834d-a75c251c12f8'),
        'scopes': ['danger', 'alert'],
    }

    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.controller = controller.GkController([], 'keyspace', None)

    def basic_asserts(self, headers):
        assert 'endpoint' in headers
        assert headers['endpoint'] == 'http://localhost:1234' or \
            headers['endpoint'] == 'http://localhost:1235'
        assert 'Authorization' in headers
        assert 'clientid' in headers
        assert headers['clientid'] == 'b708800e-a9b9-4a2e-834d-a75c251c12f8'
        assert headers['gatekeeper'] == 'testbackend'

    def test_require_user(self):
        backend = self.basic_backend.copy()
        backend['requireuser'] = True
        self.session.get_apigk.return_value = backend
        headers = self.controller.info(
            'testbackend', self.client, None, ['gk_testbackend'], {}, None)
        assert headers is None

    def test_expose_nothing(self):
        self.session.get_apigk.return_value = self.basic_backend
        self.session.get_token.return_value = {
            'access_token': 'my secret',
            'scope': ['userid'],
        }
        headers = self.controller.info(
            'testbackend', self.client, self.user, ['gk_testbackend'], {}, None)
        assert len(headers) == 6
        self.basic_asserts(headers)

    def test_no_user(self):
        self.session.get_apigk.return_value = self.basic_backend
        self.session.get_token.return_value = {
            'access_token': 'my secret',
            'scope': ['userid'],
        }
        headers = self.controller.info('testbackend', self.client, None, ['gk_testbackend'], {
            'testbackend': 'my secret',
        }, None)
        assert len(headers) == 7
        self.basic_asserts(headers)
        assert 'userid' not in headers
        assert 'token' in headers

    def test_expose_userid(self):
        backend = self.basic_backend.copy()
        self.session.get_apigk.return_value = backend
        self.session.get_token.return_value = {
            'access_token': 'my secret',
            'scope': ['userid'],
        }
        headers = self.controller.info('testbackend', self.client, self.user,
                                       ['gk_testbackend'], {
                                           'testbackend': 'my secret',
                                       }, None)
        assert len(headers) == 8
        self.basic_asserts(headers)
        assert 'userid' in headers
        assert headers['userid'] == '0186bdb5-5f68-436a-8453-6efe4a66cf1e'
        assert 'userid-feide' not in headers
        assert 'userid-nin' not in headers

    def test_acr(self):
        backend = self.basic_backend.copy()
        self.session.get_apigk.return_value = backend
        self.session.get_token.return_value = {
            'access_token': 'my secret',
            'scope': ['userid'],
        }
        headers = self.controller.info('testbackend', self.client, self.user,
                                       ['gk_testbackend'], {
                                           'testbackend': 'my secret',
                                       }, "level 4")
        assert len(headers) == 8
        self.basic_asserts(headers)
        assert 'userid' in headers
        assert headers['userid'] == '0186bdb5-5f68-436a-8453-6efe4a66cf1e'
        assert 'userid-feide' not in headers
        assert 'userid-nin' not in headers
        assert 'acr' in headers
        assert headers['acr'] == "level 4"

    def test_expose_feideid(self):
        backend = self.basic_backend.copy()
        self.session.get_apigk.return_value = backend
        self.session.get_token.return_value = {
            'access_token': 'my secret',
            'scope': ['userid', 'userid-feide'],
        }
        headers = self.controller.info('testbackend', self.client, self.user,
                                       ['gk_testbackend'], {'testbackend': 'my secret'}, None)
        assert len(headers) == 9
        self.basic_asserts(headers)
        assert 'userid' in headers
        assert headers['userid'] == '0186bdb5-5f68-436a-8453-6efe4a66cf1e'
        assert 'userid-sec' in headers
        assert headers['userid-sec'] == 'feide:test@feide.no'

    def test_expose_only_nin(self):
        backend = self.basic_backend.copy()
        self.session.get_apigk.return_value = backend
        self.session.get_token.return_value = {
            'access_token': 'my secret',
            'scope': ['userid-nin'],
        }
        headers = self.controller.info('testbackend', self.client, self.user,
                                       ['gk_testbackend'], {'testbackend': 'my secret'}, None)
        assert len(headers) == 8
        self.basic_asserts(headers)
        assert 'userid' not in headers
        assert 'userid-sec' in headers
        assert headers['userid-sec'] == 'nin:01234567890'


class TestAuthHeader(TestCase):
    def test_token(self):
        trust = {
            'type': 'bearer',
            'token': 'abc123'
        }
        header, value = controller.auth_header(trust)
        assert header == 'Authorization'
        assert value == 'Bearer abc123'

    def test_basic(self):
        trust = {
            'type': 'basic',
            'username': 'username',
            'password': 'password',
        }
        header, value = controller.auth_header(trust)
        assert header == 'Authorization'
        assert value == 'Basic dXNlcm5hbWU6cGFzc3dvcmQ='
