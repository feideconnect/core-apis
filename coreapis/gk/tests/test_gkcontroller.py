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
        'expose': {},
        'requireuser': False,
        'trust': {
            "type": "basic",
            "username": "user",
            "password": "foobar",
        }
    }
    user = {
        'userid': uuid.UUID('0186bdb5-5f68-436a-8453-6efe4a66cf1e'),
        'userid_sec': set(['feide:test@feide.no', 'mail:test.user@feide.no']),
    }
    client = {
        'id': uuid.UUID('b708800e-a9b9-4a2e-834d-a75c251c12f8'),
        'scopes': ['danger', 'alert'],
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
        self.session.get_apigk.return_value = backend
        headers = self.controller.info('testbackend', {}, None, [])
        assert headers is None

    def test_expose_nothing(self):
        self.session.get_apigk.return_value = self.basic_backend
        headers = self.controller.info('testbackend', {}, self.user, [])
        assert len(headers) == 2
        self.basic_asserts(headers)

    def test_expose_scopes(self):
        backend = self.basic_backend.copy()
        backend['expose'] = dict(scopes=True)
        self.session.get_apigk.return_value = backend
        headers = self.controller.info('testbackend', self.client, None,
                                       ['gk_testbackend_good', 'gk_testbackend_nice', 'secrit'])
        assert len(headers) == 3
        self.basic_asserts(headers)
        assert 'scopes' in headers
        assert headers['scopes'] == 'good,nice'

    def test_expose_clientid(self):
        backend = self.basic_backend.copy()
        backend['expose'] = dict(clientid=True)
        self.session.get_apigk.return_value = backend
        headers = self.controller.info('testbackend', self.client, None,
                                       [])
        assert len(headers) == 3
        self.basic_asserts(headers)
        assert 'clientid' in headers
        assert headers['clientid'] == 'b708800e-a9b9-4a2e-834d-a75c251c12f8'

    def test_expose_userid(self):
        backend = self.basic_backend.copy()
        backend['expose'] = dict(userid=True)
        self.session.get_apigk.return_value = backend
        headers = self.controller.info('testbackend', self.client, self.user,
                                       [])
        assert len(headers) == 3
        self.basic_asserts(headers)
        assert 'userid' in headers
        assert headers['userid'] == '0186bdb5-5f68-436a-8453-6efe4a66cf1e'

    def test_expose_userid_sec(self):
        backend = self.basic_backend.copy()
        backend['expose'] = {'userid': True, 'userid-sec': True}
        self.session.get_apigk.return_value = backend
        headers = self.controller.info('testbackend', self.client, self.user,
                                       [])
        assert len(headers) == 4
        self.basic_asserts(headers)
        assert 'userid' in headers
        assert headers['userid'] == '0186bdb5-5f68-436a-8453-6efe4a66cf1e'
        assert 'userid-sec' in headers
        assert headers['userid-sec'] == 'feide:test@feide.no,mail:test.user@feide.no' or \
            headers['userid-sec'] == 'mail:test.user@feide.no,feide:test@feide.no'

    def test_expose_userid_sec_one(self):
        backend = self.basic_backend.copy()
        backend['expose'] = {'userid': True, 'userid-sec': ['feide']}
        self.session.get_apigk.return_value = backend
        headers = self.controller.info('testbackend', self.client, self.user,
                                       [])
        assert len(headers) == 4
        self.basic_asserts(headers)
        assert 'userid' in headers
        assert headers['userid'] == '0186bdb5-5f68-436a-8453-6efe4a66cf1e'
        assert 'userid-sec' in headers
        assert headers['userid-sec'] == 'feide:test@feide.no'


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
