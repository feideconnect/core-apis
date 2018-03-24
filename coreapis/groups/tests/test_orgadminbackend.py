import unittest
from unittest import mock
from pytest import raises
from coreapis.utils import translatable
from coreapis.groups.orgadmin_backend import OrgAdminBackend

ID_FEIDE_OWN = 'feide:foo@bar'
ID_FEIDE_OTHER = 'feide:this@that'
ID_SOCIAL = 'facebook:3141592653589793'
ORGTAG1 = 'org1'
ORGNAME1 = 'Test org1'
ORGTAG2 = 'org2'


def make_user(identity):
    return {
        'userid_sec': [identity]
    }


def make_orgid(orgtag):
    return 'fc:org:{}'.format(orgtag)


def make_role(identity, orgid, role):
    return {
        'identity': identity,
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
    make_role(ID_FEIDE_OWN, make_orgid(ORGTAG1), set(['admin'])),
    make_role(ID_FEIDE_OWN, make_orgid(ORGTAG2), set(['mercantile'])),
    make_role(ID_FEIDE_OWN, 'garbage', set(['mercantile'])),
    make_role(ID_SOCIAL, make_orgid(ORGTAG2), set(['admin'])),
]

ORGS = [make_org(ORGTAG1, {'nb': ORGNAME1}), make_org(ORGTAG2, None)]


def mock_get_roles(selectors, values, maxrows):
    if selectors == ['identity = ?'] and len(values) == 1:
        keyname = 'identity'
    elif selectors == ['orgid = ?'] and len(values) == 1:
        keyname = 'orgid'
    else:
        raise RuntimeError('No mock handles this case')
    return (role for role in ROLES if role[keyname] == values[0])


def mock_get_org(orgid):
    return [org for org in ORGS if org['id'] == orgid][0]


class TestOrgAdminBackend(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.backend = OrgAdminBackend('orgadmin', 100, mock.Mock())

    def _get_member_groups(self, identity):
        self.session.get_roles.side_effect = mock_get_roles
        self.session.get_org.side_effect = mock_get_org
        return self.backend.get_member_groups(make_user(identity), False)

    def test_get_member_groups(self):
        res = self._get_member_groups(ID_FEIDE_OWN)
        assert len([mship for mship in res if mship['membership']['basic'] == 'admin']) == 1
        assert len([mship for mship in res if mship['membership']['basic'] == 'member']) == 1

    def test_get_member_groups_no_memberships(self):
        res = self._get_member_groups(ID_FEIDE_OTHER)
        assert not res

    def test_get_member_groups_social(self):
        res = self._get_member_groups(ID_SOCIAL)
        assert len([mship for mship in res if mship['membership']['basic'] == 'admin']) == 1
        assert not [mship for mship in res if mship['membership']['basic'] == 'member']

    def _get_members(self, identity, groupid):
        self.session.get_roles.side_effect = mock_get_roles
        return self.backend.get_members(make_user(identity), groupid, False, True)

    def test_get_members(self):
        res = self._get_members(ID_FEIDE_OWN, 'fc:orgadmin:{}'.format(ORGTAG1))
        assert len(res) == 1

    def test_get_members_not_member(self):
        with raises(KeyError) as ex:
            self._get_members(ID_FEIDE_OTHER, 'fc:orgadmin:{}'.format(ORGTAG1))
        assert 'Not member of group' in str(ex)

    def test_get_members_bad_orgtype(self):
        with raises(KeyError) as ex:
            self._get_members(ID_FEIDE_OWN, 'fc:org:{}'.format(ORGTAG1))
        assert 'Not an orgadmin group' in str(ex)

    def test_grouptypes(self):
        res = self.backend.grouptypes()
        assert 'administrator' in res[0]['displayName']['nb']
