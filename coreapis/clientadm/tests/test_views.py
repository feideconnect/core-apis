import unittest
import mock
import uuid
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware


class ClientAdmTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
            'clientadm_maxrows': 100,
        }, enabled_components='clientadm')
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_client(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_client_by_id.return_value = {'foo': 'bar'}
        res = self.testapp.get('/clientadm/clients/{}'.format(uuid.uuid4()), status=200, headers=headers)
        out = res.json
        assert 'foo' in out

    def test_missing_client(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_client_by_id.side_effect = KeyError()
        self.testapp.get('/clientadm/clients/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_clients(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_scope(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/?scope=userlist', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_owner(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/?owner={}'.format(uuid.uuid4()), status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_bad_client_filter(self):
        headers = {'Authorization': 'Bearer client_token'}
        res = self.testapp.get('/clientadm/clients/?scope=', status=400, headers=headers)
        out = res.json
        assert out['message'] == 'missing filter value' 
