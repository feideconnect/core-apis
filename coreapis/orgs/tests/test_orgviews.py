import unittest
import mock
import uuid
import json
from copy import deepcopy
import webtest
from pyramid import testing
from cassandra.util import SortedSet
from coreapis import main, middleware
from coreapis.utils import now, json_normalize
from coreapis.clientadm.tests.helper import retrieved_client
from coreapis.clientadm.tests.helper import clientid as testclient_id

testorg_id = 'fc:org:realm1.example.com'
testorg_realm = 'realm1.example.com'
testorg = {
    'id': testorg_id,
    'organization_number': 'NO00000001',
    'type': SortedSet(['service_provider']),
    'realm': testorg_realm,
    'name': {'nb': 'testorganisasjon',
             'en': 'test organization', },
}
testorg2_id = 'fc:org:example.org'
testorg2 = {
    'id': testorg2_id,
    'organization_number': 'NO00000002',
    'type': SortedSet(['service_provider']),
    'realm': None,
    'name': {'nb': 'testorganisasjon 2',
             'en': 'test organization 2', },
    'services': ['auth'],
}
testidentity = 'feide:foo@bar.no'
testrole = {'orgid': testorg_id,
            'identity':  testidentity,
            'role': 'admin'}
testservice = 'pilot'
eg7 = dict(lat=63.4201, lon=18.969388)


PLATFORMADMIN = 'admin@example.com'


def make_user(feideid):
    return {
        'userid_sec': ['feide:' + str(feideid)],
        'userid': uuid.uuid4(),
        'name': {
            'feide': "The Admin",
        },
        'selectedsource': 'feide',
    }


def orgs_match(raw, formatted):
    return all(formatted[key] == raw[key] for key in raw)


class OrgViewTests(unittest.TestCase):
    @mock.patch('coreapis.orgs.controller.get_platform_admins')
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client, gpa):
        gpa.return_value = [PLATFORMADMIN]
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'dataporten.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='orgs', clientadm_maxrows=100, ldap_config_file='testdata/test-ldap-config.json')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = webtest.TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_org(self):
        org = deepcopy(testorg)
        org['uiinfo'] = dict(geo=[eg7])
        body = deepcopy(org)
        body['uiinfo'] = json.dumps(org['uiinfo'])
        for ver in ['', '/v1']:
            self.session.get_org.return_value = deepcopy(body)
            res = self.testapp.get('/orgs{}/{}'.format(ver, testorg_id), status=200)
            out = res.json
            assert out['realm'] == testorg_realm
            assert out['uiinfo'] == org['uiinfo']

    def test_get_org_not_found(self):
        self.session.get_org.side_effect = KeyError
        self.testapp.get('/orgs/{}'.format(testorg_id), status=404)

    def test_list_orgs(self):
        for ver in ['', '/v1']:
            self.session.list_orgs.return_value = (deepcopy(org) for org in [testorg, testorg2])
            res = self.testapp.get('/orgs{}/'.format(ver), status=200)
            out = res.json
            assert len(out) == 2
            assert out[0]['id'] == testorg_id
            assert out[1]['id'] == testorg2_id

    def test_list_orgs_with_peoplesearch(self):
        self.session.list_orgs.return_value = (deepcopy(org) for org in [testorg, testorg2])
        res = self.testapp.get('/orgs/?peoplesearch=true', status=200)
        out = res.json
        assert len(out) == 1
        assert out[0]['id'] == testorg_id

    def test_list_orgs_without_peoplesearch(self):
        self.session.list_orgs.return_value = (deepcopy(org) for org in [testorg, testorg2])
        res = self.testapp.get('/orgs/?peoplesearch=false', status=200)
        out = res.json
        assert len(out) == 1
        assert out[0]['id'] == testorg2_id

    def test_list_orgs_invalid_param(self):
        self.session.list_orgs.return_value = (deepcopy(org) for org in [testorg, testorg2])
        res = self.testapp.get('/orgs/?peoplesearch=ugle', status=200)
        out = res.json
        assert len(out) == 2

    def _test_post_org(self, httpstat, body):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_org.side_effect = KeyError()
        return self.testapp.post_json('/orgs/', body,
                                      status=httpstat, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org(self, get_user):
        res = self._test_post_org(201, body=json_normalize(testorg))
        assert orgs_match(testorg, res.json)

    def test_post_org_no_access(self):
        self._test_post_org(403, json_normalize(testorg))

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_duplicate(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_org.return_value = {'foo': 'bar'}
        self.testapp.post_json('/orgs/', json_normalize(testorg), status=409, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_invalid_json(self, get_user):
        self._test_post_org(400, body='foo')

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_not_json_object(self, get_user):
        self._test_post_org(400, body='"foo"')

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_empty_name(self, get_user):
        org = json_normalize(testorg)
        org['name'] = {}
        self._test_post_org(400, body=org)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_too_long_language_in_name(self, get_user):
        org = json_normalize(testorg)
        org['name'].update(dict(nynorsk='testorganisasjon'))
        self._test_post_org(400, body=org)

    def _test_update_org(self, httpstat, body):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_org.return_value = deepcopy(testorg)
        path = '/orgs/{}'.format(testorg_id)
        return self.testapp.patch_json(path, body, status=httpstat, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_update_org_no_change(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_org.return_value = deepcopy(testorg)
        path = '/orgs/{}'.format(testorg_id)
        body = self.testapp.get(path, status=200, headers=headers).json
        res = self.testapp.patch_json(path, body, status=200, headers=headers)
        assert orgs_match(testorg, res.json)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_update_org(self, get_user):
        body = dict(uiinfo=dict(geo=[eg7]))
        res = self._test_update_org(200, body)
        updated = res.json
        assert updated['uiinfo'] == body['uiinfo']
        assert 'type' in updated

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_update_org_add_type(self, get_user):
        body = dict(type=["higher_education", "home_organization"])
        res = self._test_update_org(200, body)
        updated = res.json
        assert updated['type'] == body['type']

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_update_org_change_id(self, get_user):
        body = dict(id='fc:org:uixyz.no')
        res = self._test_update_org(200, body)
        assert res.json['id'] != body['id']

    def test_update_org_no_access(self):
        body = json_normalize(testorg)
        self._test_update_org(403, body)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_update_org_invalid_json(self, get_user):
        body = 'foo'
        self._test_update_org(400, body)

    def _test_delete_org(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/orgs/{}'.format(testorg_id)
        return self.testapp.delete(path, status=httpstat, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_delete_org(self, get_user):
        self._test_delete_org(204)

    def test_delete_org_no_access(self):
        self._test_delete_org(403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_delete_missing_org(self, get_user):
        self.session.get_org.side_effect = KeyError
        self._test_delete_org(404)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_delete_org_mandatory_clients(self, get_user):
        self.session.get_mandatory_clients.return_value = iter([1])
        self._test_delete_org(400)

    def test_get_org_logo_default(self):
        self.session.get_org_logo.return_value = (None, None)
        for ver in ['', '/v1']:
            path = '/orgs{}/{}/logo'.format(ver, testorg_id)
            res = self.testapp.get(path, status=200)
            out = res.body
            assert b'PNG' == out[1:4]

    def _test_get_org_roles(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/orgs/{}/roles/'.format(testorg_id)
        self.session.get_roles.return_value = [testrole]
        return self.testapp.get(path, status=httpstat, headers=headers)

    def test_get_org_roles(self):
        self._test_get_org_roles(403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_get_org_roles_platform_admin(self, _):
        res = self._test_get_org_roles(200)
        assert 'admin' in res.json[0]['role']

    def test_get_org_roles_bad_orgid(self):
        self.session.get_org.side_effect = KeyError
        self._test_get_org_roles(404)

    def _test_add_org_role(self, httpstat, identity, rolenames):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/orgs/{}/roles/{}'.format(testorg_id, identity)
        self.session.get_roles.return_value = [testrole]
        return self.testapp.put_json(path, rolenames, status=httpstat, headers=headers)

    def test_add_org_role(self):
        self._test_add_org_role(403, testidentity, ['admin'])

    def test_add_org_role_bad_orgid(self):
        self.session.get_org.side_effect = KeyError
        self._test_add_org_role(404, testidentity, ['admin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_platform_admin(self, _):
        self._test_add_org_role(204, testidentity, ['admin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_social(self, _):
        self._test_add_org_role(204, 'facebook:3141592653589793', ['admin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_bad_identity(self, _):
        self._test_add_org_role(400, 'hello', ['admin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_bad_provider(self, _):
        self._test_add_org_role(400, 'bogus:foo@bar', ['admin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_malformed_identity(self, _):
        self._test_add_org_role(400, dict(identity=testidentity), ['admin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_bad_rolename(self, _):
        self._test_add_org_role(400, testidentity, ['amin'])

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_org_role_malformed_body(self, _):
        self._test_add_org_role(400, testidentity, 3)

    def _test_del_org_role(self, httpstat, identity):
        headers = {'Authorization': 'Bearer user_token'}
        path = '/orgs/{}/roles/{}'.format(testorg_id, identity)
        return self.testapp.delete(path, status=httpstat, headers=headers)

    def test_del_org_role(self):
        self._test_del_org_role(403, testidentity)

    def test_del_org_role_bad_orgid(self):
        self.session.get_org.side_effect = KeyError
        self._test_del_org_role(404, testidentity)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_org_role_platform_admin(self, _):
        self._test_del_org_role(204, testidentity)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_org_role_bad_identity(self, _):
        self._test_del_org_role(400, 'feide:hello')

    def test_get_org_logo(self):
        self.session.get_org_logo.return_value = (b"A logo", now())
        res = self.testapp.get('/orgs/{}/logo'.format(testorg_id), status=200)
        out = res.body
        assert out == b"A logo"

    def test_get_org_logo_no_org(self):
        self.session.get_org_logo.side_effect = KeyError
        self.testapp.get('/orgs/{}/logo'.format(testorg_id), status=404)

    def _test_post_org_logo_body(self, ver, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_org.return_value = testorg2
        self.session.save_org_logo = mock.MagicMock()
        with open('data/default-client.png', 'rb') as fh:
            path = '/orgs{}/{}/logo'.format(ver, uuid.uuid4())
            logo = fh.read()
            return self.testapp.post(path, logo, status=httpstat, headers=headers)

    def test_post_org_logo_body(self):
        for ver in ['', '/v1']:
            res = self._test_post_org_logo_body(ver, True, 200)
            assert res.json == 'OK'

    def test_post_org_logo_body_not_admin(self):
        self._test_post_org_logo_body('', False, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_logo_body_platform_admin(self, get_user):
        res = self._test_post_org_logo_body('', False, 200)
        assert res.json == 'OK'

    def test_post_org_logo_body_unknown_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.side_effect = KeyError
        with open('data/default-client.png', 'rb') as fh:
            path = '/orgs{}/{}/logo'.format('', uuid.uuid4())
            logo = fh.read()
            self.testapp.post(path, logo, status=404, headers=headers)

    def _test_post_org_geo(self, ver, geo, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_org.return_value = deepcopy(testorg2)
        self.session.insert_org = mock.MagicMock()
        path = '/orgs{}/{}/geo'.format(ver, uuid.uuid4())
        return self.testapp.post_json(path, geo, status=httpstat, headers=headers)

    def test_post_org_geo(self):
        for ver in ['', '/v1']:
            res = self._test_post_org_geo(ver, [eg7], True, 200)
            assert res.json == 'OK'

    def test_post_org_geo_west_pole(self):
        self._test_post_org_geo('', [dict(lat=0, lon=270)], True, 400)

    def test_post_org_geo_wrong_kind_of_json(self):
        self._test_post_org_geo('', "this_is_also_json", True, 400)

    def test_post_org_geo_not_admin(self):
        self._test_post_org_geo('', [], False, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_post_org_geo_platform_admin(self, get_user):
        res = self._test_post_org_geo('', [], False, 200)
        assert res.json == 'OK'

    def test_post_org_geo_unknown_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.side_effect = KeyError
        path = '/orgs{}/{}/geo'.format('', uuid.uuid4())
        return self.testapp.post_json(path, [], status=404, headers=headers)

    def _test_list_mandatory_clients(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_mandatory_clients.return_value = iter([testclient_id])
        self.session.get_client_by_id.return_value = retrieved_client
        self.session.get_org.return_value = deepcopy(testorg)
        with mock.patch('coreapis.crud_base.public_userinfo') as pui:
            pui.return_value = {'foo': 'bar'}
            with mock.patch('coreapis.crud_base.public_orginfo') as poi:
                poi.return_value = {'ditt': 'datt'}
                return self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg_id),
                                        status=httpstat, headers=headers)

    def test_list_mandatory_clients(self):
        res = self._test_list_mandatory_clients(True, 200)
        assert len(res.json) == 1
        assert res.json[0]['redirect_uri'] == retrieved_client['redirect_uri']

    def test_list_mandatory_clients_no_access(self):
        self._test_list_mandatory_clients(False, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_list_mandatory_clients_platform_admin(self, get_user):
        res = self._test_list_mandatory_clients(False, 200)
        assert len(res.json) == 1
        assert res.json[0]['redirect_uri'] == retrieved_client['redirect_uri']

    def test_list_mandatory_clients_no_realm(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg2
        self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg2_id), status=404,
                         headers=headers)

    def _test_add_mandatory_client(self, clientid, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_org.return_value = deepcopy(testorg)
        self.testapp.put('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                         status=httpstat, headers=headers)

    def test_add_mandatory_client(self):
        clientid = uuid.uuid4()
        self._test_add_mandatory_client(clientid, True, 204)
        self.session.add_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_add_mandatory_client_no_access(self):
        clientid = uuid.uuid4()
        self._test_add_mandatory_client(clientid, False, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_mandatory_client_platform_admin(self, get_user):
        clientid = uuid.uuid4()
        self._test_add_mandatory_client(clientid, False, 204)
        self.session.add_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_add_mandatory_client_malformed(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = deepcopy(testorg)
        clientid = "malformed uuid"
        self.testapp.put('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                         status=400, headers=headers)

    def test_add_mandatory_client_unknown_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.side_effect = KeyError
        clientid = uuid.uuid4()
        self.testapp.put('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                         status=404, headers=headers)

    def _test_del_mandatory_client(self, clientid, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_org.return_value = deepcopy(testorg)
        self.testapp.delete('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                            status=httpstat, headers=headers)

    def test_del_mandatory_client(self):
        clientid = uuid.uuid4()
        self._test_del_mandatory_client(clientid, True, 204)
        self.session.del_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_del_mandatory_client_no_access(self):
        clientid = uuid.uuid4()
        self._test_del_mandatory_client(clientid, False, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_mandatory_client_platform_admin(self, get_user):
        clientid = uuid.uuid4()
        self._test_del_mandatory_client(clientid, False, 204)
        self.session.del_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_del_mandatory_client_malformed(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = deepcopy(testorg)
        clientid = "foo"
        self.testapp.delete('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                            status=404, headers=headers)

    def test_del_mandatory_client_unknown_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.side_effect = KeyError
        clientid = uuid.uuid4()
        self.testapp.delete('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                            status=404, headers=headers)

    def _test_list_services(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_org.return_value = testorg2
        return self.testapp.get('/orgs/{}/services/'.format(testorg2_id), status=httpstat,
                                headers=headers)

    def test_list_services(self):
        res = self._test_list_services(True, 200)
        assert res.json == ['auth']

    def test_list_services_no_access(self):
        self._test_list_services(False, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_list_services_platform_admin(self, get_user):
        res = self._test_list_services(False, 200)
        assert res.json == ['auth']

    def _test_add_service(self, service, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg2
        self.testapp.put('/orgs/{}/services/{}'.format(testorg2_id, service),
                         status=httpstat, headers=headers)

    def test_add_service_org_admin(self):
        self._test_add_service(testservice, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_service_platform_admin(self, get_user):
        self._test_add_service(testservice, 204)
        services = set()
        services.add(testservice)
        self.session.add_services.assert_called_with(testorg2_id, services)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_unknown_service(self, get_user):
        self._test_add_service("foo", 400)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_service_unknown_org(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = False
        self.session.get_org.side_effect = KeyError
        self.testapp.put('/orgs/{}/services/{}'.format(testorg2_id, testservice),
                         status=404, headers=headers)

    def _test_del_service(self, service, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg2
        self.testapp.delete('/orgs/{}/services/{}'.format(testorg2_id, service),
                            status=httpstat, headers=headers)

    def test_del_service_org_admin(self):
        self._test_del_service(testservice, 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_service_platform_admin(self, get_user):
        self._test_del_service(testservice, 204)
        services = set()
        services.add(testservice)
        self.session.del_services.assert_called_with(testorg2_id, services)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_service_unknown_org(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = False
        self.session.get_org.side_effect = KeyError
        self.testapp.delete('/orgs/{}/services/{}'.format(testorg2_id, testservice),
                            status=404, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_unknown_service(self, get_user):
        self._test_del_service("foo", 400)
