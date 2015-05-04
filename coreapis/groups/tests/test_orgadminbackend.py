import unittest
import mock
from pytest import raises
from coreapis.utils import translatable
from coreapis.groups.orgadmin_backend import OrgAdminBackend

FEIDEID_OWN = 'foo@bar'
FEIDEID_OTHER = 'this@that'
ORGTAG1 = 'org1'
ORGNAME1 = 'Test org1'
ORGTAG2 = 'org2'


def make_user(feideid):
    return {
        'userid_sec': ['feide:{}'.format(feideid)]
    }


def make_orgid(orgtag):
    return 'fc:org:{}'.format(orgtag)


def make_role(feideid, orgid, role):
    return {
        'feideid': feideid,
        'orgid': orgid,
        'role': role
    }


def make_org(orgtag, name):
    res = {
        'id': make_orgid(orgtag),
    }
    if name:
        res['name'] = translatable(name)
        res['type'] = set('foo')
    return res

ROLES = [
    make_role(FEIDEID_OWN, make_orgid(ORGTAG1), set(['admin'])),
    make_role(FEIDEID_OWN, make_orgid(ORGTAG2), set(['mercantile'])),
    make_role(FEIDEID_OWN, 'garbage', set(['mercantile']))
]

ORGS = [make_org(ORGTAG1, {'nb': ORGNAME1}), make_org(ORGTAG2, None)]


def mock_get_roles(selectors, values, maxrows):
    if selectors == ['feideid = ?'] and len(values) == 1:
        keyname = 'feideid'
    elif selectors == ['orgid = ?'] and len(values) == 1:
        keyname = 'orgid'
    else:
        raise RuntimeError('No mock handles this case')
    res = [role for role in ROLES if role[keyname] == values[0]]
    print('selectors={}, values={}, res={}'.format(selectors, values, res))
    return res


def mock_get_org(orgid):
    res = [org for org in ORGS if org['id'] == orgid][0]
    print('orgid={}, res={}'.format(orgid, res))
    return res


class TestOrgAdminBackend(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.backend = OrgAdminBackend('orgadmin', 100, mock.Mock())

    def _get_member_groups(self, feideid):
        self.session.get_roles.side_effect = mock_get_roles
        self.session.get_org.side_effect = mock_get_org
        return self.backend.get_member_groups(make_user(feideid), False)

    def test_get_member_groups(self):
        res = self._get_member_groups(FEIDEID_OWN)
        assert len([mship for mship in res if 'admin' == mship['membership']['basic']]) == 1
        assert len([mship for mship in res if 'member' == mship['membership']['basic']]) == 1

    def test_get_member_groups_no_memberships(self):
        res = self._get_member_groups(FEIDEID_OTHER)
        assert len(res) == 0

    def _get_members(self, feideid, groupid):
        self.session.get_roles.side_effect = mock_get_roles
        return self.backend.get_members(make_user(feideid), groupid, False)

    def test_get_members(self):
        res = self._get_members(FEIDEID_OWN, 'fc:orgadmin:{}'.format(ORGTAG1))
        print(res)
        assert len(res) == 1

    def test_get_members_not_member(self):
        with raises(KeyError) as ex:
            res = self._get_members(FEIDEID_OTHER, 'fc:orgadmin:{}'.format(ORGTAG1))
            print(res)
        assert 'Not member of group' in str(ex)

    def test_get_members_bad_orgtype(self):
        with raises(KeyError) as ex:
            res = self._get_members(FEIDEID_OWN, 'fc:org:{}'.format(ORGTAG1))
            print(res)
        assert 'Not an orgadmin group' in str(ex)

    def test_grouptypes(self):
        res = self.backend.grouptypes()
        assert 'administrator' in res[0]['displayName']['nb']
