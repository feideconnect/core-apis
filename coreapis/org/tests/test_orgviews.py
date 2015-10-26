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


class OrgViewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
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
        self.session.list_orgs.return_value = [testorg, testorg2]
        for ver in ['', '/v1']:
            res = self.testapp.get('/orgs{}/'.format(ver), status=200)
            out = res.json
            assert len(out) == 2
            assert out[0]['id'] == testorg_id
            assert out[1]['id'] == testorg2_id

    def test_list_orgs_with_peoplesearch(self):
        self.session.list_orgs.return_value = [testorg, testorg2]
        res = self.testapp.get('/orgs/?peoplesearch=true', status=200)
        out = res.json
        assert len(out) == 1
        assert out[0]['id'] == testorg_id

    def test_list_orgs_without_peoplesearch(self):
        self.session.list_orgs.return_value = [testorg, testorg2]
        res = self.testapp.get('/orgs/?peoplesearch=false', status=200)
        out = res.json
        assert len(out) == 1
        assert out[0]['id'] == testorg2_id

    def test_list_orgs_invalid_param(self):
        self.session.list_orgs.return_value = [testorg, testorg2]
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

    def test_list_mandatory_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_mandatory_clients.return_value = []
        self.session.get_org.return_value = testorg
        res = self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg_id), status=200,
                               headers=headers)
        assert res.json == []

    def test_list_mandatory_clients_no_access(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = False
        self.session.get_org.return_value = testorg
        self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg_id), status=403,
                         headers=headers)

    def test_list_mandatory_clients_no_realm(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg2
        self.testapp.get('/orgs/{}/mandatory_clients/'.format(testorg2_id), status=403,
                         headers=headers)

    def test_add_mandatory_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg
        clientid = uuid.uuid4()
        res = self.testapp.post_json('/orgs/{}/mandatory_clients/'.format(testorg_id),
                                     str(clientid), status=201, headers=headers)
        self.session.add_mandatory_client.assert_called_with(testorg_realm, clientid)
        assert res.json == str(clientid)

    def test_add_mandatory_client_malformed(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg
        clientid = "malformed uuid"
        self.testapp.post_json('/orgs/{}/mandatory_clients/'.format(testorg_id),
                               str(clientid), status=400, headers=headers)

    def test_del_mandatory_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg
        clientid = uuid.uuid4()
        self.testapp.delete('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                            status=204, headers=headers)
        self.session.del_mandatory_client.assert_called_with(testorg_realm, clientid)

    def test_del_mandatory_client_malformed(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = True
        self.session.get_org.return_value = testorg
        clientid = "foo"
        self.testapp.delete('/orgs/{}/mandatory_clients/{}'.format(testorg_id, clientid),
                            status=404, headers=headers)
