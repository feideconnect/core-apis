import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware, apigkadm

post_body_minimal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'endpoints': ['https://foo.no/bar'],
    'requireuser': False,
}

post_body_maximal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'id': 'f3f043db-9fd6-4c5a-b0bc-61992bea9eca',
    'created': '2015-01-12 14:05:16+0100', 'descr': 'green',
    'status': ['lab'],
    'updated': '2015-01-12 14:05:16+0100',
    'endpoints': ['https://foo.com/bar', 'https://ugle.org/foo'],
    'requireuser': True,
    'httpcertspinned': '',
    'expose': {
        'userid': True,
        'clientid': True,
        'scopes': True,
        'groups': False,
        'userid-sec': ['feide'],
    },
    'scopedef': {},
    'trust': {
        'type': 'basic',
        'username': 'username',
        'password': 'secrit',
    },
}


class TestValidation(unittest.TestCase):
    @mock.patch('coreapis.apigkadm.controller.cassandra_client.Client')
    def setUp(self, Client):
        self.controller = apigkadm.controller.APIGKAdmController([], '', 20)

    def test_validation(self):
        self.controller.validate_apigk(post_body_maximal)
        self.controller.validate_apigk(post_body_minimal)


class APIGKAdmTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='apigkadm', apigkadm_maxrows=100)
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_apigk(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_apigk.return_value = {'foo': 'bar'}
        res = self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=200, headers=headers)
        out = res.json
        assert 'foo' in out

    def test_missing_apigk(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_apigk.side_effect = KeyError()
        self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_apigks(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/apigkadm/apigks/', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_apigks_by_scope(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/apigkadm/apigks/?scope=userlist', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_apigks_by_owner(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/apigkadm/apigks/?owner={}'.format(uuid.uuid4()), status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_bad_apigk_filter(self):
        headers = {'Authorization': 'Bearer client_token'}
        res = self.testapp.get('/apigkadm/apigks/?owner=', status=400, headers=headers)
        out = res.json
        assert out['message'] == 'missing filter value'

    def test_post_apigk_minimal(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().insert_apigk = mock.MagicMock()
        res = self.testapp.post_json('/apigkadm/apigks/', post_body_minimal, status=201, headers=headers)
        out = res.json
        assert '4f4e' in out['owner']

    def test_post_apigk_maximal(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        res = self.testapp.post_json('/apigkadm/apigks/', post_body_maximal, status=201, headers=headers)
        out = res.json
        assert '4f4e' in out['owner']

    def test_post_apigk_duplicate(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        self.testapp.post_json('/apigkadm/apigks/', post_body_maximal, status=409, headers=headers)

    def test_post_apigk_missing_name(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_json(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = 'foo'
        self.testapp.post('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_uuid(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['owner'] = 'owner'
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_text(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_ts(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['created'] = 42
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_text_list(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_list(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_unknown_attr(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_delete_apigk(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.delete('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=204, headers=headers)

    def test_delete_apigk_no_id(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.delete('/apigkadm/apigks/', status=404, headers=headers)

    def test_delete_apigk_malformed_id(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.delete('/apigkadm/apigks/{}'.format('foo'), status=400, headers=headers)
