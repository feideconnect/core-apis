import unittest
import mock
import uuid
from coreapis.groups.adhoc_backend import *
from coreapis.utils import parse_datetime

user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
user2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
user3 = uuid.UUID("00000000-0000-0000-0000-000000000003")
groupid1 = uuid.UUID("00000000-0000-0000-0001-000000000001")
groupid2 = uuid.UUID("00000000-0000-0000-0001-000000000002")
group1_invitation = '62649b1d-353a-4588-8483-6f4a31863c78'
group2_invitation = '62649b1d-353a-4588-8483-6f4a31863c79'
group1 = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid1,
    "owner": user1,
    "name": "pre update",
    "descr": "some data",
    "public": False,
    'invitation_token': group1_invitation,
}
public_userinfo = {
    'userid_sec': ['p:foo'],
    'selectedsource': 'us',
    'name': {'us': 'foo'},
}
public_userinfo_view = {
    'id': 'p:foo',
    'name': 'foo',
}
group1_view = {
    "id": 'adhoc:' + str(groupid1),
    "displayName": "pre update",
    "description": "some data",
    "type": "voot:ad-hoc",
    "membership": {
        "basic": "member",
    }
}

group2 = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid2,
    "owner": user2,
    "name": "pre update",
    "descr": "some data",
    "public": True,
    'invitation_token': group2_invitation,
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


class TestAdHocBackend(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.backend = AdHocGroupBackend('adhoc', 100, mock.Mock())

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
