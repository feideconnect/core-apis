import unittest
import mock
from pytest import raises
from coreapis.utils import translatable
from coreapis.groups.ldap_backend import go_membership, org_membership_name


class TestGOMembership(unittest.TestCase):
    def test_student(self):
        assert go_membership('student') == {
            'displayName': translatable({'nb': 'Elev'}),
            'basic': 'member',
            'affiliation': 'student'
        }

    def test_teacher(self):
        assert go_membership('faculty') == {
            'displayName': translatable({'nb': 'Lærer'}),
            'basic': 'admin',
            'affiliation': 'faculty'
        }

    def test_unknown(self):
        assert go_membership('ugle') == {
            'displayName': 'ugle',
            'basic': 'member',
            'affiliation': 'ugle'
        }


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
