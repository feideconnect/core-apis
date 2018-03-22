import unittest
import datetime
import pytz
from pytest import raises
from coreapis.utils import translatable, now
from coreapis.groups.gogroups import GOGroup

GROUP1 = "urn:mace:feide.no:go:group:b::NO975278964:6A:2014-08-01:2015-06-15:student:Klasse%206A"
GROUP2 = ("urn:mace:feide.no:go:group:u:" +
          "REA3012:NO974558386:3kja:2014-08-01:2015-06-15:faculty:Kjemi%202A")
GROUPID1 = 'urn:mace:feide.no:go:groupid:b:NO975278964:6a:2014-08-01:2015-06-15'
GROUPID1_NONCANONICAL = 'urn:mace:feide.no:go:groupid:b:NO975278964:6A:2014-08-01:2015-06-15'


# pylint: disable=protected-access
class TestGOGroups(unittest.TestCase):
    def test_parse_gogroup(self):
        group = GOGroup(GROUP1)
        assert group.group_type == 'b'
        assert group.grep_code == ''
        assert group.organization == 'NO975278964'
        assert group._group_id == '6a'
        assert group.valid_from == datetime.datetime(2014, 8, 1, tzinfo=pytz.UTC)
        assert group.valid_to == datetime.datetime(2015, 6, 15, tzinfo=pytz.UTC)
        assert group.role == 'student'
        assert group.name == 'Klasse 6A'

        group = GOGroup(GROUP2)
        assert group.group_type == 'u'
        assert group.grep_code == 'REA3012'
        assert group.organization == 'NO974558386'
        assert group._group_id == '3kja'
        assert group.valid_from == datetime.datetime(2014, 8, 1, tzinfo=pytz.UTC)
        assert group.valid_to == datetime.datetime(2015, 6, 15, tzinfo=pytz.UTC)
        assert group.role == 'faculty'
        assert group.name == 'Kjemi 2A'
        with raises(KeyError):
            GOGroup("urn:mace:uninett.no:go:group:u:" +
                    "REA3012:NO974558386:3kja:2014-08-01:2015-06-15:faculty:Kjemi%202A")
        with raises(KeyError):
            GOGroup("urn:mace:feide.no:go:group:u:" +
                    "NO974558386:3kja:2014-08-01:2015-06-15:faculty:Kjemi%202A")

    def test_parse_gogroup_noncanonical(self):
        group = GOGroup(GROUP1, canonicalize=False)
        assert group.group_type == 'b'
        assert group.grep_code == ''
        assert group.organization == 'NO975278964'
        assert group._group_id == '6A'
        assert group.valid_from == datetime.datetime(2014, 8, 1, tzinfo=pytz.UTC)
        assert group.valid_to == datetime.datetime(2015, 6, 15, tzinfo=pytz.UTC)
        assert group.role == 'student'
        assert group.name == 'Klasse 6A'

        group = GOGroup(GROUP2, canonicalize=False)
        assert group.group_type == 'u'
        assert group.grep_code == 'REA3012'
        assert group.organization == 'NO974558386'
        assert group._group_id == '3kja'
        assert group.valid_from == datetime.datetime(2014, 8, 1, tzinfo=pytz.UTC)
        assert group.valid_to == datetime.datetime(2015, 6, 15, tzinfo=pytz.UTC)
        assert group.role == 'faculty'
        assert group.name == 'Kjemi 2A'

    def test_membership(self):
        group = GOGroup(GROUP1)
        assert group.membership() == {
            'displayName': translatable({'nb': 'Elev'}),
            'basic': 'member',
            'affiliation': 'student'
        }

        group = GOGroup(GROUP2)
        assert group.membership() == {
            'displayName': translatable(dict(nb='Lærer',
                                             nn='Lærar')),
            'basic': 'admin',
            'affiliation': 'faculty'
        }

        group.role = 'ugle'
        assert group.membership() == {
            'displayName': 'ugle',
            'basic': 'member',
            'affiliation': 'ugle'
        }

    def test_candidate(self):
        assert GOGroup.candidate(GROUP1)
        assert not GOGroup.candidate('ugle')

    def test_groupid_entitlement(self):
        group = GOGroup(GROUP1)
        assert group.groupid_entitlement() == GROUPID1

    def test_groupid_entitlement_noncanonical(self):
        group = GOGroup(GROUP1, canonicalize=False)
        assert group.groupid_entitlement() == GROUPID1_NONCANONICAL

    def test_groupid(self):
        group = GOGroup(GROUP1)
        assert (group.group_id('fc:org', 'uninett.no') ==
                'fc:org:uninett.no:b:NO975278964:6a:2014-08-01:2015-06-15')

    def test_groupid_noncanonical(self):
        group = GOGroup(GROUP1, canonicalize=False)
        assert (group.group_id('fc:org', 'uninett.no') ==
                'fc:org:uninett.no:b:NO975278964:6A:2014-08-01:2015-06-15')

    def test_valid(self):
        group = GOGroup(GROUP1)
        assert not group.valid()
        group.valid_to = now() + datetime.timedelta(days=2)
        assert group.valid()
        group.valid_from = now() + datetime.timedelta(days=1)

    def test_format_group(self):
        group = GOGroup(GROUP1)
        assert group.format_group('gogroup', 'example.org', 'fc:parent') == {
            'displayName': 'Klasse 6A',
            'go_type': 'b',
            'go_type_displayName': translatable({'nb': 'basisgruppe'}),
            'id': 'gogroup:example.org:b:NO975278964:6a:2014-08-01:2015-06-15',
            'membership': {
                'affiliation': 'student',
                'basic': 'member',
                'displayName': translatable({'nb': 'Elev'}),
            },
            'notAfter': datetime.datetime(2015, 6, 15, tzinfo=pytz.UTC),
            'notBefore': datetime.datetime(2014, 8, 1, tzinfo=pytz.UTC),
            'parent': 'fc:parent:example.org:unit:NO975278964',
            'type': 'fc:gogroup',
        }
