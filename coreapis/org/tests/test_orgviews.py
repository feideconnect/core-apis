import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import json_normalize, now

testorg_id = 'fc:org:example.com'
testorg = {
    'id': testorg_id,
    'organization_number': 'NO00000001',
    'type': ['service_provider'],
    'realm': 'example.com',
    'name': {'nb': 'testorganisasjon',
             'en': 'test organization', },
}
testorg2_id = 'fc:org:example.org'
testorg2 = {
    'id': testorg2_id,
    'organization_number': 'NO00000002',
    'type': ['service_provider'],
    'realm': 'example.org',
    'name': {'nb': 'testorganisasjon 2',
             'en': 'test organization 2', },
}


class OrgViewTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='org', clientadm_maxrows=100)
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_org(self):
        self.session.get_org.return_value = testorg
        res = self.testapp.get('/orgs/{}'.format(testorg), status=200)
        out = res.json
        assert out['realm'] == 'example.com'

    def test_get_org_not_found(self):
        self.session.get_org.side_effect = KeyError
        self.testapp.get('/orgs/{}'.format(testorg), status=404)

    def test_list_orgs(self):
        self.session.list_orgs.return_value = [testorg, testorg2]
        res = self.testapp.get('/orgs/', status=200)
        out = res.json
        assert len(out) == 2
        assert out[0]['id'] == testorg_id
        assert out[1]['id'] == testorg2_id

    def test_get_org_logo_default(self):
        self.session.get_org_logo.return_value = (None, None)
        res = self.testapp.get('/orgs/{}/logo'.format(testorg), status=200)
        out = res.body
        assert b'PNG' == out[1:4]

    def test_get_org_logo(self):
        self.session.get_org_logo.return_value = (b"A logo", now())
        res = self.testapp.get('/orgs/{}/logo'.format(testorg), status=200)
        out = res.body
        assert out == b"A logo"

    def test_get_org_logo_no_org(self):
        self.session.get_org_logo.side_effect = KeyError
        self.testapp.get('/orgs/{}/logo'.format(testorg), status=404)

    
