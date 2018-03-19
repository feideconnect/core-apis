import unittest
from pytest import raises
import mock
from coreapis.groups.platformadmin_backend import PlatformAdminBackend


FEIDEID_OWN = 'foo@bar'
FEIDEID_OTHER = 'this@that'
PLATFORMADMIN_GROUPID = 'fc:platformadmin:admins'


def make_user(feideid):
    return {
        'userid_sec': ['feide:' + str(feideid)]
    }


class TestPlatformAdminBackend(unittest.TestCase):
    @mock.patch('coreapis.groups.platformadmin_backend.get_platform_admins')
    def setUp(self, get_platform_admins):
        get_platform_admins.return_value = [FEIDEID_OWN]
        self.backend = PlatformAdminBackend('orgadmin', 100, mock.Mock())

    def _get_member_groups(self, feideid):
        return self.backend.get_member_groups(make_user(feideid), False)

    def test_get_member_groups_as_admin(self):
        res = self._get_member_groups(FEIDEID_OWN)
        assert len(res) == 1
        assert 'admin' in str(res)

    def test_get_member_groups_not_admin(self):
        res = self._get_member_groups(FEIDEID_OTHER)
        assert not res

    def _get_members(self, feideid, groupid):
        return self.backend.get_members(make_user(feideid), groupid, False, True)

    def test_get_members_as_admin(self):
        res = self._get_members(FEIDEID_OWN, PLATFORMADMIN_GROUPID)
        assert len(res) == 1
        assert 'admin' in str(res)

    def test_get_members_not_admin(self):
        with raises(KeyError) as ex:
            self._get_members(FEIDEID_OTHER, PLATFORMADMIN_GROUPID)
        assert 'Not member of group' in str(ex)

    def test_get_members_not_my_grouptype(self):
        with raises(KeyError) as ex:
            self._get_members(FEIDEID_OWN, 'fc:org:foo')
        assert 'Not platformadmin group' in str(ex)

    def _get_group(self, feideid, groupid):
        return self.backend.get_group(make_user(feideid), groupid)

    def test_get_group_as_admin(self):
        res = self._get_group(FEIDEID_OWN, PLATFORMADMIN_GROUPID)
        assert res['id'] == PLATFORMADMIN_GROUPID

    def test_get_group_not_admin(self):
        with raises(KeyError) as ex:
            self._get_group(FEIDEID_OTHER, PLATFORMADMIN_GROUPID)
        assert 'Not member of group' in str(ex)

    def test_get_group_not_my_grouptype(self):
        with raises(KeyError) as ex:
            self._get_group(FEIDEID_OWN, 'fc:org:foo')
        assert 'Not platformadmin group' in str(ex)

    def _get_groups(self, feideid, query):
        return self.backend.get_groups(make_user(feideid), query)

    def test_get_groups_as_admin(self):
        res = self._get_groups(FEIDEID_OWN, None)
        assert 'admin' in str(res)

    def test_get_groups_not_admin(self):
        with raises(KeyError) as ex:
            self._get_groups(FEIDEID_OTHER, None)
        assert 'Not member of group' in str(ex)

    def test_get_groups_with_query(self):
        with raises(KeyError) as ex:
            self._get_groups(FEIDEID_OWN, 'platform')
        assert 'Querying not supported' in str(ex)

    def test_grouptypes(self):
        res = self.backend.grouptypes()
        assert 'Plattformadministrator' in res[0]['displayName']['nb']
