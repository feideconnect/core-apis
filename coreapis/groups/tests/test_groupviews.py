import unittest
import mock
from webtest import TestApp
from coreapis import main, middleware
from . import groupid1, groupid2


class GroupsViewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
            'use_eventlets': 'true',
        }, enabled_components='groups', groups_backend_test='coreapis.groups.tests:MockBackend')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.testapp = TestApp(mw)

    def test_grouptypes(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/grouptypes', status=200, headers=headers)
        out = res.json
        assert len(out) == 1
        gtype = out[0]
        assert 'id' in gtype
        assert 'displayName' in gtype
        assert gtype['id'] == 'feideconnect:test'

    def test_group_members(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/groups/{}/members'.format(groupid1),
                               status=200, headers=headers)
        members = res.json
        assert len(members) == 1
        assert members[0]['name'] == "test user 1"
        assert members[0]['membership']['basic'] == 'member'

    def test_group_members_showall(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/groups/{}/members'.format(groupid1),
                               status=200, headers=headers, params=dict(showAll='true'))
        members = res.json
        assert len(members) == 2
        assert members[0]['name'] == "test user 1"
        assert members[0]['membership']['basic'] == 'member'
        assert members[1]['name'] == "test user 2"
        assert members[1]['membership']['basic'] == 'member'
        assert members[1]['membership']['active'] is False

    def test_get_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/groups/{}'.format(groupid1),
                               status=200, headers=headers)
        group = res.json
        assert group['id'] == groupid1
        assert 'displayName' in group

    def test_get_group_no_access(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/groups/groups/{}'.format(groupid2),
                         status=404, headers=headers)

    def test_get_membership(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/me/groups/{}'.format(groupid1),
                               status=200, headers=headers)
        membership = res.json
        assert membership['basic'] == 'member'

    def test_get_membership_not_member(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/groups/me/groups/{}'.format(groupid2),
                         status=404, headers=headers)

    def test_get_member_groups(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/me/groups',
                               status=200, headers=headers)
        groups = res.json
        assert len(groups) == 1
        assert groups[0]['id'] == groupid1
        assert 'displayName' in groups[0]

    def test_get_groups(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/groups',
                               status=200, headers=headers)
        groups = res.json
        assert len(groups) == 2
        assert groups[0]['id'] == groupid1
        assert 'displayName' in groups[0]
        assert groups[1]['id'] == groupid2
        assert 'displayName' in groups[1]


class GroupsViewErrorHandlingTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
            'use_eventlets': 'true',
        }, enabled_components='groups', groups_timeout_backend='200',
            groups_backend_test='coreapis.groups.tests:MockBackend',
            groups_backend_stale='coreapis.groups.tests:StaleBackend',
            groups_backend_crash='coreapis.groups.tests:CrashBackend')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.testapp = TestApp(mw)

    def test_get_groups(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/groups/groups',
                               status=200, headers=headers)
        groups = res.json
        assert len(groups) == 2
        assert groups[0]['id'] == groupid1
        assert 'displayName' in groups[0]
        assert groups[1]['id'] == groupid2
        assert 'displayName' in groups[1]

    def test_get_group_bad_prefix(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/groups/groups/nosuch:group',
                         status=404, headers=headers)

    def test_get_group_bad_groupid(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/groups/groups/nocolon',
                         status=404, headers=headers)

    def test_my_groups_clientonly(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.get('/groups/me/groups',
                         status=403, headers=headers)

    def test_my_membership_clientonly(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.get('/groups/me/groups/somegroupid',
                         status=403, headers=headers)
