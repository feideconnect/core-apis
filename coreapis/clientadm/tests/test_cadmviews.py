# pylint: disable=invalid-name
import unittest
import json
import uuid
from datetime import timedelta
from copy import deepcopy
import mock
from cassandra.util import SortedSet
from aniso8601 import parse_datetime
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import translatable
from coreapis.clientadm.tests.helper import (
    userid_own, userid_other, clientid, date_created, testscope, otherscope, testuris, baduris,
    post_body_minimal, post_body_other_owner, post_body_maximal, retrieved_client,
    retrieved_user, retrieved_gk_clients, testgk, testgk_foo, othergk, owngk, nullscopedefgk,
    httptime, mock_get_apigk, mock_get_clients, retrieved_apigks, userstatus, reservedstatus,
    testrealm, is_full_client, is_public_client)


PLATFORMADMIN = 'admin@example.com'
FEIDETESTER = 'asbjorn_elevg@spusers.feide.no'


def make_user(source, userid):
    return {
        'userid_sec': ['{}:{}'.format(source, userid)]
    }


def make_feide_user(feideid):
    return make_user('feide', feideid)


class ClientAdmTests(unittest.TestCase):
    @mock.patch('coreapis.clientadm.controller.get_platform_admins')
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
            enabled_components='clientadm',
            clientadm_scopedefs_file='testdata/scopedefs_testing.json',
            clientadm_maxrows=100)
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.session.get_apigk.side_effect = mock_get_apigk
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        res = self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=200,
                               headers=headers)
        out = res.json
        assert is_full_client(out)

    def test_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError()
        self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=404,
                         headers=headers)

    def _test_get_client_not_owner(self, headers, httpstat):
        client = deepcopy(retrieved_client)
        client['owner'] = userid_other
        owner = deepcopy(retrieved_user)
        owner['userid'] = uuid.UUID(userid_other)
        self.session.get_client_by_id.return_value = client
        self.session.get_user_by_id.return_value = owner
        return self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)),
                                headers=headers, status=httpstat)

    def test_get_client_unauthenticated(self):
        res = self._test_get_client_not_owner(None, 200)
        assert is_public_client(res.json)

    def test_get_client_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self._test_get_client_not_owner(headers, 200)
        assert is_public_client(res.json)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_get_client_platform_admin(self, _):
        headers = {'Authorization': 'Bearer user_token'}
        res = self._test_get_client_not_owner(headers, 200)
        assert is_full_client(res.json)

    def test_get_client_missing_user(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session.get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        path = '/clientadm/clients/{}'.format(uuid.UUID(clientid))
        self.testapp.get(path, status=404, headers=headers)

    def test_list_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.side_effect = mock_get_clients
        res = self.testapp.get('/clientadm/clients/', status=200, headers=headers)
        assert is_full_client(res.json[0])
        assert len(res.json) < len(retrieved_gk_clients)

    def _test_list_clients_show_all(self, val, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.side_effect = mock_get_clients
        path = '/clientadm/clients/?showAll={}'.format(val)
        return self.testapp.get(path, status=httpstat, headers=headers)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_list_clients_show_all_platform_admin(self, _):
        res = self._test_list_clients_show_all('true', 200)
        assert is_full_client(res.json[0])
        assert len(res.json) == len(retrieved_gk_clients)

    def test_list_clients_show_all_normal_user(self):
        self._test_list_clients_show_all('true', 403)

    def test_list_clients_show_all_param_not_true(self):
        res = self._test_list_clients_show_all('1', 200)
        assert is_full_client(res.json[0])
        assert len(res.json) < len(retrieved_gk_clients)

    def test_list_clients_by_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = iter([deepcopy(retrieved_client)])
        res = self.testapp.get('/clientadm/clients/?scope=userlist', status=200, headers=headers)
        assert is_full_client(res.json[0])

    def _test_list_clients_by_org_as_admin(self, orgadmin, expected):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = iter([deepcopy(retrieved_client)])
        self.session.is_org_admin.return_value = orgadmin
        path = '/clientadm/clients/?organization={}'.format('fc:org:example.com')
        return self.testapp.get(path, status=expected, headers=headers)

    def test_list_clients_by_org_as_admin(self):
        res = self._test_list_clients_by_org_as_admin(True, 200)
        assert is_full_client(res.json[0])

    def test_list_clients_by_org_not_admin(self):
        self._test_list_clients_by_org_as_admin(False, 403)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_list_clients_by_org_platform_admin(self, _):
        res = self._test_list_clients_by_org_as_admin(False, 200)
        assert is_full_client(res.json[0])

    def test_list_public_clients(self):
        org_client = deepcopy(retrieved_client)
        org_client['organization'] = 'fc:org:example.com'
        self.session.get_user_by_id.return_value = retrieved_user
        self.session.get_org.return_value = {'id': 'fc:org:example.com',
                                             'name': translatable({'en': 'testorg'})}
        for ver in ['', '/v1']:
            self.session.get_clients.return_value = iter(deepcopy([retrieved_client, org_client]))
            res = self.testapp.get('/clientadm{}/public/'.format(ver), status=200)
            out = res.json
            assert out[0]['name'] == 'per'
            assert all(is_public_client(c) for c in out)
            assert out[1]['organization']['id'] == 'fc:org:example.com'
            assert out[1]['organization']['name'] == 'testorg'

    def test_list_public_clients_bogus_user(self):
        self.session.get_clients.return_value = iter(deepcopy([retrieved_client]))
        self.session.get_user_by_id.side_effect = KeyError
        res = self.testapp.get('/clientadm/public/', status=200)
        assert res.json[0] is None

    def test_list_public_clients_orgauth(self):
        org_client = deepcopy(retrieved_gk_clients[3])
        org_client['organization'] = 'fc:org:example.com'
        self.session.get_clients.return_value = iter([org_client])
        self.session.get_user_by_id.return_value = retrieved_user
        self.session.get_org.return_value = {'id': 'fc:org:example.com',
                                             'name': translatable({'en': 'testorg'})}
        path = '/clientadm/public/?orgauthorization={}'.format(testrealm)
        res = self.testapp.get(path, status=200)
        out = res.json
        assert out[0]['name'] == 'per'
        assert 'scopes' not in out[0]
        assert out[0]['organization']['id'] == 'fc:org:example.com'
        assert out[0]['organization']['name'] == 'testorg'

    def _test_post_client_minimal(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/'
        return self.testapp.post_json(path, post_body_minimal, status=httpstat, headers=headers)

    def test_post_client_minimal(self):
        res = self._test_post_client_minimal(201)
        out = res.json
        assert out['name'] == 'per'
        assert out['organization'] is None

    def test_post_client_maximal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.insert_client = mock.MagicMock()
        self.session.get_client_by_id.side_effect = KeyError()
        path = '/clientadm/clients/'
        res = self.testapp.post_json(path, post_body_maximal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == userid_own
        assert out['organization'] is None
        assert out['orgauthorization'] is None

    @mock.patch('coreapis.clientadm.views.get_user',
                return_value=make_user('linkbook', '12345'))
    def test_post_client_not_feide(self, _):
        self._test_post_client_minimal(403)

    @mock.patch('coreapis.clientadm.views.get_user',
                return_value=make_feide_user(FEIDETESTER))
    def test_post_client_feide_tester(self, _):
        self._test_post_client_minimal(403)

    @mock.patch('coreapis.clientadm.views.get_user',
                return_value=make_user('nin', '10108012345'))
    def test_post_client_idporten(self, _):
        self._test_post_client_minimal(403)

    def _test_post_client_other_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/'
        return self.testapp.post_json(path, post_body_other_owner, status=201, headers=headers)

    def test_post_client_other_owner(self):
        res = self._test_post_client_other_owner()
        assert res.json['owner'] == userid_own

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_post_client_other_owner_platform_admin(self, _):
        res = self._test_post_client_other_owner()
        assert res.json['owner'] == userid_other

    def test_post_client_duplicate(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.insert_client = mock.MagicMock()
        self.session.get_client_by_id.return_value = {'foo': 'bar'}
        path = '/clientadm/clients/'
        self.testapp.post_json(path, post_body_maximal, status=409, headers=headers)

    def _test_post_client_scope_given(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes'] = [testscope]
        self.session.insert_client = mock.MagicMock()
        return self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)

    def test_post_client_scope_given(self):
        res = self._test_post_client_scope_given()
        assert testscope not in res.json['scopes']

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_post_client_scope_given_platform_admin(self, _):
        res = self._test_post_client_scope_given()
        assert testscope in res.json['scopes']

    def test_post_client_autoscope_requested(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [otherscope]
        self.session.insert_client = mock.MagicMock()
        res = self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)
        out = res.json
        assert out['scopes'] == [otherscope]

    def _test_post_client_organization(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['organization'] = 'fc:org:example.com'
        self.session.insert_client = mock.MagicMock()
        self.session.is_org_admin.return_value = orgadmin
        return self.testapp.post_json('/clientadm/clients/', body, status=httpstat, headers=headers)

    def test_post_client_organization_as_orgadmin(self):
        res = self._test_post_client_organization(True, 201)
        assert res.json['organization'] == 'fc:org:example.com'

    def test_post_client_organization_not_orgadmin(self):
        self._test_post_client_organization(False, 403)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_post_client_organization_platform_admin(self, _):
        res = self._test_post_client_organization(False, 201)
        assert res.json['organization'] == 'fc:org:example.com'

    def test_post_client_invalid_scope_requested(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = ['nosuchthing']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_gkscope_does_not_exist(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = ['gk_nosuchthing']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_gksubscope_given(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [testgk, testgk + '_foo']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)

    def test_post_client_gksubscope_does_not_exist(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [testgk, testgk + '_bar']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_gksubscope_no_subscopedefs(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [othergk, othergk + '_bar']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_missing_name(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = 'foo'
        self.testapp.post('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_not_json_object(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = '"foo"'
        self.testapp.post('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_uuid(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['id'] = 'foo'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_unknown_attr(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def _test_post_client_statusflag(self, flag):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['status'] = [flag]
        self.session.insert_client = mock.MagicMock()
        return self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)

    def test_post_client_userstatus(self):
        flag = userstatus
        res = self._test_post_client_statusflag(flag)
        assert flag in res.json['status']

    def test_post_client_status_reservedstatus(self):
        flag = reservedstatus
        res = self._test_post_client_statusflag(flag)
        assert flag not in res.json['status']

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_post_client_status_reservedstatus_platform_admin(self, _):
        flag = reservedstatus
        res = self._test_post_client_statusflag(flag)
        assert flag in res.json['status']

    def test_post_client_status_null(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['status'] = None
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)

    def test_post_client_bad_uri_scheme(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [baduris[0]]
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_bad_privacypolicyurl(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['privacypolicyurl'] = 'foo'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_bad_homepageurl(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['homepageurl'] = ''
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_bad_loginurl(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['loginurl'] = 'http://'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_bad_supporturl(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['supporturl'] = 'www.vg.no'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_bad_authoptions(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['authoptions'] = '{"this":'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_delete_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        path = '/clientadm/clients/{}'.format(uuid.UUID(clientid))
        self.testapp.delete(path, status=204, headers=headers)

    def test_delete_client_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/clientadm/clients/', status=404, headers=headers)

    def test_delete_client_malformed_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/clientadm/clients/{}'.format('foo')
        self.testapp.delete(path, status=404, headers=headers)

    def _test_delete_client_not_owner(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        client['organization'] = 'fc:org:example.com'
        self.session.get_client_by_id.return_value = client
        self.session.is_org_admin.return_value = orgadmin
        path = '/clientadm/clients/{}'.format(uuid.UUID(clientid))
        self.testapp.delete(path, status=httpstat, headers=headers)

    def test_delete_client_not_owner(self):
        self._test_delete_client_not_owner(False, 403)

    def test_delete_client_not_owner_org_admin_(self):
        self._test_delete_client_not_owner(True, 204)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_delete_client_not_owner_platform_admin_(self, _):
        self._test_delete_client_not_owner(False, 204)

    def _test_delete_missing_client(self, orgadmin):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        self.session.is_org_admin.return_value = orgadmin
        path = '/clientadm/clients/{}'.format(uuid.UUID(clientid))
        self.testapp.delete(path, status=404, headers=headers)

    def test_delete_missing_client(self):
        self._test_delete_missing_client(False)

    def test_delete_missing_client_org_admin_(self):
        self._test_delete_missing_client(True)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_delete_missing_client_platform_admin_(self, _):
        self._test_delete_missing_client(False)

    def test_update_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        ret = deepcopy(retrieved_client)
        ret['orgauthorization'] = {testrealm: json.dumps([testgk])}
        self.session.get_client_by_id.return_value = ret
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'descr': 'blue'}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['descr'] == 'blue'

    def test_update_client_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/clientadm/clients/'
        attrs = {'descr': 'blue'}
        self.testapp.patch_json(path, attrs, status=404, headers=headers)

    def test_update_client_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = 'bar'
        self.testapp.patch(path, attrs, status=400, headers=headers)

    def test_update_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError()
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'descr': 'blue'}
        self.testapp.patch_json(path, attrs, status=404, headers=headers)

    def _test_update_client_not_owner(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        client['organization'] = 'fc:org:example.com'
        self.session.get_client_by_id.return_value = client
        self.session.is_org_admin.return_value = orgadmin
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'descr': 'blue'}
        return self.testapp.patch_json(path, attrs, status=httpstat, headers=headers)

    def test_update_client_not_owner(self):
        self._test_update_client_not_owner(False, 403)

    def test_update_client_not_owner_org_admin(self):
        res = self._test_update_client_not_owner(True, 200)
        assert res.json['descr'] == 'blue'

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_update_client_not_owner_platform_admin(self, _):
        res = self._test_update_client_not_owner(False, 200)
        assert res.json['descr'] == 'blue'

    def test_update_client_change_timestamp(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'created': '2000-01-01T00:00:00+01:00'}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['created'] == date_created

    def test_update_client_change_owner_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'owner': userid_other, 'organization': 'fc:org:example.com'}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['owner'] == userid_own
        assert out['organization'] is None

    def test_update_client_change_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = [testscope]
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': [otherscope]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes'] == [testscope]

    def _test_update_client_change_scopes_not_auto(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = [otherscope]
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': [testscope]}
        return self.testapp.patch_json(path, attrs, status=200, headers=headers)

    def test_update_client_change_scopes_not_auto(self):
        res = self._test_update_client_change_scopes_not_auto()
        out = res.json
        assert testscope not in out['scopes']

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_update_client_change_scopes_platform_admin(self, _):
        res = self._test_update_client_change_scopes_not_auto()
        out = res.json
        assert testscope in out['scopes']

    def test_update_client_owner_of_gk_and_client_changes_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [owngk]
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': [owngk]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes'] == [owngk]

    def test_update_client_gkscope_lacking_scopedef(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes_requested': [nullscopedefgk]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes_requested'] == [nullscopedefgk]

    def test_update_client_stranger_changes_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [othergk]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': [othergk]}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_stranger_removes_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = [testscope]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': []}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_stranger_removes_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = [othergk]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': []}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_stranger_removes_bad_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = ['gk_nosuchthing']
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes': []}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_remove_requested_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = SortedSet([otherscope])
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'scopes_requested': [testscope]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes'] == []

    def test_update_client_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'redirect_uri': testuris[0]}
        self.testapp.patch_json(path, attrs, status=400, headers=headers)

    def test_update_client_gkowner_adds_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [owngk]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_add': [owngk]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out == "OK"

    def test_update_client_gkowner_removes_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = SortedSet([owngk])
        client['scopes_requested'] = SortedSet([owngk])
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_remove': [owngk]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out == "OK"

    def test_update_client_gkowner_adds_unwanted_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = []
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_add': [owngk]}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_gkowner_removes_unwanted_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = SortedSet([owngk])
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_remove': [owngk]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out == "OK"

    def test_update_client_gkowner_removes_requested_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = SortedSet([owngk])
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_remove': [owngk]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out == "OK"

    def test_update_client_gkowner_adds_bad_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = ['gk_nosuchthing']
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_add': ['gk_nosuchthing']}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_gkowner_adds_normal_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [testscope]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_add': [testscope]}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_stranger_adds_gkscope(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [testgk]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}/gkscopes'.format(clientid)
        attrs = {'scopes_add': [testgk]}
        self.testapp.patch_json(path, attrs, status=403, headers=headers)

    def test_update_client_change_userstatus(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        flag = userstatus
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'status': [flag]}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert flag in out['status']

    def _test_update_client_change_statusflag(self, flag):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'status': [flag]}
        return self.testapp.patch_json(path, attrs, status=200, headers=headers)

    def test_update_client_change_reservedstatus(self):
        flag = reservedstatus
        res = self._test_update_client_change_statusflag(flag)
        out = res.json
        assert flag not in out['status']

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_update_client_change_reservedstatus_platform_admin(self, _):
        flag = reservedstatus
        res = self._test_update_client_change_statusflag(flag)
        out = res.json
        assert flag in out['status']

    def test_update_client_change_authoptions(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['authoptions'] = '{}'
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'authoptions': {'foo': 'bar'}}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['authoptions'] == {'foo': 'bar'}

    def test_update_client_change_authoptions_from_none(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'authoptions': {'foo': 'bar'}}
        res = self.testapp.patch_json(path, attrs, status=200, headers=headers)
        out = res.json
        assert out['authoptions'] == {'foo': 'bar'}

    def _test_update_idporten(self, provider_name, orgid, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client.update(organization=orgid)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        path = '/clientadm/clients/{}'.format(clientid)
        attrs = {'authproviders': [provider_name]}
        return self.testapp.patch_json(path, attrs, status=httpstat, headers=headers)

    def test_update_client_authproviders_idporten_no_org(self):
        self._test_update_idporten('idporten', None, 400)

    def test_update_client_authproviders_idporten_no_such_org(self):
        self.session.get_org.side_effect = KeyError
        self._test_update_idporten('idporten', 'foo', 400)

    def test_update_client_authproviders_idporten_not_in_services(self):
        self.session.get_org.return_value = dict(services=[])
        self._test_update_idporten('idporten', 'foo', 400)

    def test_update_client_authproviders_idporten_in_services(self):
        self.session.get_org.return_value = dict(services=['idporten'])
        self._test_update_idporten('idporten', 'foo', 200)

    def test_update_client_authproviders_unknown_provider(self):
        self.session.get_org.return_value = dict(services=['idporten'])
        self._test_update_idporten('iqporten', 'foo', 200)

    def test_get_client_logo(self):
        updated = parse_datetime(date_created)
        date_older = updated - timedelta(minutes=1)
        headers = {'Authorization': 'Bearer user_token', 'If-Modified-Since': httptime(date_older)}
        self.session.get_client_logo.return_value = b'mylittlelogo', updated
        for ver in ['', '/v1']:
            path = '/clientadm{}/clients/{}/logo'.format(ver, uuid.UUID(clientid))
            res = self.testapp.get(path, status=200, headers=headers)
            assert res.content_type == 'image/png'
            out = res.body
            assert b'mylittlelogo' in out

    def test_get_client_logo_null(self):
        updated = parse_datetime(date_created)
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_logo.return_value = None, updated
        path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
        res = self.testapp.get(path, status=200, headers=headers)
        out = res.body
        assert out[1:4] == b'PNG'

    def test_get_client_logo_not_modified(self):
        updated = parse_datetime(date_created)
        date_newer = updated + timedelta(minutes=1)
        headers = {'Authorization': 'Bearer user_token', 'If-Modified-Since': httptime(date_newer)}
        self.session.get_client_logo.return_value = b'mylittlelogo', updated
        path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
        self.testapp.get(path, status=304, headers=headers)

    def test_get_client_logo_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_logo.side_effect = KeyError()
        path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
        self.testapp.get(path, status=404, headers=headers)

    def test_get_client_logo_default_logo_file_not_found(self):
        m = mock.mock_open()
        with mock.patch('coreapis.utils.open', m, create=True):
            updated = parse_datetime(date_created)
            headers = {'Authorization': 'Bearer user_token'}
            m.side_effect = FileNotFoundError()
            self.session.get_client_logo.return_value = None, updated
            path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
            self.testapp.get(path, status=500, headers=headers)

    def test_post_client_logo_multipart(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.save_logo = mock.MagicMock()
        for ver in ['', '/v1']:
            with open('data/default-client.png', 'rb') as fh:
                path = '/clientadm{}/clients/{}/logo'.format(ver, uuid.UUID(clientid))
                logo = fh.read()
                files = [('logo', 'logo.png', logo)]
                res = self.testapp.post(path, status=200, headers=headers, upload_files=files)
                out = res.json
                assert out == 'OK'

    def test_post_client_logo_body(self):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.save_logo = mock.MagicMock()
        with open('data/default-client.png', 'rb') as fh:
            path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
            logo = fh.read()
            res = self.testapp.post(path, logo, status=200, headers=headers)
            out = res.json
            assert out == 'OK'

    def test_post_client_logo_bad_data(self):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
        logo = b'mylittlelogo'
        self.testapp.post(path, logo, status=400, headers=headers)

    def _test_post_client_logo_not_owner(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        client['organization'] = 'fc:org:example.com'
        self.session.get_client_by_id.return_value = client
        self.session.is_org_admin.return_value = orgadmin
        self.session.save_logo = mock.MagicMock()
        with open('data/default-client.png', 'rb') as fh:
            path = '/clientadm/clients/{}/logo'.format(uuid.UUID(clientid))
            logo = fh.read()
            return self.testapp.post(path, logo, status=httpstat, headers=headers)

    def test_post_client_logo_not_owner(self):
        self._test_post_client_logo_not_owner(False, 403)

    def test_post_client_logo_org_admin(self):
        res = self._test_post_client_logo_not_owner(True, 200)
        assert res.json == 'OK'

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_post_client_logo_platform_admin(self, _):
        res = self._test_post_client_logo_not_owner(False, 200)
        assert res.json == 'OK'

    def test_list_public_scopes(self):
        for ver in ['', '/v1']:
            res = self.testapp.get('/clientadm{}/scopes/'.format(ver), status=200)
            assert 'userinfo' in res.json
            assert 'apigkadm' not in res.json

    def test_get_orgauthorization(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_gk_clients[3])
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        res = self.testapp.get(path, status=200, headers=headers)
        assert res.json[0] == testgk

    def test_get_orgauth_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError()
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        self.testapp.get(path, status=404, headers=headers)

    def _test_get_orgauth_not_owner(self, realmadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_gk_clients[3])
        client['owner'] = uuid.UUID(userid_other)
        self.session.get_client_by_id.return_value = client
        self.session.is_org_admin.return_value = realmadmin
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        return self.testapp.get(path, status=httpstat, headers=headers)

    def test_get_orgauth_not_owner(self):
        self._test_get_orgauth_not_owner(False, 403)

    def test_get_orgauth_realm_admin(self):
        res = self._test_get_orgauth_not_owner(True, 200)
        assert res.json[0] == testgk

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_get_orgauth_platform_admin(self, _):
        res = self._test_get_orgauth_not_owner(False, 200)
        assert res.json[0] == testgk

    def test_get_orgauth_empty_orgauthorization(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        res = self.testapp.get(path, status=200, headers=headers)
        assert res.json == []

    def test_get_orgauth_no_orgauthorization(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        del client['orgauthorization']
        self.session.get_client_by_id.return_value = client
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        self.testapp.get(path, status=404, headers=headers)

    def _test_update_orgauthorization(self, realmadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        self.session.is_org_admin.return_value = realmadmin
        return self.testapp.patch_json(path, [testgk], status=httpstat, headers=headers)

    def test_update_orgauthorization(self):
        res = self._test_update_orgauthorization(True, 200)
        assert res.json == [testgk]

    def test_update_orgauth_not_realm_admin(self):
        self._test_update_orgauthorization(False, 403)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_update_orgauthorization_platform_admin(self, _):
        res = self._test_update_orgauthorization(False, 200)
        assert res.json == [testgk]

    def test_update_orgauth_bad_realm(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = False
        for realm in [testrealm, 'big|bad|wolf.com', 'feide|vgs|' + testrealm]:
            path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, realm)
            self.testapp.patch_json(path, [testgk], status=403, headers=headers)

    def test_update_orgauth_bad_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        self.testapp.patch_json(path, testgk, status=400, headers=headers)

    def _test_delete_orgauthorization(self, ownerid, realmadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_gk_clients[3])
        client['owner'] = uuid.UUID(ownerid)
        self.session.get_client_by_id.return_value = client
        self.session.is_org_admin.return_value = realmadmin
        path = '/clientadm/clients/{}/orgauthorization/{}'.format(clientid, testrealm)
        self.testapp.delete(path, status=httpstat, headers=headers)

    def test_delete_orgauthorization_owner(self):
        self._test_delete_orgauthorization(userid_own, True, 204)

    def test_delete_orgauthorization_realm_admin(self):
        self._test_delete_orgauthorization(userid_other, True, 204)

    def test_delete_orgauthorization_stranger(self):
        self._test_delete_orgauthorization(userid_other, False, 403)

    @mock.patch('coreapis.clientadm.views.get_user', return_value=make_feide_user(PLATFORMADMIN))
    def test_delete_orgauthorization_platform_admin(self, _):
        self._test_delete_orgauthorization(userid_other, False, 204)

    def test_list_targetrealm(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = iter(deepcopy(retrieved_gk_clients))
        self.session.get_apigks.return_value = deepcopy(retrieved_apigks)
        self.session.get_client_by_id.return_value = deepcopy(retrieved_gk_clients[3])
        self.session.get_user_by_id.return_value = retrieved_user
        path = '/clientadm/realmclients/targetrealm/{}/'.format(testrealm)
        res = self.testapp.get(path, status=200, headers=headers)
        assert res.json[0]['scopeauthorizations'][testgk_foo] is True

    def _test_policy(self):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/clientadm/policy'
        return self.testapp.get(path, status=200, headers=headers)

    def test_policy_can_register(self):
        res = self._test_policy()
        assert res.json.get('register')

    @mock.patch('coreapis.clientadm.views.get_user',
                return_value=make_user('linkbook', '12345'))
    def test_policy_cannot_register(self, _):
        res = self._test_policy()
        assert 'register' in res.json and not res.json['register']
