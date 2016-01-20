import unittest
import mock
import uuid
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import now

testorg_id = 'fc:org:realm1.example.com'
testorg_realm = 'realm1.example.com'
testorg = {
    'id': testorg_id,
    'organization_number': 'NO00000001',
    'type': ['service_provider'],
    'realm': testorg_realm,
    'name': {'nb': 'testorganisasjon',
             'en': 'test organization', },
}
testorg2_id = 'fc:org:example.org'
testorg2 = {
    'id': testorg2_id,
    'organization_number': 'NO00000002',
    'type': ['service_provider'],
    'realm': None,
    'name': {'nb': 'testorganisasjon 2',
             'en': 'test organization 2', },
}
testservice = 'pilot'


PLATFORMADMIN = 'admin@example.com'


def make_user(feideid):
    return {
        'userid_sec': ['feide:' + str(feideid)]
    }


class OrgViewTests(unittest.TestCase):
    @mock.patch('coreapis.org.controller.get_platform_admins')
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client, gpa):
        gpa.return_value = [PLATFORMADMIN]
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='org', clientadm_maxrows=100, ldap_config_file='testdata/test-ldap-config.json')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_org(self):
        self.session.get_org.return_value = testorg
        for ver in ['', '/v1']:
            res = self.testapp.get('/orgs{}/{}'.format(ver, testorg), status=200)
            out = res.json
            assert out['realm'] == testorg_realm

    def test_get_org_not_found(self):
        self.session.get_org.side_effect = KeyError
        self.testapp.get('/orgs/{}'.format(testorg), status=404)

    def test_list_orgs(self):
        for ver in ['', '/v1']:
            self.session.list_orgs.return_value = iter([testorg, testorg2])
            res = self.testapp.get('/orgs{}/'.format(ver), status=200)
            out = res.json
            assert len(out) == 2
            assert out[0]['id'] == testorg_id
            assert out[1]['id'] == testorg2_id

    def test_list_orgs_with_peoplesearch(self):
        self.session.list_orgs.return_value = iter([testorg, testorg2])
        res = self.testapp.get('/orgs/?peoplesearch=true', status=200)
        out = res.json
        assert len(out) == 1
        assert out[0]['id'] == testorg_id

    def test_list_orgs_without_peoplesearch(self):
        self.session.list_orgs.return_value = iter([testorg, testorg2])
        res = self.testapp.get('/orgs/?peoplesearch=false', status=200)
        out = res.json
        assert len(out) == 1
        assert out[0]['id'] == testorg2_id

    def test_list_orgs_invalid_param(self):
        self.session.list_orgs.return_value = iter([testorg, testorg2])
        res = self.testapp.get('/orgs/?peoplesearch=ugle', status=200)
        out = res.json
        assert len(out) == 2

    def test_get_org_logo_default(self):
        self.session.get_org_logo.return_value = (None, None)
        for ver in ['', '/v1']:
            path = '/orgs{}/{}/logo'.format(ver, testorg)
            res = self.testapp.get(path, status=200)
            out = res.body
            assert b'PNG' == out[1:4]

    def test_get_org_logo(self):
        self.session.get_org_logo.return_value = (b"A logo", now())
        res = self.testapp.get('/orgs/{}/logo'.format(testorg), status=200)
        out = res.body
        assert out == b"A logo"

    def test_get_org_logo_no_org(self):
        self.session.get_org_logo.side_effect = KeyError
        self.testapp.get('/orgs/{}/logo'.format(testorg), status=404)

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

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
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

    def _test_list_mandatory_clients(self, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_mandatory_clients.return_value = []
        self.session.get_org.return_value = testorg
        return self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg_id), status=httpstat,
                                headers=headers)

    def test_list_mandatory_clients(self):
        res = self._test_list_mandatory_clients(True, 200)
        assert res.json == []

    def test_list_mandatory_clients_no_access(self):
        self._test_list_mandatory_clients(False, 403)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_list_mandatory_clients_platform_admin(self, get_user):
        res = self._test_list_mandatory_clients(False, 200)
        assert res.json == []

    def test_list_mandatory_clients_no_realm(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg2
        self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg2_id), status=403,
                         headers=headers)

    def _test_add_mandatory_client(self, clientid, orgadmin, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = orgadmin
        self.session.get_org.return_value = testorg
        self.testapp.put('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                         status=httpstat, headers=headers)

    def test_add_mandatory_client(self):
        clientid = uuid.uuid4()
        self._test_add_mandatory_client(clientid, True, 204)
        self.session.add_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_add_mandatory_client_no_access(self):
        clientid = uuid.uuid4()
        self._test_add_mandatory_client(clientid, False, 403)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_mandatory_client_platform_admin(self, get_user):
        clientid = uuid.uuid4()
        self._test_add_mandatory_client(clientid, False, 204)
        self.session.add_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_add_mandatory_client_malformed(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg
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
        self.session.get_org.return_value = testorg
        self.testapp.delete('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                            status=httpstat, headers=headers)

    def test_del_mandatory_client(self):
        clientid = uuid.uuid4()
        self._test_del_mandatory_client(clientid, True, 204)
        self.session.del_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_del_mandatory_client_no_access(self):
        clientid = uuid.uuid4()
        self._test_del_mandatory_client(clientid, False, 403)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_mandatory_client_platform_admin(self, get_user):
        clientid = uuid.uuid4()
        self._test_del_mandatory_client(clientid, False, 204)
        self.session.del_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_del_mandatory_client_malformed(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg
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
        assert res.json == []

    def test_list_services_no_access(self):
        self._test_list_services(False, 403)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_list_services_platform_admin(self, get_user):
        res = self._test_list_services(False, 200)
        assert res.json == []

    def _test_add_service(self, service, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg2
        self.testapp.put('/orgs/{}/services/{}'.format(testorg2_id, service),
                         status=httpstat, headers=headers)

    def test_add_service_org_admin(self):
        self._test_add_service(testservice, 403)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_service_platform_admin(self, get_user):
        self._test_add_service(testservice, 204)
        services = set()
        services.add(testservice)
        self.session.add_services.assert_called_with(testorg2_id, services)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_unknown_service(self, get_user):
        self._test_add_service("foo", 400)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
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

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_service_platform_admin(self, get_user):
        self._test_del_service(testservice, 204)
        services = set()
        services.add(testservice)
        self.session.del_services.assert_called_with(testorg2_id, services)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_service_unknown_org(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = False
        self.session.get_org.side_effect = KeyError
        self.testapp.delete('/orgs/{}/services/{}'.format(testorg2_id, testservice),
                            status=404, headers=headers)

    @mock.patch('coreapis.org.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_del_unknown_service(self, get_user):
        self._test_del_service("foo", 400)
