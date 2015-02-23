import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import parse_datetime, json_normalize

post_body_minimal = {
    'name': 'per',
    'public': True,
}

post_body_maximal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'id': 'max-gk',
    'created': '2015-01-12T14:05:16+01:00', 'descr': 'green',
    'updated': '2015-01-12T14:05:16+01:00',
    'descr': 'new descr',
    'public': True,
}

user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
user2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
groupid1 = uuid.UUID("00000000-0000-0000-0001-000000000001")
groupid2 = uuid.UUID("00000000-0000-0000-0001-000000000002")
group1 = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid1,
    "owner": user1,
    "name": "pre update",
    "descr": "some data",
    "public": False,
}

member_token = '9nFIGK7dEiuVfXdGhVcgvaQVOBZScQ_6y9Yd2BTdMizUtL8yB5b7Im5Zcr3W9hjd'


class AdHocGroupAdmTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='adhocgroupadm', adhocgroupadm_maxrows=100,
            profile_token_secret='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        res = self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=200, headers=headers)
        assert res.json == json_normalize(group1)

    def test_missing_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.side_effect = KeyError()
        self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_groups(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_groups.return_value = [{'id': groupid1}]
        self.session().get_group_memberships.return_value = [
            {
                'groupid': groupid1,
            },
            {
                'groupid': groupid2,
            }
        ]
        self.session().get_group.return_value = {'id': groupid2}
        res = self.testapp.get('/adhocgroups/', status=200, headers=headers)
        out = res.json
        assert len(out) == 2
        assert out[0]['id'] == "00000000-0000-0000-0001-000000000001"
        assert out[1]['id'] == "00000000-0000-0000-0001-000000000002"

    def test_post_group_minimal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group = mock.MagicMock(side_effect=KeyError)
        res = self.testapp.post_json('/adhocgroups/', post_body_minimal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_group_maximal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.side_effect = KeyError()
        res = self.testapp.post_json('/adhocgroups/', post_body_maximal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_group_missing_name(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = 'foo'
        self.testapp.post('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_other_user(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['owner'] = 'owner'
        self.session().insert_group = mock.MagicMock()
        self.session().get_group.side_effect = KeyError()
        res = self.testapp.post_json('/adhocgroups/', body, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_group_invalid_text(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_invalid_text_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_unknown_attr(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_delete_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        self.testapp.delete('/adhocgroups/{}'.format(uuid.uuid4()), status=204, headers=headers)

    def test_delete_group_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/adhocgroups/', status=404, headers=headers)

    def test_update_no_change(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        res = self.testapp.patch_json('/adhocgroups/{}'.format(groupid1), {}, status=200, headers=headers)
        updated = res.json
        expected = json_normalize(group1)
        assert updated['updated'] > expected['updated']
        del updated['updated']
        del expected['updated']
        assert updated == expected

    def test_update_invalid_request(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        self.testapp.patch('/adhocgroups/{}'.format(groupid1), '{', status=400, headers=headers)
        self.testapp.patch_json('/adhocgroups/{}'.format(groupid1), {'endpoints': 'file:///etc/shadow'},
                                status=400, headers=headers)

    def test_update_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        to_update = deepcopy(group1)
        to_update['owner'] = uuid.uuid4()
        self.session().get_group.return_value = to_update
        self.testapp.patch_json('/adhocgroups/{}'.format(groupid1), {},
                                status=401, headers=headers)

    def test_get_group_members(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        self.session().get_group_members.return_value = []
        res = self.testapp.get('/adhocgroups/{}/members'.format(groupid1), status=200, headers=headers)
        assert res.json == []

    def test_get_group_members_no_access(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        group['owner'] = user2
        self.session().get_group.return_value = group
        self.session().get_group_members.return_value = []
        self.testapp.get('/adhocgroups/{}/members'.format(groupid1), status=401, headers=headers)

    def test_add_group_members_no_access(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        group['owner'] = user2
        self.session().get_group.return_value = group
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), [], status=401,
                                headers=headers)

    def test_add_group_members(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_userid_by_userid_sec.return_value = user1
        data = [
            {
                'token': member_token,
                'type': 'member',
            }
        ]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=200,
                                headers=headers)
        self.session().add_group_member.assert_called_with(groupid1, user1, 'member', 'unconfirmed')

    def test_add_group_members_bad_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch_json('/adhocgroups/abc/members', [], status=404,
                                headers=headers)

    def test_add_group_members_bad_data(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        self.testapp.patch('/adhocgroups/{}/members'.format(groupid1), '"', status=400,
                           headers=headers)

    def test_add_group_members_invalid_data(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        data = [{
            'token': member_token,
            'type': 'ninja',
        }]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=400,
                                headers=headers)

    def test_del_group_members(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_userid_by_userid_sec.return_value = user1
        data = [
            'p:' + str(user1),
        ]
        self.testapp.delete_json('/adhocgroups/{}/members'.format(groupid1), data, status=204,
                                 headers=headers)
        self.session().del_group_member.assert_called_with(groupid1, user1)

    def test_del_group_members_bad_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete_json('/adhocgroups/abc/members', [], status=404,
                                 headers=headers)

    def test_del_group_members_invalid_data(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.testapp.delete_json('/adhocgroups/{}/members'.format(groupid1), "foobar", status=400,
                                 headers=headers)

    def test_leave_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.testapp.delete_json('/adhocgroups/memberships', [str(groupid1)], status=200,
                                 headers=headers)
        self.session().del_group_member.assert_called_with(groupid1, user1)

    def test_confirm_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_membership_data.return_value = {
            'groupid': groupid1,
            'userid': user1,
            'status': 'unconfirmed',
            'type': 'normal',
        }
        self.testapp.patch_json('/adhocgroups/memberships', [str(groupid1)], status=200,
                                headers=headers)
        self.session().set_group_member_status.assert_called_with(groupid1, user1, "normal")

    def test_confirm_group_not_member(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_membership_data.side_effect = KeyError
        self.testapp.patch_json('/adhocgroups/memberships', [str(groupid1)], status=409,
                                headers=headers)
        assert not self.session().set_group_member_status.called
