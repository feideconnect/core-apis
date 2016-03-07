# pylint: disable=invalid-name
import unittest
import uuid
from copy import deepcopy
import mock
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import (json_normalize, now)
from coreapis.apigkadm.tests.data import (
    post_body_minimal, post_body_maximal, pre_update, mock_get_apigks, num_mock_apigks)

PLATFORMADMIN = 'admin@example.com'


def make_user(source, userid):
    return {
        'userid': uuid.uuid4(),
        'userid_sec': ['{}:{}'.format(source, userid)]
    }


def make_feide_user(feideid):
    return make_user('feide', feideid)


class APIGKAdmTests(unittest.TestCase):
    @mock.patch('coreapis.apigkadm.controller.get_platform_admins')
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client, gpa):
        gpa.return_value = [PLATFORMADMIN]
        app = main(
            {
                'statsd_server': 'localhost',
                'statsd_port': '8125',
                'statsd_prefix': 'dataporten.tests',
                'oauth_realm': 'test realm',
                'cassandra_contact_points': '',
                'cassandra_keyspace': 'notused',
            },
            enabled_components='apigkadm',
            apigkadm_maxrows=100,
            clientadm_scopedefs_file='testdata/scopedefs_testing.json')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_apigk(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = pre_update
        path = '/apigkadm/apigks/{}'.format(uuid.uuid4())
        res = self.testapp.get(path, status=200, headers=headers)
        out = res.json
        assert out['id'] == 'updateable'

    def _test_get_apigk_not_owner(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        other_owner = deepcopy(pre_update)
        other_owner['owner'] = uuid.uuid4()
        self.session().get_apigk.return_value = other_owner
        path = '/apigkadm/apigks/{}'.format(uuid.uuid4())
        self.testapp.get(path, status=httpstat, headers=headers)

    def test_get_apigk_not_owner(self):
        self._test_get_apigk_not_owner(403)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_get_apigk_platform_admin(self, _):
        self._test_get_apigk_not_owner(200)

    def test_missing_apigk(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.side_effect = KeyError()
        self.testapp.get('/apigkadm/apigks/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_apigks(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.side_effect = mock_get_apigks
        res = self.testapp.get('/apigkadm/apigks/', status=200, headers=headers)
        out = res.json
        assert 'trust' in out[0]
        assert len(out) < num_mock_apigks

    def _test_list_apigks_show_all(self, val, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.side_effect = mock_get_apigks
        path = '/apigkadm/apigks/?showAll={}'.format(val)
        return self.testapp.get(path, status=httpstat, headers=headers)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_list_apigks_show_all_platform_admin(self, _):
        res = self._test_list_apigks_show_all('true', 200)
        out = res.json
        assert 'trust' in out[0]
        assert len(out) == num_mock_apigks

    def test_list_apigks_show_all_normal_user(self):
        self._test_list_apigks_show_all('true', 403)

    def test_list_apigks_show_all_param_not_true(self):
        res = self._test_list_apigks_show_all('1', 200)
        out = res.json
        assert 'trust' in out[0]
        assert len(out) < num_mock_apigks

    def test_list_apigks_by_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [pre_update]
        path = '/apigkadm/apigks/?owner={}'.format('00000000-0000-0000-0000-000000000001')
        res = self.testapp.get(path, status=200, headers=headers)
        out = res.json
        assert out[0]['id'] == 'updateable'

    def _test_list_apigks_by_org(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigks.return_value = [pre_update]
        self.session().is_org_admin.return_value = orgadmin
        path = '/apigkadm/apigks/?organization={}'.format('fc:org:example.com')
        return self.testapp.get(path, status=httpstat, headers=headers)

    def test_list_apigks_by_org(self):
        res = self._test_list_apigks_by_org(True, 200)
        out = res.json
        assert out[0]['id'] == 'updateable'

    def test_list_apigks_by_org_not_admin(self):
        self._test_list_apigks_by_org(False, 403)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_list_apigks_by_org_admin_for_platform_not_for_org(self, _):
        self._test_list_apigks_by_org(False, 200)

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
        res = self.testapp.post_json('/apigkadm/apigks/', post_body_minimal,
                                     status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def _test_post_apigk_minimal(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk = mock.MagicMock(side_effect=KeyError)
        path = '/apigkadm/apigks/'
        return self.testapp.post_json(path, post_body_minimal, status=httpstat, headers=headers)

    def test_post_apigk_maximal(self):
        res = self._test_post_apigk_minimal(201)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'
        assert out['organization'] is None

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_user('linkbook', '12345'))
    def test_post_apigk_not_feide(self, _):
        self._test_post_apigk_minimal(403)

    def test_post_apigk_path(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        data = deepcopy(post_body_maximal)
        data['endpoints'] = ['https://ugle.com/bar']
        self.testapp.post_json('/apigkadm/apigks/', data, status=201, headers=headers)

    def _test_post_apigk(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_apigk = mock.MagicMock()
        self.session().get_apigk.side_effect = KeyError()
        self.session().is_org_admin.return_value = orgadmin
        data = deepcopy(post_body_maximal)
        data['organization'] = 'fc:org:example.com'
        return self.testapp.post_json('/apigkadm/apigks/', data, status=httpstat, headers=headers)

    def test_post_apigk_org(self):
        res = self._test_post_apigk(True, 201)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_apigk_org_not_admin(self):
        self._test_post_apigk(False, 403)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_post_apigk_admin_for_platform_not_for_org(self, _):
        self._test_post_apigk(False, 201)

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

    def test_post_apigk_not_json_object(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = '"foo"'
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

    def _test_delete_apigk(self, owner, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        gkid = 'testapi'
        self.session().get_apigk.return_value = {'owner': uuid.UUID(owner), 'id': gkid}
        self.testapp.delete('/apigkadm/apigks/{}'.format(id), status=httpstat, headers=headers)

    def test_delete_apigk(self):
        self._test_delete_apigk('00000000-0000-0000-0000-000000000001', 204)

    def test_delete_apigk_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/apigkadm/apigks/', status=404, headers=headers)

    def test_delete_apigk_not_owner(self):
        self._test_delete_apigk('00000000-0000-0000-0000-000000000002', 403)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_delete_apigk_platform_admin(self, _):
        self._test_delete_apigk('00000000-0000-0000-0000-000000000002', 204)

    def _test_delete_unknown_apigk(self, orgadmin):
        headers = {'Authorization': 'Bearer user_token'}
        gkid = 'testapi'
        self.session().get_apigk.side_effect = KeyError
        self.session().is_org_admin.return_value = orgadmin
        self.testapp.delete('/apigkadm/apigks/{}'.format(gkid), status=404, headers=headers)

    def test_delete_unknown_apigk_orgadmin(self):
        self._test_delete_unknown_apigk(True)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_delete_unknown_apigk_platform_admin(self, _):
        self._test_delete_unknown_apigk(True)

    def test_update_no_change(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        val = self.testapp.get('/apigkadm/apigks/updatable', status=200, headers=headers).json
        res = self.testapp.patch_json('/apigkadm/apigks/updatable', val,
                                      status=200, headers=headers)
        updated = res.json
        expected = json_normalize(pre_update)
        assert updated['updated'] > expected['updated']
        del updated['updated']
        del expected['updated']
        assert updated == expected

    def test_update_clientonly_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        val = self.testapp.get('/apigkadm/apigks/updatable', status=200, headers=headers).json
        val['scopes_requested'].append('openid')
        res = self.testapp.patch_json('/apigkadm/apigks/updatable', val,
                                      status=200, headers=headers)
        updated = res.json
        expected = json_normalize(pre_update)
        assert updated['updated'] > expected['updated']
        del updated['updated']
        del expected['updated']
        assert updated == expected

    def test_update_api_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_apigk.return_value = deepcopy(pre_update)
        val = self.testapp.get('/apigkadm/apigks/updatable', status=200, headers=headers).json
        val['scopes_requested'].append('gk_someapi')
        res = self.testapp.patch_json('/apigkadm/apigks/updatable',
                                      val, status=200, headers=headers)
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

    def _test_update_not_owner(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        to_update = deepcopy(pre_update)
        to_update['owner'] = uuid.uuid4()
        self.session().get_apigk.return_value = to_update
        self.testapp.patch_json('/apigkadm/apigks/updatable', {},
                                status=httpstat, headers=headers)

    def test_update_not_owner(self):
        self._test_update_not_owner(403)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_update_as_platform_admin(self, _):
        self._test_update_not_owner(200)

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

    def _test_apigk_get_org_clients(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        org = 'fc:org:example.com'
        apigks = [{'id': 'fooapi', 'organization': org},
                  {'id': 'barapi', 'organization': org}]
        self.session().is_org_admin.return_value = orgadmin
        for count in [0, 1, 2]:
            self.session().get_apigks.return_value = apigks[:count]
            with mock.patch('coreapis.clientadm.controller.ClientAdmController.get_gkscope_clients',
                            return_value=[]):
                self.testapp.get('/apigkadm/apigks/orgs/{}/clients/'.format(org),
                                 status=httpstat, headers=headers)

    def test_apigk_get_org_clients(self):
        self._test_apigk_get_org_clients(True, 200)

    def test_apigk_get_org_clients_not_admin(self):
        self._test_apigk_get_org_clients(False, 403)

    @mock.patch('coreapis.apigkadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_apigk_get_org_clients_admin_for_platform_not_for_org(self, _):
        self._test_apigk_get_org_clients(False, 200)

    def test_get_apigk_logo(self):
        self.session().get_apigk_logo.return_value = (b'mylittlelogo', now())
        for ver in ['', '/v1']:
            path = '/apigkadm{}/apigks/{}/logo'.format(ver, uuid.uuid4())
            res = self.testapp.get(path, status=200)
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
