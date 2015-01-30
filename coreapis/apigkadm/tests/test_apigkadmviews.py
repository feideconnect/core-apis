import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware, apigkadm
from coreapis.utils import ValidationError, parse_datetime, json_normalize
import py.test

post_body_minimal = {
    'id': 'testgk',
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'endpoints': ['https://foo.no'],
    'requireuser': False,
    'trust': {
        'type': 'basic',
        'username': 'username',
        'password': 'secrit',
    },
}

post_body_maximal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'id': 'max-gk',
    'created': '2015-01-12T14:05:16+01:00', 'descr': 'green',
    'status': ['lab'],
    'updated': '2015-01-12T14:05:16+01:00',
    'endpoints': ['https://foo.com', 'https://ugle.org:5000'],
    'requireuser': True,
    'httpscertpinned': '',
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

pre_update = {
    "httpscertpinned": None,
    "scopedef": None,
    "descr": None,
    "status": None,
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": "updateable",
    "expose": {
    },
    "owner": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "trust": {
        "token": "abcderf",
        "type": "bearer"
    },
    "endpoints": [
        "https://example.com"
    ],
    "name": "pre update",
    "requireuser": False
}


class TestValidation(unittest.TestCase):
    @mock.patch('coreapis.apigkadm.controller.cassandra_client.Client')
    def setUp(self, Client):
        self.controller = apigkadm.controller.APIGKAdmController([], '', 20)

    def test_validation(self):
        self.controller.validate(post_body_maximal)
        self.controller.validate(post_body_minimal)
        testdata = deepcopy(post_body_minimal)
        testdata['id'] = 'ab1'
        self.controller.validate(testdata)
        testdata['id'] = 'ab1-12abc123'
        self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = 'a'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = '1ab'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = 'abcdefghijklmeno'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = '.'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = '/'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = ':'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = 'ab1'
            testdata['created'] = 42
            self.controller.validate(testdata)


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
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = {'foo': 'bar'}
        res = self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=200, headers=headers)
        out = res.json
        assert 'foo' in out

    def test_missing_apigk(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.side_effect = KeyError()
        self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_apigks(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/apigkadm/apigks/', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_apigks_by_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/apigkadm/apigks/?scope=userlist', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_apigks_by_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/apigkadm/apigks/?owner={}'.format('00000000-0000-0000-0000-000000000001'),
                               status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_post_apigk_minimal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk = mock.MagicMock(side_effect=KeyError)
        res = self.testapp.post_json('/apigkadm/apigks/', post_body_minimal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_apigk_maximal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        res = self.testapp.post_json('/apigkadm/apigks/', post_body_maximal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_apigk_duplicate(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigks.return_value = [{'foo': 'bar'}]
        self.testapp.post_json('/apigkadm/apigks/', post_body_maximal, status=409, headers=headers)

    def test_post_apigk_missing_name(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = 'foo'
        self.testapp.post('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_other_user(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['owner'] = 'owner'
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        res = self.testapp.post_json('/apigkadm/apigks/', body, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_apigk_invalid_text(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_text_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_unknown_attr(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_invalid_endpoint(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['endpoints'] = ['https://ugle.com/bar']
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)
        body['endpoints'] = ['ugle.com']
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)
        body['endpoints'] = ['ftp://ugle.com']
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_delete_apigk(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = {'owner': uuid.UUID('00000000-0000-0000-0000-000000000001')}
        self.testapp.delete('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=204, headers=headers)

    def test_delete_apigk_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/apigkadm/apigks/', status=404, headers=headers)

    def test_update_no_change(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        res = self.testapp.patch_json('/apigkadm/apigks/updatable', {}, status=200, headers=headers)
        updated = res.json
        expected = json_normalize(pre_update)
        assert updated['updated'] > expected['updated']
        del updated['updated']
        del expected['updated']
        assert updated == expected

    def test_update_invalid_request(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        self.testapp.patch('/apigkadm/apigks/updatable', '{', status=400, headers=headers)
        self.testapp.patch_json('/apigkadm/apigks/updatable', {'endpoints': 'file:///etc/shadow'},
                                status=400, headers=headers)

    def test_update_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        to_update = deepcopy(pre_update)
        to_update['owner'] = uuid.uuid4()
        self.session().get_apigk.return_value = to_update
        self.testapp.patch_json('/apigkadm/apigks/updatable', {},
                                status=401, headers=headers)

    def test_apigk_exists(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        res = self.testapp.get('/apigkadm/apigks/updatable/exists', status=200, headers=headers)
        assert res.json is True

    def test_apigk_exists_other_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        other_owner = deepcopy(pre_update)
        other_owner['owner'] = uuid.uuid4()
        self.session().get_apigk.return_value = other_owner
        res = self.testapp.get('/apigkadm/apigks/updatable/exists', status=200, headers=headers)
        assert res.json is True

    def test_apigk_does_not_exist(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.side_effect = KeyError
        res = self.testapp.get('/apigkadm/apigks/updatable/exists', status=200, headers=headers)
        assert res.json is False

    def test_apigk_get_owner_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        apigks = [{ 'id': 'fooapi'}, { 'id': 'barapi'}]
        for count in [0, 1, 2]:
            self.session().get_apigks.return_value = apigks[:count]
            with mock.patch('coreapis.clientadm.controller.ClientAdmController.get_gkscope_clients',
                            return_value=[]):
                self.testapp.get('/apigkadm/apigks/owners/{}/clients/'.format(uuid.uuid4()),
                                 status=200, headers=headers)
