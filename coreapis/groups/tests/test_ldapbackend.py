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
            translatable(dict(nb='Akademisk ansatt',
                              nn='Akademisk tilsett'))

    def test_go_student(self):
        assert org_membership_name(['student', 'member'],
                                   ['upper_secondary']) == \
            translatable(dict(nb='Elev'))

    def test_no_match(self):
        assert org_membership_name(['ugle'], ['foo']) == 'ugle'


class TestLDAPBackend(unittest.TestCase):
    @mock.patch('coreapis.groups.ldap_backend.ldapcontroller')
    @mock.patch('coreapis.groups.ldap_backend.cassandra_client.Client')
    def setUp(self, session, ldap):
        self.backend = LDAPBackend('org', 100, {})
        self.session = session()
        self.ldap = ldap.LDAPController()

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
        result = self.backend.get_go_members(
            None,
            'fc:org:example.org:b:NO975278964:6a:2014-08-01:2015-06-15',
            True, False)
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
        result = self.backend.get_go_members(
            None,
            'fc:org:example.org:b:NO975278964:6a:2014-08-01:2015-06-15',
            True, True)
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

    def test_get_org_he(self):
        self.ldap.search.return_value = [{
            'attributes': {
                'eduOrgLegalName': ['testOrg'],
            },
        }]
        self.session.get_org_by_realm.return_value = {
            'type': {'higher_education', 'service_provider'},
        }
        result = self.backend._get_org('example.org', 'dc=example,dc=org', {})
        assert result == {
            'displayName': 'testOrg',
            'orgType': ['higher_education'],
            'type': 'fc:org',
            'public': True,
            'id': 'org:example.org',
            'eduOrgLegalName': 'testOrg',
            'membership': {'basic': 'member'}
        }

    def test_get_org_go(self):
        self.ldap.search.return_value = [{
            'attributes': {
                'eduOrgLegalName': ['testOrg'],
            },
        }]
        self.session.get_org_by_realm.return_value = {
            'type': {'primary_and_lower_secondary', 'service_provider'},
        }
        result = self.backend._get_org('example.org', 'dc=example,dc=org', {})
        assert result == {
            'displayName': 'testOrg',
            'orgType': ['primary_and_lower_secondary_owner'],
            'type': 'fc:org',
            'public': True,
            'id': 'org:example.org',
            'eduOrgLegalName': 'testOrg',
            'membership': {'basic': 'member'}
        }

    def test_get_org_not_found(self):
        self.ldap.search.return_value = []
        with raises(KeyError):
            self.backend._get_org('example.org', 'dc=example,dc=org', {})

    def test_get_orgunit_he(self):
        self.ldap.search.return_value = [{
            'attributes': {
                'ou': ['testOrgUnit'],
                'norEduOrgUnitUniqueIdentifier': ['AVD-Q10'],
            },
        }]
        self.session.get_org_by_realm.return_value = {
            'type': {'higher_education', 'service_provider'},
        }
        result = self.backend._get_orgunit('example.org', 'dc=example,dc=org', 'dc=example,dc=org')
        assert result == {
            'displayName': 'testOrgUnit',
            'type': 'fc:orgunit',
            'public': True,
            'id': 'org:example.org:unit:AVD-Q10',
            'membership': {
                'basic': 'member',
                'primaryOrgUnit': True,
            },
            'parent': 'org:example.org',
        }

    def test_get_orgunit_go(self):
        self.ldap.search.return_value = [{
            'attributes': {
                'ou': ['testSchool'],
                'norEduOrgUnitUniqueIdentifier': ['NO123456789'],
            },
        }]
        self.session.get_org_by_realm.return_value = {
            'type': {'primary_and_lower_secondary', 'service_provider'},
        }
        result = self.backend._get_orgunit('example.org', 'dc=example,dc=org', None)
        assert result == {
            'displayName': 'testSchool',
            'orgType': ['primary_and_lower_secondary'],
            'type': 'fc:org',
            'public': True,
            'id': 'org:example.org:unit:NO123456789',
            'membership': {
                'basic': 'member',
                'primarySchool': False,
            },
            'parent': 'org:example.org',
        }

    def test_get_orgunit_not_found(self):
        self.ldap.search.return_value = []
        with raises(KeyError):
            self.backend._get_orgunit('example.org', 'dc=example,dc=org', None)
