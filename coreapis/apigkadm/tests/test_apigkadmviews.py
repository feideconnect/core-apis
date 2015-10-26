import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import (json_normalize, now)
from coreapis.apigkadm.tests.data import post_body_minimal, post_body_maximal, pre_update


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
        self.session().get_apigk.return_value = pre_update
        res = self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=200, headers=headers)
        out = res.json
        assert out['id'] == 'updateable'

    def test_missing_apigk(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.side_effect = KeyError()
        self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_apigks(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [pre_update]
        res = self.testapp.get('/apigkadm/apigks/', status=200, headers=headers)
        out = res.json
        assert out[0]['id'] == 'updateable'

    def test_list_apigks_by_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [pre_update]
        res = self.testapp.get('/apigkadm/apigks/?owner={}'.format('00000000-0000-0000-0000-000000000001'),
                               status=200, headers=headers)
        out = res.json
        assert out[0]['id'] == 'updateable'

    def test_list_apigks_by_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [pre_update]
        self.session().is_org_admin.return_value = True
        res = self.testapp.get('/apigkadm/apigks/?organization={}'.format('fc:org:example.com'),
                               status=200, headers=headers)
        out = res.json
        assert out[0]['id'] == 'updateable'

    def test_list_apigks_by_org_not_admin(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [pre_update]
        self.session().is_org_admin.return_value = False
        self.testapp.get('/apigkadm/apigks/?organization={}'.format('fc:org:example.com'),
                         status=403, headers=headers)

    def test_list_public_apigks(self):
        pubapi = deepcopy(pre_update)
        pubapi['status'] = {'public'}
        self.session().get_apigks.return_value = [pubapi]
        retrieved_user = {
            'userid_sec': ['p:foo'],
            'selectedsource': 'us',
            'name': {'us': 'foo'},
            'userid': uuid.UUID('00000000-0000-0000-0000-000000000001'),
        }
        self.session().get_user_by_id.return_value = retrieved_user
        for ver in ['', '/v1']:
            res = self.testapp.get('/apigkadm{}/public'.format(ver), status=200)
            assert 'owner' in res.json[0]
            assert 'systemdescr' in res.json[0]
            assert 'privacypolicyurl' in res.json[0]
            assert 'docurl' in res.json[0]
            assert 'endpoints' not in res.json[0]

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
        assert out['organization'] is None

    def test_post_apigk_path(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        data = deepcopy(post_body_maximal)
        data['endpoints'] = ['https://ugle.com/bar']
        self.testapp.post_json('/apigkadm/apigks/', data, status=201, headers=headers)

    def test_post_apigk_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        self.session().is_org_admin.return_value = True
        data = deepcopy(post_body_maximal)
        data['organization'] = 'fc:org:example.com'
        res = self.testapp.post_json('/apigkadm/apigks/', data, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_apigk_org_not_admin(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        self.session().is_org_admin.return_value = False
        data = deepcopy(post_body_maximal)
        data['organization'] = 'fc:org:example.com'
        self.testapp.post_json('/apigkadm/apigks/', data, status=403, headers=headers)

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
        body['endpoints'] = ['ugle.com']
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)
        body['endpoints'] = ['ftp://ugle.com']
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_privacypolicyurl(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['privacypolicyurl'] = 'htpp://www.vg.no'
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_post_apigk_invalid_docurl(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['docurl'] = ''
        self.session().insert_apigk = mock.MagicMock()
        self.testapp.post_json('/apigkadm/apigks/', body, status=400, headers=headers)

    def test_delete_apigk(self):
        headers = {'Authorization': 'Bearer user_token'}
        id = 'testapi'
        self.session().get_apigk.return_value = {'owner': uuid.UUID('00000000-0000-0000-0000-000000000001'), 'id': id}
        self.testapp.delete('/apigkadm/apigks/{}'.format(id), status=204, headers=headers)

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
                                status=403, headers=headers)

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
        apigks = [{'id': 'fooapi', 'organization': None},
                  {'id': 'barapi', 'organization': 'someorg'}]
        for count in [0, 1, 2]:
            self.session().get_apigks.return_value = apigks[:count]
            with mock.patch('coreapis.clientadm.controller.ClientAdmController.get_gkscope_clients',
                            return_value=[]):
                self.testapp.get('/apigkadm/apigks/owners/{}/clients/'.format(
                    uuid.UUID('00000000-0000-0000-0000-000000000001')),
                                 status=200, headers=headers)

    def test_apigk_get_owner_clients_me(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/apigkadm/apigks/owners/me/clients/',
                         status=200, headers=headers)

    def test_apigk_get_owner_clients_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/apigkadm/apigks/owners/{}/clients/'.format(uuid.uuid4()),
                         status=403, headers=headers)

    def test_apigk_get_org_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        org = 'fc:org:example.com'
        apigks = [{'id': 'fooapi', 'organization': org},
                  {'id': 'barapi', 'organization': org}]
        self.session().is_org_admin.return_value = True
        for count in [0, 1, 2]:
            self.session().get_apigks.return_value = apigks[:count]
            with mock.patch('coreapis.clientadm.controller.ClientAdmController.get_gkscope_clients',
                            return_value=[]):
                self.testapp.get('/apigkadm/apigks/orgs/{}/clients/'.format(org),
                                 status=200, headers=headers)

    def test_apigk_get_org_clients_not_admin(self):
        headers = {'Authorization': 'Bearer user_token'}
        org = 'fc:org:example.com'
        apigks = [{'id': 'fooapi', 'organization': org},
                  {'id': 'barapi', 'organization': org}]
        self.session().is_org_admin.return_value = False
        for count in [0, 1, 2]:
            self.session().get_apigks.return_value = apigks[:count]
            with mock.patch('coreapis.clientadm.controller.ClientAdmController.get_gkscope_clients',
                            return_value=[]):
                self.testapp.get('/apigkadm/apigks/orgs/{}/clients/'.format(org),
                                 status=403, headers=headers)

    def test_get_apigk_logo(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk_logo.return_value = (b'mylittlelogo', now())
        for ver in ['', '/v1']:
            path = '/apigkadm{}/apigks/{}/logo'.format(ver, uuid.uuid4())
            res = self.testapp.get(path, status=200, headers=headers)
            assert res.content_type == 'image/png'
            out = res.body
            assert b'mylittlelogo' in out

    def test_post_apigk_logo_body(self):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        self.session().save_logo = mock.MagicMock()
        for ver in ['', '/v1']:
            with open('data/default-client.png', 'rb') as fh:
                path = '/apigkadm{}/apigks/{}/logo'.format(ver, uuid.uuid4())
                logo = fh.read()
                res = self.testapp.post(path, logo, status=200, headers=headers)
                out = res.json
                assert out == 'OK'
