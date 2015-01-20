import unittest
import mock
import uuid
import dateutil.parser
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware

post_body_minimal = {
    'name': 'per', 'scopes': [], 'redirect_uri': [], 'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493'
}

post_body_maximal = {
    'name': 'per', 'scopes': ['clientadmin'], 'redirect_uri': [],
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493', 'id': 'f3f043db-9fd6-4c5a-b0bc-61992bea9eca',
    'client_secret': 'sekrit', 'created': '2015-01-12 14:05:16+0100', 'descr': 'green',
    'scopes_requested': [], 'status': ['lab'], 'type': 'client',
    'updated': '2015-01-12 14:05:16+0100'
}

retrieved_client = {
    'name': 'per', 'scopes': ['clientadmin'], 'redirect_uri': [],
    'owner': uuid.UUID('4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493'), 
    'id': uuid.UUID('f3f043db-9fd6-4c5a-b0bc-61992bea9eca'),
    'client_secret': 'sekrit', 'created': dateutil.parser.parse('2015-01-12 14:05:16+0100'), 
    'descr': 'green',
    'scopes_requested': [], 'status': ['lab'], 'type': 'client',
    'updated': dateutil.parser.parse('2015-01-12 14:05:16+0100')
}

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
        }, enabled_components='clientadm', clientadm_maxrows=100)
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

    def test_post_client_minimal(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().insert_client = mock.MagicMock() 
        res = self.testapp.post_json('/clientadm/clients/', post_body_minimal, status=201, headers=headers)
        out = res.json
        assert '4f4e' in out['owner']

    def test_post_client_maximal(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().insert_client = mock.MagicMock() 
        self.session().get_client_by_id.side_effect = KeyError()
        res = self.testapp.post_json('/clientadm/clients/', post_body_maximal, status=201, headers=headers)
        out = res.json
        assert '4f4e' in out['owner']

    def test_post_client_duplicate(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().insert_client = mock.MagicMock() 
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        self.testapp.post_json('/clientadm/clients/', post_body_maximal, status=409, headers=headers)

    def test_post_client_missing_name(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_json(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = 'foo'
        self.testapp.post('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_uuid(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['owner'] = 'owner'
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_ts(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['created'] = 42
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text_list(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_list(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_unknown_attr(self):
        headers = {'Authorization': 'Bearer client_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_delete_client(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.delete('/clientadm/clients/{}'.format(uuid.uuid4()), status=204, headers=headers)

    def test_delete_client_no_id(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.delete('/clientadm/clients/', status=404, headers=headers)

    def test_delete_client_malformed_id(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.delete('/clientadm/clients/{}'.format('foo'), status=400, headers=headers)

    def test_update_client(self):
        headers = {'Authorization': 'Bearer client_token'}
        id = post_body_maximal['id']
        self.session().get_client_by_id.return_value = retrieved_client
        self.session().insert_client = mock.MagicMock()
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(id), {'descr': 'blue'}, status=200, headers=headers)
        out = res.json
        assert out['descr'] == 'blue'

    def test_update_client_no_id(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.patch_json('/clientadm/clients/', {'descr': 'blue'}, status=404, headers=headers)

    def test_update_client_malformed_id(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.patch_json('/clientadm/clients/{}'.format('foo'), {'descr': 'blue'}, status=400, headers=headers)

    def test_update_client_invalid_json(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.testapp.patch('/clientadm/clients/{}'.format('foo'), 'bar', status=400, headers=headers)

    def test_update_missing_client(self):
        headers = {'Authorization': 'Bearer client_token'}
        id = post_body_maximal['id']
        self.session().get_client_by_id.side_effect = KeyError()
        self.session().insert_client = mock.MagicMock()
        self.testapp.patch_json('/clientadm/clients/{}'.format(id), {'descr': 'blue'}, status=404, headers=headers)

    def test_update_client_invalid_ts(self):
        headers = {'Authorization': 'Bearer client_token'}
        id = post_body_maximal['id']
        self.session().get_client_by_id.return_value = retrieved_client
        self.session().insert_client = mock.MagicMock()
        self.testapp.patch_json('/clientadm/clients/{}'.format(id), {'created': 'blue'}, status=400, headers=headers)
