import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import (json_normalize, now)
from coreapis.adhocgroupadm.tests.data import \
    public_userinfo, public_userinfo_view, \
    group1, group1_invitation, group1_view, groupid1, group1_details, \
    group2, group2_invitation, group2_view, groupid2, \
    user1, user2, \
    post_body_minimal, post_body_maximal, member_token


PLATFORMADMIN = 'admin@example.com'


def make_user(feideid):
    return {
        'userid': 'foo',
        'userid_sec': ['feide:' + str(feideid)]
    }


class AdHocGroupAdmTests(unittest.TestCase):
    @mock.patch('coreapis.adhocgroupadm.controller.get_platform_admins')
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
        }, enabled_components='adhocgroupadm', adhocgroupadm_maxrows=100,
            adhocgroupadm_max_add_members=4,
            profile_token_secret='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_group_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        self.session().get_user_by_id.return_value = public_userinfo
        res = self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=200, headers=headers)
        assert res.json == group1_view

    def test_get_group_invitation(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group2
        self.session().get_user_by_id.return_value = public_userinfo
        res = self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()),
                               {'invitation_token': group2_invitation},
                               status=200, headers=headers)
        assert res.json == group2_view

    def test_get_group_wrong_invitation(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group2
        self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()),
                         {'invitation_token': group1_invitation},
                         status=403, headers=headers)

    def _test_get_group_no_access(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group2
        self.session().get_user_by_id.return_value = public_userinfo
        self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=httpstat, headers=headers)

    def test_get_group_no_access(self):
        self._test_get_group_no_access(403)

    @mock.patch('coreapis.adhocgroupadm.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_get_group_platform_admin(self, get_user):
        self._test_get_group_no_access(200)

    def test_get_group_member(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group2
        self.session().get_user_by_id.return_value = public_userinfo
        self.session().get_membership_data.return_value = dict(type='member', status='normal')
        res = self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=200, headers=headers)
        assert res.json == group2_view

    def test_get_group_details(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        self.session().get_user_by_id.return_value = public_userinfo
        res = self.testapp.get('/adhocgroups/{}/details'.format(uuid.uuid4()), status=200, headers=headers)
        assert res.json == json_normalize(group1_details)

    def test_missing_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.side_effect = KeyError()
        self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_groups(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_groups.return_value = [group1]
        self.session().get_user_by_id.return_value = public_userinfo
        self.session().get_group_memberships.return_value = [
            {
                'groupid': groupid1,
            },
            {
                'groupid': groupid2,
            }
        ]
        self.session().get_group.return_value = group2
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

    def _test_delete_group(self, group, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group
        self.testapp.delete('/adhocgroups/{}'.format(uuid.uuid4()),
                            status=httpstat, headers=headers)

    def test_delete_group(self):
        self._test_delete_group(group1, 204)

    def test_delete_group_not_owner(self):
        self._test_delete_group(group2, 403)

    @mock.patch('coreapis.adhocgroupadm.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_delete_group_platform_admin(self, get_user):
        self._test_delete_group(group2, 204)

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

    def _test_update_not_owner(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        to_update = deepcopy(group1)
        to_update['owner'] = uuid.uuid4()
        self.session().get_group.return_value = to_update
        return self.testapp.patch_json('/adhocgroups/{}'.format(groupid1), {},
                                       status=httpstat, headers=headers)

    def test_update_not_owner(self):
        res = self._test_update_not_owner(403)
        assert res.www_authenticate is None

    @mock.patch('coreapis.adhocgroupadm.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_update_platform_admin(self, get_user):
        self._test_update_not_owner(200)

    def test_get_group_members_empty(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        self.session().get_group_members.return_value = []
        res = self.testapp.get('/adhocgroups/{}/members'.format(groupid1), status=200, headers=headers)
        assert res.json == []

    def test_get_group_members(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        members = [
            {'userid': user1, 'type': 'member', 'status': 'normal'},
            {'userid': user2, 'type': 'admin', 'status': 'normal'}
        ]
        self.session().get_group_members.return_value = members
        self.session().get_user_by_id.return_value = public_userinfo
        res = self.testapp.get('/adhocgroups/{}/members'.format(groupid1), status=200,
                               headers=headers)
        expected1 = {'type': 'member', 'status': 'normal', 'is_owner': True}
        expected1.update(public_userinfo_view)
        expected2 = {'type': 'admin', 'status': 'normal'}
        expected2.update(public_userinfo_view)
        assert res.json == [expected1, expected2]

    def _test_get_group_members_no_access(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        group['owner'] = user2
        self.session().get_group.return_value = group
        self.session().get_group_members.return_value = []
        self.testapp.get('/adhocgroups/{}/members'.format(groupid1),
                         status=httpstat, headers=headers)

    def test_get_group_members_no_access(self):
        self._test_get_group_members_no_access(403)

    @mock.patch('coreapis.adhocgroupadm.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_get_group_members_platform_admin(self, get_user):
        self._test_get_group_members_no_access(200)

    def _test_add_group_members_no_access(self, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        group['owner'] = user2
        self.session().get_group.return_value = group
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), [], status=httpstat,
                                headers=headers)

    def test_add_group_members_no_access(self):
        self._test_add_group_members_no_access(403)

    @mock.patch('coreapis.adhocgroupadm.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_add_group_members_platform_admin(self, get_user):
        self._test_add_group_members_no_access(200)

    def test_add_group_members_over_limit(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_group_members.return_value = list(range(10))
        data = [
            {
                'token': member_token,
                'type': 'member',
            }
        ]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=409,
                                headers=headers)

    def test_change_membership_type_over_limit(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_group_members.return_value = list(range(10))
        self.session().get_userid_by_userid_sec.return_value = user1
        data = [
            {
                'id': 'p:' + str(user1),
                'type': 'member',
            }
        ]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=200,
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
        self.session().add_group_member.assert_called_with(groupid1, user1, 'member', 'unconfirmed', None)

    def test_add_group_members_bad_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch_json('/adhocgroups/abc/members', [], status=404,
                                headers=headers)

    def test_add_group_members_bad_data(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        self.testapp.patch('/adhocgroups/{}/members'.format(groupid1), '"', status=400,
                           headers=headers)

    def test_add_group_members_invalid_type(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        data = [{
            'token': member_token,
            'type': 'ninja',
        }]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=400,
                                headers=headers)

    def test_add_group_members_only_type(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        data = [{
            'type': 'member',
        }]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=400,
                                headers=headers)

    def test_add_group_members_invalid_token(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        data = [{
            'token': '',
            'type': 'member',
        }]
        res = self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=400,
                                      headers=headers)
        assert 'message' in res.json

    def test_update_group_member_type(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_userid_by_userid_sec.return_value = user1
        data = [
            {
                'id': 'p:' + str(user1),
                'type': 'member',
            }
        ]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=200,
                                headers=headers)
        self.session().set_group_member_type.assert_called_with(groupid1, user1, 'member')

    def test_update_group_member_invalid_type(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_userid_by_userid_sec.return_value = user1
        data = [
            {
                'id': 'p:' + str(user1),
                'type': 'ninja',
            }
        ]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=400,
                                headers=headers)

    def test_update_group_member_invalid_user(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_userid_by_userid_sec.side_effect = KeyError('No such user')
        data = [
            {
                'id': 'p:' + str(user1),
                'type': 'member',
            }
        ]
        self.testapp.patch_json('/adhocgroups/{}/members'.format(groupid1), data, status=400,
                                headers=headers)

    def test_update_group_member_not_member(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_membership_data.side_effect = KeyError('No such membership')
        data = [
            {
                'id': 'p:' + str(user1),
                'type': 'member',
            }
        ]
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

    def test_get_memberships(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_user_by_id.return_value = public_userinfo
        self.session().get_group.return_value = group
        self.session().get_group_memberships.return_value = [
            {
                'groupid': groupid1,
                'userid': user1,
                'status': 'normal',
                'type': 'member',
            },
        ]

        res = self.testapp.get('/adhocgroups/memberships', status=200,
                               headers=headers)
        memberships = res.json
        assert len(memberships) == 1
        membership = memberships[0]
        assert 'group' in membership
        assert 'type' in membership
        assert 'status' in membership
#        assert len(membership) == 3
        group = membership['group']
        assert 'invitation_token' not in group

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

    def test_invitation_token(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_membership_data.side_effect = KeyError
        res = self.testapp.post_json('/adhocgroups/{}/invitation'.format(groupid1),
                                     {'invitation_token':
                                      group1_invitation}, status=200,
                                     headers=headers)
        assert res.json == json_normalize({
            'groupid': groupid1,
            'status': 'normal',
            'type': 'member',
        })

    def test_wrong_invitation_token(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_membership_data.side_effect = KeyError
        self.testapp.post_json('/adhocgroups/{}/invitation'.format(groupid1),
                               {'invitation_token': 'foo'},
                               status=409, headers=headers)

    def test_invitation_token_member(self):
        headers = {'Authorization': 'Bearer user_token'}
        group = deepcopy(group1)
        self.session().get_group.return_value = group
        self.session().get_membership_data.return_value = {
            'groupid': groupid1,
            'userid': user1,
            'type': 'member',
            'status': 'unconfirmed',
        }
        self.testapp.post_json('/adhocgroups/{}/invitation'.format(groupid1),
                               {'invitation_token': 'foo'},
                               status=409, headers=headers)

    def test_get_adhocgroup_logo(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group_logo.return_value = (b'mylittlelogo', now())
        for ver in ['', '/v1']:
            path = '/adhocgroups{}/{}/logo'.format(ver, groupid1)
            res = self.testapp.get(path, status=200, headers=headers)
            assert res.content_type == 'image/png'
            out = res.body
            assert b'mylittlelogo' in out

    def test_post_adhocgroup_logo_body(self):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session().get_group.return_value = deepcopy(group1)
        self.session().save_logo = mock.MagicMock()
        for ver in ['', '/v1']:
            with open('data/default-client.png', 'rb') as fh:
                path = '/adhocgroups/{}/logo'.format(groupid1)
                logo = fh.read()
                res = self.testapp.post(path, logo, status=200, headers=headers)
                out = res.json
                assert out == 'OK'
