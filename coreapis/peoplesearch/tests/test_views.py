import unittest
import mock
from webtest import TestApp
from coreapis import main, middleware


class PeoplesearchViewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        with mock.patch('coreapis.peoplesearch.controller.CassandraCache'):
            app = main({
                'statsd_server': 'localhost',
                'statsd_port': '8125',
                'statsd_prefix': 'feideconnect.tests',
                'oauth_realm': 'test realm',
                'cassandra_contact_points': '',
                'cassandra_keyspace': 'notused',
            }, enabled_components='peoplesearch',
                profile_token_secret='AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=')
            mw = middleware.MockAuthMiddleware(app, 'test realm')
            self.session = Client()
            self.testapp = TestApp(mw)

    def test_search_no_user(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.get('/peoplesearch/search/feide.no/jk',
                         status=403, headers=headers)

    def test_search_max_replies(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/peoplesearch/search/feide.no/jk?max_replies=1',
                         status=200, headers=headers)

    def test_search_bad_max_replies(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/peoplesearch/search/feide.no/jk?max_replies=one',
                         status=400, headers=headers)

    def test_search_invalid_org(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/peoplesearch/search/vg.no/jk',
                         status=404, headers=headers)

    def test_list_realms(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.get('/peoplesearch/orgs',
                         status=200, headers=headers)
