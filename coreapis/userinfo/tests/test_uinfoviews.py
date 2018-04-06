import unittest
from unittest import mock
import datetime
import webtest
from pyramid import testing
from coreapis import main, middleware


class UinfoViewTests(unittest.TestCase):
    @mock.patch('coreapis.ldap.controller.LDAPController')
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client, ldap):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'dataporten.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused'
        }, enabled_components='userinfo', ldap_controller=ldap)
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.ldap = ldap
        self.testapp = webtest.TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_userinfo(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.ldap.lookup_feideid.return_value = {}
        self.testapp.get('/userinfo/v1/userinfo', status=200, headers=headers)

    def test_get_userinfo_user_not_found(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.ldap.lookup_feideid.side_effect = KeyError
        self.testapp.get('/userinfo/v1/userinfo', status=404, headers=headers)

    def test_get_profilephoto(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_user_profilephoto.return_value = (
            b'foo', datetime.datetime.now())
        userid_sec = 'p:foo'
        self.testapp.get('/userinfo/v1/user/media/{}'.format(userid_sec),
                         status=200, headers=headers)

    def test_get_profilephoto_user_not_found(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_user_profilephoto.side_effect = KeyError
        userid_sec = 'p:foo'
        self.testapp.get('/userinfo/v1/user/media/{}'.format(userid_sec),
                         status=404, headers=headers)

    def test_get_profilephoto_bad_sec_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        userid_sec = 'q:foo'
        self.testapp.get('/userinfo/v1/user/media/{}'.format(userid_sec),
                         status=404, headers=headers)
