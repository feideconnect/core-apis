from copy import deepcopy
import json
import unittest
import uuid

import webtest
from pyramid import testing

import mock
from coreapis import main, middleware

testrealm = 'ipadi.no'
testuser = 'pelle'
testprincipalname = '{}@{}'.format(testuser, testrealm)
testuserid = '00000000-0000-0000-0000-000000000001'
clientid = '00000000-0000-0000-0000-000000000004'
incomplete_ldap_person = {'eduPersonPrincipalName': testprincipalname}
ldap_person = incomplete_ldap_person.copy()
ldap_person.update({'mail': testprincipalname, 'displayName': testuser})
retrieved_user = {
    'userid_sec': ['p:foo', 'feide:' + testprincipalname],
    'selectedsource': 'us',
    'name': {'us': 'foo'},
    'userid': uuid.UUID(testuserid),
    'email': {'us': testprincipalname},
}
retrieved_client = {
    'id': uuid.UUID(clientid),
}

def make_test_orgauthz(subscopes):
    return {'ipadi.no': json.dumps(["gk_orgpersons_" + ssc for ssc in subscopes])}

subscopes_all = ['systemlookup', 'systemsearch', 'usersearchglobal', 'usersearchlocal']
retrieved_client['orgauthorization'] = make_test_orgauthz(subscopes_all)

class OrgViewTests(unittest.TestCase):
    @mock.patch('coreapis.orgpersons.views.LDAPController')
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client, ldap):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'dataporten.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='orgpersons', ldap_config_file='testdata/test-ldap-config.json')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.ldap = ldap()
        self.testapp = webtest.TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def _test_get_orgperson(self, userid_sec, headers, status):
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        return self.testapp.get('/orgpersons/users/{}'.format(userid_sec),
                                status=status, headers=headers)

    def test_get_orgperson_no_hdr_clientid(self):
        headers = {'Authorization': 'Bearer client_token'}
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 400)

    def test_get_orgperson_bad_clientid(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': 'xyzzy'}
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 400)

    def test_get_orgperson_social(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self._test_get_orgperson('linkbook:12345', headers, 500)

    def test_get_orgperson_incomplete_ldap_person(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.lookup_feideid.return_value = incomplete_ldap_person
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 500)

    def test_get_orgperson_never_loggedin(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.lookup_feideid.return_value = ldap_person
        self.session.get_userid_by_userid_sec.side_effect = KeyError
        self.session.get_user_by_id.return_value = retrieved_user
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 200)

    def test_get_orgperson_not_in_ldap(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.lookup_feideid.side_effect = KeyError
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 404)

    def test_get_orgperson_for_user(self):
        headers = {'Authorization': 'Bearer user_token', 'x-dataporten-clientid': clientid,
                   'x-dataporten-userid-sec': 'feide:' + testprincipalname}
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 403)

    def test_get_orgperson_no_orgauthz(self):
        client = deepcopy(retrieved_client)
        client['orgauthorization'] = {}
        self.session.get_client_by_id.return_value = client
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        return self.testapp.get('/orgpersons/users/{}'.format('feide:{}'.format(testprincipalname)),
                                status=403, headers=headers)

    def test_get_orgperson(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.lookup_feideid.return_value = ldap_person
        self.session.get_userid_by_userid_sec.return_value = testuserid
        self.session.get_user_by_id.return_value = retrieved_user
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 200)

    def test_get_orgperson_no_photo(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        user = deepcopy(retrieved_user)
        user['userid_sec'] = ['feide:' + testprincipalname]
        self.ldap.lookup_feideid.return_value = ldap_person
        self.session.get_userid_by_userid_sec.return_value = testuserid
        self.session.get_user_by_id.return_value = user
        self._test_get_orgperson('feide:{}'.format(testprincipalname) , headers, 200)

    def _test_get_orgpersons(self, query, headers, subscopes, status):
        orgauthz = {'ipadi.no': json.dumps(["gk_orgpersons_" + ssc for ssc in subscopes])}
        client = deepcopy(retrieved_client)
        client['orgauthorization'] = orgauthz
        self.session.get_client_by_id.return_value = client
        return self.testapp.get('/orgpersons/orgs/{}/users/?q={}'.format(testrealm, query),
                                status=status, headers=headers)

    def test_get_orgpersons_incomplete_ldap_person(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.ldap_search.return_value = [{'attributes': incomplete_ldap_person}]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self._test_get_orgpersons(testuser, headers, subscopes_all, 200)
        assert len(res.json) == 0

    def test_get_orgpersons(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.ldap_search.return_value = [{'attributes': ldap_person}]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self._test_get_orgpersons(testuser, headers, subscopes_all, 200)
        assert len(res.json) == 1

    def test_get_orgpersons_email(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self.ldap.ldap_search.return_value = [{'attributes': ldap_person}]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self._test_get_orgpersons(testprincipalname, headers, subscopes_all, 200)
        assert len(res.json) == 1

    def test_get_orgpersons_for_user_no_privs(self):
        headers = {'Authorization': 'Bearer user_token', 'x-dataporten-clientid': clientid,
                   'x-dataporten-userid-sec': 'feide:' + testprincipalname}
        self._test_get_orgpersons(testuser, headers, [], 403)

    def test_get_orgpersons_for_user_usersearchlocal_own_realm(self):
         headers = {'Authorization': 'Bearer user_token', 'x-dataporten-clientid': clientid,
                   'x-dataporten-userid-sec': 'feide:' + testprincipalname}
         self._test_get_orgpersons(testuser, headers, ['usersearchlocal'], 200)

    def test_get_orgpersons_for_user_usersearchlocal_foreign_realm(self):
        headers = {'Authorization': 'Bearer user_token', 'x-dataporten-clientid': clientid,
                   'x-dataporten-userid-sec': 'feide:ab@cde.no'}
        self._test_get_orgpersons(testuser, headers, ['usersearchlocal'], 403)

    def test_get_orgpersons_for_user_usersearchglobal(self):
        headers = {'Authorization': 'Bearer user_token', 'x-dataporten-clientid': clientid,
                   'x-dataporten-userid-sec': 'feide:' + testprincipalname}
        self._test_get_orgpersons(testuser, headers, ['usersearchglobal'], 200)

    def test_get_orgpersons_for_system_no_privs(self):
        headers = {'Authorization': 'Bearer client_token', 'x-dataporten-clientid': clientid}
        self._test_get_orgpersons(testuser, headers, [], 403)
