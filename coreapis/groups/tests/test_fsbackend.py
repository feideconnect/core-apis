import unittest
from copy import deepcopy
from pytest import raises
import mock
from coreapis.utils import translatable
from coreapis.groups.fs_backend import FsBackend

ORGTAG1 = 'org1'
ORGNAME1 = 'Test org1'
ORGTAG2 = 'org2'
USERIDS = [
    '00000000-0000-0000-0000-000000000001',
    '00000000-0000-0000-0000-000000000002',
    '00000000-0000-0000-0000-000000000003'
]


def make_user(userid, identity):
    return {
        'userid': userid,
        'userid_sec': [identity]
    }


def make_orgid(orgtag):
    return 'fc:org:{}'.format(orgtag)


def make_org(orgtag, name):
    res = {
        'id': make_orgid(orgtag),
    }
    if name:
        res['name'] = translatable(name)
        res['type'] = set('foo')
    return res


ORGS = [make_org(ORGTAG1, {'nb': ORGNAME1}), make_org(ORGTAG2, None)]
USERS = [
    make_user(USERIDS[0], 'feide:per@bar.no'),
    make_user(USERIDS[1], 'feide:kari@bar.no'),
    make_user(USERIDS[2], 'facebook:3141592653589793')
]
MEMBERS = [{
    'userid': user['userid_sec'][0],
    'name': 'foo',
} for user in USERS[:-1]]
MEMBERS[0]['membership'] = {'active': True}
MEMBER_GROUPS = [
    {'id': 'foo'},
    {'id': 'per',
     'membership': {}},
    {'id': 'fc:baz',
     'membership': {'active': False},
     'parent': 'fc:sdfsdf'},
    {'id': 'fc:buzz',
     'membership': {'active': True}},
    {'id': 'fc:fizz',
     'displayName': {'nb': 'Hei'},
     'membership': {'active': True,
                    'notAfter': '2019-01-26T16:05:59Z'},
     'parent': ORGS[0]['id']},
    {'id': 'fc:buzz',
     'membership': {'active': True,
                    'displayName': {'nb': 'Hei'},
                    'notBefore': '2016-01-26T16:05:59Z'},
     'parent': 'foo'}
]


def mock_get_org(orgid):
    return [org for org in ORGS if org['id'] == orgid][0]


class MockResponse(object):
    def __init__(self, response_data):
        self.response_data = deepcopy(response_data)
        self.status_code = 200
        self.headers = {
            'content-type': 'application/json'
        }

    def raise_for_status(self):
        pass

    def json(self):
        return self.response_data


class TestFsBackend(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        settings = {'timer': mock.MagicMock()}
        self.session = Client()
        self.backend = FsBackend('fs', 100, settings)

    def _get_member_groups(self, user, show_all):
        with mock.patch('coreapis.groups.fs_backend.requests.get',
                        return_value=MockResponse(MEMBER_GROUPS)):
            self.session.get_org.side_effect = mock_get_org
            return self.backend.get_member_groups(user, show_all)

    def test_get_member_groups(self):
        res = self._get_member_groups(USERS[0], False)
        assert len(res) == 3

    def test_get_member_groups_show_all(self):
        res = self._get_member_groups(USERS[0], True)
        assert len(res) == 4

    def test_get_member_groups_social(self):
        res = self._get_member_groups(USERS[2], False)
        assert not res

    def test_get_member_groups_org_not_enabled(self):
        self.session.org_use_fs_groups.return_value = False
        res = self._get_member_groups(USERS[0], False)
        assert not res

    def _get_members(self, user, groupid):
        with mock.patch('coreapis.groups.fs_backend.requests.get',
                        return_value=MockResponse(MEMBERS)):
            return self.backend.get_members(user, groupid, False, True)

    def test_get_members(self):
        res = self._get_members(USERS[0], 'fc:kull:foo:bar')
        assert len(res) == 2

    def test_get_members_org_not_enabled(self):
        self.session.org_use_fs_groups.return_value = False
        with raises(KeyError) as ex:
            self._get_members(USERS[0], 'fc:kull:foo:bar')
        assert 'not enabled' in str(ex)

    def test_get_members_not_member(self):
        with raises(KeyError) as ex:
            self._get_members(USERS[2], 'fc:kull:foo:bar')
        assert 'not member' in str(ex)

    def test_get_members_bad_grouptype(self):
        with raises(KeyError) as ex:
            self._get_members(USERS[0], 'fc:foo:bar')
        assert 'invalid group id' in str(ex)

    def test_get_members_no_info(self):
        resp_data = [{'userid': USERS[0]['userid_sec'][0]}]
        with mock.patch('coreapis.groups.fs_backend.requests.get',
                        return_value=MockResponse(resp_data)):
            res = self.backend.get_members(USERS[0], 'fc:kull:foo:bar', False, True)
            assert not res

    def test_grouptypes(self):
        res = self.backend.grouptypes()
        assert 'Emne' in [gtype['displayName']['nb'] for gtype in res]
