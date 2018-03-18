import unittest
import ldap3
import mock
import uuid
from copy import deepcopy
import webtest
from pyramid import testing
from cassandra.util import SortedSet
from coreapis import main, middleware

testorg_id = 'fc:org:realm1.example.com'
testorg_realm = 'realm1.example.com'
testorg = {
    'id': testorg_id,
    'organization_number': 'NO00000001',
    'type': SortedSet(['service_provider']),
    'realm': testorg_realm,
    'name': {'nb': 'testorganisasjon',
             'en': 'test organization', },
}
testidentity = 'feide:foo@realm1.example.com'
testrole = {'orgid': testorg_id,
            'identity':  testidentity,
            'role': 'admin'}
ldap_response = [{
    'attributes': {
        'eduPersonOrgDN': 'foo',
        'eduPersonAffiliation': 'bar',
        'displayName': 'fizz',
        'eduPersonPrincipalName': 'buzz',
        'eduPersonOrgDN': 'per',
        'eduPersonOrgUnitDN': 'paal'
    }
}]


PLATFORMADMIN = 'admin@example.com'


def make_user(feideid):
    return {
        'userid_sec': ['feide:' + str(feideid)],
        'userid': uuid.uuid4(),
        'name': {
            'feide': "The Admin",
        },
        'selectedsource': 'feide',
    }


class MockExcArgs(object):
    def __init__(self):
        self.args = ['bar']


class OrgViewTests(unittest.TestCase):
    @mock.patch('coreapis.orgs.controller.get_platform_admins')
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client, gpa):
        gpa.return_value = [PLATFORMADMIN]
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'dataporten.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='orgs', clientadm_maxrows=100, ldap_config_file='testdata/test-ldap-config.json')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = webtest.TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def _test_ldap_status(self, roles, httpstat):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_roles.return_value = roles
        self.session.get_org.return_value = testorg
        return self.testapp.get('/orgs/{}/ldap_status'.format(testorg_id), status=httpstat, headers=headers)

    def test_ldap_status_not_admin(self):
        self._test_ldap_status([testrole], 403)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status(self, get_user):
        self._test_ldap_status([testrole], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_no_admins(self, get_user):
        self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_admin_no_realm(self, get_user):
        role = deepcopy(testrole)
        role['identity'] = 'feide:12345'
        self._test_ldap_status([role], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_admin_not_in_realm(self, get_user):
        role = deepcopy(testrole)
        role['identity'] = 'feide:foo@bar.com'
        self._test_ldap_status([role], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_admin_not_in_feide(self, get_user):
        role = deepcopy(testrole)
        role['identity'] = 'linkbook:12345'
        self._test_ldap_status([role], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_feideid(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        feideid = testidentity.split(':')[1]
        self.testapp.get('/orgs/{}/ldap_status?feideid={}'.format(testorg_id, feideid),
                         status=200, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_bind_user(self, get_user):
        headers = {'Authorization': 'Bearer user_token'}
        realm = 'realm2.example.org'
        orgid = 'fc:org:' + realm
        self.session.get_org.return_value = {'id': orgid, 'realm': realm}
        self.testapp.get('/orgs/' + orgid + '/ldap_status', status=200, headers=headers)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_conn_response_empty(self, get_user):
        with mock.patch('ldap3.Connection'):
            self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_comm_error(self, get_user):
        with mock.patch('ldap3.Connection',
                        side_effect=ldap3.core.exceptions.LDAPCommunicationError('foo')):
            self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_comm_error_details(self, get_user):
        details = [[1,2,MockExcArgs()]]
        with mock.patch('ldap3.Connection',
                        side_effect=ldap3.core.exceptions.LDAPCommunicationError('foo', details)):
            self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_bind_error(self, get_user):
        with mock.patch('ldap3.Connection',
                        side_effect=ldap3.core.exceptions.LDAPBindError('foo')):
            self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_bind_error_details(self, get_user):
        details = [[1,2,MockExArgs()]]
        with mock.patch('ldap3.Connection',
                        side_effect=ldap3.core.exceptions.LDAPBindError('foo', details)):
            self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_nonsense(self, get_user):
        with mock.patch('ldap3.Connection') as mock_connection:
            instance = mock_connection.return_value
            instance.response = "eferferfer"
            self._test_ldap_status([], 200)

    @mock.patch('coreapis.orgs.views.get_user', return_value=make_user(PLATFORMADMIN))
    def test_ldap_status_sensible(self, get_user):
        with mock.patch('ldap3.Connection') as mock_connection:
            instance = mock_connection.return_value
            instance.response = ldap_response
            self._test_ldap_status([], 200)
            with mock.patch('coreapis.ldap.status.check_object', return_value=[]):
                self._test_ldap_status([], 200)
            response2 = deepcopy(ldap_response)
            del(response2[0]['attributes']['displayName'])
            del(response2[0]['attributes']['eduPersonOrgDN'])
            del(response2[0]['attributes']['eduPersonOrgUnitDN'])
            instance.response = response2
            self._test_ldap_status([], 200)
