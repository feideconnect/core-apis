import datetime
import os
import time
from unittest import mock
from pytest import mark
from pytz import UTC
from coreapis.groups.ldap_backend import LDAPBackend
from coreapis.tests.test_cassandra import setUpModule as setupCassandra

SETTINGS = {}


def setUpModule():
    global SETTINGS  # pylint: disable=global-statement
    cclient = setupCassandra()
    cclient.insert_org({
        'id': 'foo:org:example.org',
        'realm': 'example.org',
        'organization_number': '987654321',
        'type': {'upper_secondary'},
        'name': {'nb': 'example organization'},
        'fs_groups': None,
        'services': None,
        'uiinfo': None
    })
#    if 'TEST_LDAP_CREDS' not in os.environ:
#        raise unittest.SkipTest('No ldap credentials available')
    SETTINGS['timer'] = mock.MagicMock()
    SETTINGS['cassandra_contact_points'] = [os.environ.get('DP_CASSANDRA_TEST_NODE',
                                                           'cassandra-test-coreapis')]
    SETTINGS['cassandra_keyspace'] = os.environ.get('DP_CASSANDRA_TEST_KEYSPACE', 'test_coreapis')
    SETTINGS['cassandra_authz'] = None
    SETTINGS['statsd_factory'] = mock.Mock()
    SETTINGS['statsd_host_factory'] = mock.Mock()
    SETTINGS['ldap_config_file'] = os.path.join(os.path.dirname(__file__), 'ldap-config.json')
    SETTINGS['ldap_ca_certs'] = '/etc/ldap_certs.crt'


# pylint: disable=protected-access
@mark.eventlet
class TestLDAPIntegration(object):
    def setup(self):
        self.backend = LDAPBackend(  # pylint: disable=attribute-defined-outside-init
            'foo', 1000, SETTINGS)

    def test_get_member_groups(self):
        assert self.backend._get_member_groups(True, 'asbjorn_elevg@example.org') == [
            {
                'displayName': 'Osp kommune',
                'eduOrgLegalName': 'Osp kommune',
                'id': 'foo:example.org',
                'mail': 'support@feide.no',
                'type': 'fc:org',
                'norEduOrgNIN': 'NO856326502',
                'orgType': ['upper_secondary_owner'],
                'public': True,
                'membership': {
                    'basic': 'member',
                    'affiliation': ['student', 'member'],
                    'primaryAffiliation': 'student'
                }
            },
            {
                'displayName': 'Grøn barneskole',
                'id': 'foo:example.org:unit:NO856326499',
                'membership': {
                    'basic': 'member',
                    'primarySchool': True
                },
                'orgType': ['upper_secondary'],
                'parent': 'foo:example.org',
                'public': True,
                'type': 'fc:org',
            },
            {
                'displayName': 'Klasse 10A',
                'go_type': 'b',
                'go_type_displayName': {'nb': 'basisgruppe'},
                'id': 'fc:gogroup:example.org:b:NO856326499:10a:2016-01-01:2019-06-20',
                'membership': {'affiliation': 'student',
                               'basic': 'member',
                               'displayName': {'nb': 'Elev'}},
                'notAfter': datetime.datetime(2019, 6, 20, 0, 0, tzinfo=UTC),
                'notBefore': datetime.datetime(2016, 1, 1, 0, 0, tzinfo=UTC),
                'parent': 'foo:example.org:unit:NO856326499',
                'type': 'fc:gogroup'
            },
            {
                'displayName': 'Laboratoriegruppe 1',
                'go_type': 'a',
                'go_type_displayName': {'en': 'other groups', 'nb': 'andre grupper'},
                'id': 'fc:gogroup:example.org:a:NO856326499:10a-lab1:2016-01-01:2019-06-20',
                'membership': {'affiliation': 'student',
                               'basic': 'member',
                               'displayName': {'nb': 'Elev'}},
                'notAfter': datetime.datetime(2019, 6, 20, 0, 0, tzinfo=UTC),
                'notBefore': datetime.datetime(2016, 1, 1, 0, 0, tzinfo=UTC),
                'parent': 'foo:example.org:unit:NO856326499',
                'type': 'fc:gogroup'
            }
        ]

    @mock.patch.dict('coreapis.groups.ldap_backend.GROUPID_CANONICALIZATION_MIGRATION_TIME',
                     {'example.org': time.time() + 1000})
    def test_get_member_groups_noncanonical(self):
        assert self.backend._get_member_groups(True, 'asbjorn_elevg@example.org') == [
            {
                'displayName': 'Osp kommune',
                'eduOrgLegalName': 'Osp kommune',
                'id': 'foo:example.org',
                'mail': 'support@feide.no',
                'type': 'fc:org',
                'norEduOrgNIN': 'NO856326502',
                'orgType': ['upper_secondary_owner'],
                'public': True,
                'membership': {
                    'basic': 'member',
                    'affiliation': ['student', 'member'],
                    'primaryAffiliation': 'student'
                }
            },
            {
                'displayName': 'Grøn barneskole',
                'id': 'foo:example.org:unit:NO856326499',
                'membership': {
                    'basic': 'member',
                    'primarySchool': True
                },
                'orgType': ['upper_secondary'],
                'parent': 'foo:example.org',
                'public': True,
                'type': 'fc:org',
            },
            {
                'displayName': 'Klasse 10A',
                'go_type': 'b',
                'go_type_displayName': {'nb': 'basisgruppe'},
                'id': 'fc:gogroup:example.org:b:NO856326499:10A:2016-01-01:2019-06-20',
                'membership': {'affiliation': 'student',
                               'basic': 'member',
                               'displayName': {'nb': 'Elev'}},
                'notAfter': datetime.datetime(2019, 6, 20, 0, 0, tzinfo=UTC),
                'notBefore': datetime.datetime(2016, 1, 1, 0, 0, tzinfo=UTC),
                'parent': 'foo:example.org:unit:NO856326499',
                'type': 'fc:gogroup'
            },
            {
                'displayName': 'Laboratoriegruppe 1',
                'go_type': 'a',
                'go_type_displayName': {'en': 'other groups', 'nb': 'andre grupper'},
                'id': 'fc:gogroup:example.org:a:NO856326499:10A-LAB1:2016-01-01:2019-06-20',
                'membership': {'affiliation': 'student',
                               'basic': 'member',
                               'displayName': {'nb': 'Elev'}},
                'notAfter': datetime.datetime(2019, 6, 20, 0, 0, tzinfo=UTC),
                'notBefore': datetime.datetime(2016, 1, 1, 0, 0, tzinfo=UTC),
                'parent': 'foo:example.org:unit:NO856326499',
                'type': 'fc:gogroup'
            }
        ]

    def test_get_go_members(self):
        assert self.backend.get_go_members(
            'asbjorn_elevg@example.org',
            'fc:gogroup:example.org:a:NO856326499:10a-lab1:2016-01-01:2019-06-20', True, True) == [
                {
                    'name': 'Asbjørn ElevG Hansen',
                    'userid_sec': ['feide:asbjorn_elevg@example.org'],
                    'membership': {
                        'affiliation': 'student',
                        'basic': 'member',
                        'displayName': {'nb': 'Elev'}
                    }
                }
            ]

    def test_get_go_members_uncanonical_groupid(self):
        assert self.backend.get_go_members(
            'asbjorn_elevg@example.org',
            'fc:gogroup:example.org:a:NO856326499:10a:2016-01-01:2019-06-20', True, True) == []

    @mock.patch.dict(
        'coreapis.groups.ldap_backend.GROUPID_CANONICALIZATION_MIGRATION_TIME',
        {'example.org': time.time() + 1000})
    def test_get_go_members_noncanonical(self):
        assert self.backend.get_go_members(
            'asbjorn_elevg@example.org',
            'fc:gogroup:example.org:a:NO856326499:10A:2016-01-01:2019-06-20', True, True) == []
