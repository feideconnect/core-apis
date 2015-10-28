import unittest
from copy import deepcopy
import py.test
import mock
from coreapis.groups.adhoc_backend import query_match, format_membership, AdHocGroupBackend
from coreapis.adhocgroupadm.tests.data import \
    user1, user2, user3, \
    groupid1, group1, \
    groupid2, group2, \
    public_userinfo


group1_view = {
    "id": 'adhoc:' + str(groupid1),
    "displayName": "pre update",
    "description": "some data",
    "type": "voot:ad-hoc",
    "membership": {
        "basic": "member",
    }
}

group2_view = {
    "id": 'adhoc:' + str(groupid2),
    "displayName": "pre update",
    "description": "some data",
    "type": "voot:ad-hoc",
    "public": True,
    "membership": {
        "basic": "admin",
    }
}

groups = {
    groupid1: group1,
    groupid2: group2
}

membership1 = {
    'groupid': groupid1,
    'userid': user1,
    'status': 'normal',
    'type': 'normal',
}


class TestQueryMatch(unittest.TestCase):
    def test_no_query(self):
        assert query_match(None, {})

    def test_match_displayName(self):
        assert query_match('foo', {'displayName': 'a foo group'})

    def test_match_description(self):
        assert query_match('foo', {'displayName': 'test group', 'description': 'a foo group'})

    def test_no_description(self):
        assert not query_match('foo', {'displayName': 'test group'})

    def test_no_match(self):
        assert not query_match('foo', {'displayName': 'no match', 'description': 'no match'})


class TestFormatMembership(unittest.TestCase):
    def test_owner_admin(self):
        assert format_membership(group1, {'userid': user1, 'type': 'admin'}) == {'basic': 'owner'}

    def test_owner_member(self):
        assert format_membership(group1, {'userid': user1, 'type': 'admin'}) == {'basic': 'owner'}

    def test_member(self):
        assert format_membership(group1, {'userid': user2, 'type': 'member'}) == {'basic': 'member'}

    def test_admin(self):
        assert format_membership(group1, {'userid': user2, 'type': 'admin'}) == {'basic': 'admin'}


class TestAdHocBackendBase(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.backend = AdHocGroupBackend('adhoc', 100, mock.Mock())


class TestAdHocBackend(TestAdHocBackendBase):
    def test_get_member_groups(self):
        self.session.get_group_memberships.return_value = [
            {
                'groupid': groupid1,
                'status': 'normal',
                'type': 'member',
                'userid': user3
            },
            {
                'groupid': groupid2,
                'status': 'normal',
                'type': 'admin',
                'userid': user3
            },
        ]
        self.session.get_group.side_effect = groups.get
        res = self.backend.get_member_groups(dict(userid=user3), False)
        assert res == [group1_view, group2_view]


class TestAdHocBackendGet(TestAdHocBackendBase):
    def test_normal(self):
        self.session.get_group.return_value = group1
        self.session.get_membership_data.return_value = membership1
        assert self.backend._get(user1, 'fc:adhoc:{}'.format(groupid1)) == (group1, membership1)

    def test_not_member(self):
        group = deepcopy(group1)
        self.session.get_group.return_value = group
        self.session.get_membership_data.side_effect = KeyError
        with py.test.raises(KeyError):
            self.backend._get(user2, 'fc:adhoc:{}'.format(groupid1))

    def test_not_member_but_owner(self):
        group = deepcopy(group1)
        self.session.get_group.return_value = group
        self.session.get_membership_data.side_effect = KeyError
        assert self.backend._get(user1, 'fc:adhoc:{}'.format(groupid1)) == (group1, None)

    def test_not_member_but_public(self):
        group = deepcopy(group1)
        group['public'] = True
        self.session.get_group.return_value = group
        self.session.get_membership_data.side_effect = KeyError
        self.backend._get(user2, 'fc:adhoc:{}'.format(groupid1)) == (group1, None)


class TestAdHocBackendGetMembership(TestAdHocBackendBase):
    def test_normal(self):
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, membership1
            assert self.backend.get_membership({'userid': user1}, 'fc:adhoc:{}'.format(groupid1)) == {'basic': 'owner'}

    def test_not_member(self):
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, None
            with py.test.raises(KeyError):
                self.backend.get_membership({'userid': user1}, 'fc:adhoc:{}'.format(groupid1))


class TestAdHocBackendGetGroup(TestAdHocBackendBase):
    def test_normal(self):
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, None
            res = self.backend.get_group({'userid': user1}, 'fc:adhoc:{}'.format(groupid1))
            expected = deepcopy(group1_view)
            del expected['membership']
            assert res == expected


class TestAdHocBackendGetMembers(TestAdHocBackendBase):
    def test_normal(self):
        members = [{'userid': user1, 'type': 'member', 'status': 'normal'}]
        self.session.get_group_members.return_value = members
        self.session.get_user_by_id.return_value = public_userinfo
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, membership1
            res = self.backend.get_members({'userid': user1}, 'fc:adhoc:{}'.format(groupid1), False, False)
            assert res == [{'membership': {'basic': 'owner'}, 'name': 'foo'}]

    def test_bad_member(self):
        members = [{'userid': user1, 'type': 'member', 'status': 'normal'}]
        self.session.get_group_members.return_value = members
        self.session.get_user_by_id.side_effect = KeyError
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, membership1
            res = self.backend.get_members({'userid': user1}, 'fc:adhoc:{}'.format(groupid1), False, False)
            assert res == []

    def test_bad_status(self):
        members = [{'userid': user1, 'type': 'member', 'status': 'hacked'}]
        self.session.get_group_members.return_value = members
        self.session.get_user_by_id.return_value = public_userinfo
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, membership1
            res = self.backend.get_members({'userid': user1}, 'fc:adhoc:{}'.format(groupid1), False, False)
            assert res == []

    def test_not_member(self):
        members = []
        self.session.get_group_members.return_value = members
        self.session.get_user_by_id.return_value = public_userinfo
        with mock.patch('coreapis.groups.adhoc_backend.AdHocGroupBackend._get') as _get:
            _get.return_value = group1, None
            with py.test.raises(KeyError):
                self.backend.get_members({'userid': user1}, 'fc:adhoc:{}'.format(groupid1), False, False)
