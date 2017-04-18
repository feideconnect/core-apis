import unittest
import mock
import uuid
from copy import deepcopy
import webtest
from pyramid import testing
from coreapis import main, middleware
from coreapis.authorizations.tests.data import (authz1, ret_authz1, client1, group1, user1, clients, users)
#from coreapis.utils import json_normalize


class AuthzviewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'dataporten.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='authorizations')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = webtest.TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_list_authz(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_authorizations.return_value = iter([authz1])
        self.session.get_client_by_id.return_value = {'id': client1, 'name': 'foo'}
        res = self.testapp.get('/authorizations/', status=200, headers=headers)
        assert res.json == [ret_authz1]

    def test_list_authz_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_authorizations.return_value = iter([authz1])
        self.session.get_client_by_id.side_effect = KeyError()
        res = self.testapp.get('/authorizations/', status=200, headers=headers)
        assert res.json == []

    def test_delete_authz(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/authorizations/{}'.format(client1), status=204, headers=headers)

    def test_delete_authz_bad_uuid(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/authorizations/{}'.format('foo'), status=404, headers=headers)

    def test_delete_all_authz(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.is_org_admin.return_value = False
        self.session.get_client_by_id.return_value = clients[client1]
        self.testapp.delete('/authorizations/all_users/{}'.format(client1),
                            status=204, headers=headers)

    def test_delete_all_authz_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(clients[client1])
        client['owner'] = uuid.uuid4()
        self.session.is_org_admin.return_value = False
        self.testapp.delete('/authorizations/all_users/{}'.format(client1),
                            status=403, headers=headers)

    def test_delete_all_authz_bad_uuid(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/authorizations/all_users/{}'.format('foo'),
                            status=404, headers=headers)

    def test_resources_owned(self):
        headers = {'Authorization': 'Bearer user_token'}
        for groups, expected in [([], True), ([{}], False)]:
            self.session.get_groups.return_value = iter(groups)
            res = self.testapp.get('/authorizations/resources_owned', status=200, headers=headers)
            assert expected == res.json['ready']

    def test_consent_withdrawn(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_group_memberships.return_value = iter([{'groupid': group1}])
        self.session.get_authorizations.return_value = iter([authz1])
        self.session.get_client_by_id.return_value = {'id': client1, 'name': 'foo'}
        self.testapp.post('/authorizations/consent_withdrawn', status=200, headers=headers)

    def test_consent_withdrawn_not_ready(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = iter([{}])
        self.testapp.post('/authorizations/consent_withdrawn', status=403, headers=headers)

    def test_get_mandatory_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = iter([])
        self.session.get_mandatory_clients.return_value = [client1]
        self.session.get_client_by_id.return_value = clients[client1]
        self.session.get_user_by_id.return_value = users[user1]
        resp = self.testapp.get('/authorizations/mandatory_clients/', status=200, headers=headers)

        assert resp.json == [
            {'authproviders': [],
             'descr': 'green',
             'homepageurl': None,
             'id': '00000000-0000-0000-0001-000000000001',
             'loginurl': None,
             'name': 'per',
             'organization': None,
             'owner': {'id': 'p:foo', 'name': 'foo'},
             'privacypolicyurl': None,
             'redirect_uri': ['https://test.example.com'],
             'supporturl': None,
             'systemdescr': None}]
        self.session.get_clients.return_value = [clients[client1]]
        self.session.get_mandatory_clients.return_value = []
#        self.session.get_client_by_id.return_value = clients[client1]
        self.session.get_user_by_id.return_value = users[user1]
        resp = self.testapp.get('/authorizations/mandatory_clients/', status=200, headers=headers)

        assert resp.json == [
            {'authproviders': [],
             'descr': 'green',
             'homepageurl': None,
             'id': '00000000-0000-0000-0001-000000000001',
             'loginurl': None,
             'name': 'per',
             'organization': None,
             'owner': {'id': 'p:foo', 'name': 'foo'},
             'privacypolicyurl': None,
             'redirect_uri': ['https://test.example.com'],
             'supporturl': None,
             'systemdescr': None}]
