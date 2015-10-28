import unittest
import mock
from pytest import raises
from coreapis.utils import translatable
from coreapis.groups.ldap_backend import org_membership_name, LDAPBackend
from coreapis.groups.tests import test_gogroups


class TestOrgMembershipName(unittest.TestCase):
    def test_he_faculty(self):
        assert org_membership_name(['member', 'employee', 'faculty'],
                                   ['higher_education']) == \
            translatable(dict(nb='Akademisk ansatt'))

    def test_go_student(self):
        assert org_membership_name(['student', 'member'],
                                   ['upper_secondary']) == \
            translatable(dict(nb='Elev'))

    def test_no_match(self):
        assert org_membership_name(['ugle'], ['foo']) == 'ugle'


class TestLDAPBackend(unittest.TestCase):
    @mock.patch('coreapis.groups.ldap_backend.LDAPController')
    @mock.patch('coreapis.groups.ldap_backend.cassandra_client.Client')
    def setUp(self, session, ldap):
        self.backend = LDAPBackend('org', 100, {})
        self.session = session()
        self.ldap = ldap()

    def test_handle_gogroup(self):
        with raises(KeyError):
            self.backend._handle_gogroup('example.org', test_gogroups.GROUP1, False)
        result = self.backend._handle_gogroup('example.org', test_gogroups.GROUP1, True)
        assert 'grep' not in result
        assert 'parent' in result
        assert result['parent'].startswith(self.backend.prefix)
        assert 'id' in result
        assert 'example.org' in result['id']

    def test_handle_gogroup_grep(self):
        self.session.get_grep_code_by_code.return_value = {'title': {'default': 'grep stuff'}}
        result = self.backend._handle_gogroup('example.org', test_gogroups.GROUP2, True)
        assert 'grep' in result
        assert result['grep'] == {'displayName': 'grep stuff',
                                  'code': 'REA3012'}

    def test_handle_go_groups(self):
        entitlements = [
            test_gogroups.GROUP1,
            'ugle',
        ]
        result = self.backend._handle_go_groups('example.org', entitlements, True)
        assert len(result) == 1
        assert 'id' in result[0]

    def test_find_group_for_groupid(self):
        entitlements = [
            test_gogroups.GROUP2,
            'ugle',
            test_gogroups.GROUP1,
            test_gogroups.GROUPID1,
        ]
        group = self.backend._find_group_for_groupid(test_gogroups.GROUPID1, entitlements)
        assert group
        assert group.groupid_entitlement() == test_gogroups.GROUPID1

    def test_get_go_members(self):
        self.ldap.get_base_dn.return_value = 'dc=example,dc=org'
        self.ldap.search.return_value = [
            {
                'attributes': {
                    'displayName': ['Member 1'],
                    'eduPersonEntitlement': [
                        test_gogroups.GROUP1,
                        test_gogroups.GROUPID1,
                    ],
                }
            },
            {
                'attributes': {
                    'displayName': ['Member 2'],
                    'eduPersonEntitlement': [
                        test_gogroups.GROUP1,
                        test_gogroups.GROUPID1,
                    ],
                }
            },
        ]
        result = self.backend.get_go_members(None, 'fc:org:example.org:b:NO975278964:6A:2014-08-01:2015-06-15', True, False)
        assert result == [
            {
                'membership': {
                    'affiliation': 'student',
                    'basic': 'member',
                    'displayName': {'nb': 'Elev'}
                },
                'name': 'Member 1'
            },
            {
                'membership': {
                    'affiliation': 'student',
                    'basic': 'member',
                    'displayName': {'nb': 'Elev'}
                },
                'name': 'Member 2'
            }
        ]

    def test_get_go_members_ids(self):
        self.ldap.get_base_dn.return_value = 'dc=example,dc=org'
        self.ldap.search.return_value = [
            {
                'attributes': {
                    'displayName': ['Member 1'],
                    'eduPersonPrincipalName': ['m1@example.org'],
                    'eduPersonEntitlement': [
                        test_gogroups.GROUP1,
                        test_gogroups.GROUPID1,
                    ],
                }
            },
            {
                'attributes': {
                    'displayName': ['Member 2'],
                    'eduPersonPrincipalName': ['m2@example.org'],
                    'eduPersonEntitlement': [
                        test_gogroups.GROUP1,
                        test_gogroups.GROUPID1,
                    ],
                }
            },
        ]
        result = self.backend.get_go_members(None, 'fc:org:example.org:b:NO975278964:6A:2014-08-01:2015-06-15', True, True)
        assert result == [
            {
                'membership': {
                    'affiliation': 'student',
                    'basic': 'member',
                    'displayName': {'nb': 'Elev'}
                },
                'userid_sec': ['feide:m1@example.org'],
                'name': 'Member 1'
            },
            {
                'membership': {
                    'affiliation': 'student',
                    'basic': 'member',
                    'displayName': {'nb': 'Elev'}
                },
                'userid_sec': ['feide:m2@example.org'],
                'name': 'Member 2'
            }
        ]
