import unittest
import mock
import uuid
import dateutil.parser
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware

userid_own   = '00000000-0000-0000-0000-000000000001'
userid_other = '00000000-0000-0000-0000-000000000002'
clientid     = '00000000-0000-0000-0000-000000000003'
date_created = '2015-01-12T14:05:16+01:00'
testscope    = 'clientadmin'
testuri      = 'http://example.org'

post_body_minimal = {
    'name': 'per', 'scopes_requested': [testscope], 'redirect_uri': [testuri]
}

post_body_other_owner = {
    'name': 'per', 'scopes_requested': [testscope], 'redirect_uri': [testuri], 'owner': userid_other
}

post_body_maximal = {
    'name': 'per', 'scopes': [], 'redirect_uri': [testuri],
    'owner': userid_own, 'id': clientid,
    'client_secret': 'sekrit', 'descr': 'green',
    'scopes_requested': [testscope], 'status': ['lab'], 'type': 'client'
}

retrieved_client = {
    'name': 'per', 'scopes': [testscope], 'redirect_uri': [testuri],
    'owner': uuid.UUID(userid_own),
    'id': uuid.UUID(clientid),
    'client_secret': 'sekrit', 'created': dateutil.parser.parse(date_created),
    'descr': 'green',
    'scopes_requested': [testscope], 'status': ['lab'], 'type': 'client',
    'updated': dateutil.parser.parse(date_created)
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
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        res = self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=200, headers=headers)
        out = res.json
        assert 'foo' in out

    def test_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_client_by_id.side_effect = KeyError()
        self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=404, headers=headers)

    def test_get_client_missing_user(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session().get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=401, headers=headers)

    def test_list_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/?scope=userlist', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/?owner={}'.format(uuid.UUID(userid_own)), status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_other_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_clients.return_value = [{'foo': 'bar'}]
        self.testapp.get('/clientadm/clients/?owner={}'.format(uuid.UUID(userid_other)), status=401, headers=headers)

    def test_bad_client_filter(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/clientadm/clients/?scope=', status=400, headers=headers)
        out = res.json
        assert out['message'] == 'missing filter value' 

    def test_post_client_minimal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_client = mock.MagicMock() 
        res = self.testapp.post_json('/clientadm/clients/', post_body_minimal, status=201, headers=headers)
        out = res.json
        assert out['name'] == 'per'

    def test_post_client_maximal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_client = mock.MagicMock() 
        self.session().get_client_by_id.side_effect = KeyError()
        res = self.testapp.post_json('/clientadm/clients/', post_body_maximal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == userid_own

    def test_post_client_other_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', post_body_other_owner, status=401, headers=headers)

    def test_post_client_duplicate(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().insert_client = mock.MagicMock() 
        self.session().get_client_by_id.return_value = [{'foo': 'bar'}]
        self.testapp.post_json('/clientadm/clients/', post_body_maximal, status=409, headers=headers)

    def test_post_client_missing_name(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = 'foo'
        self.testapp.post('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_uuid(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['id'] = 'foo'
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_unknown_attr(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session().insert_client = mock.MagicMock() 
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_delete_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        self.testapp.delete('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=204, headers=headers)

    def test_delete_client_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/clientadm/clients/', status=404, headers=headers)

    def test_delete_client_malformed_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/clientadm/clients/{}'.format('foo'), status=400, headers=headers)

    def test_delete_client_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_other)}
        self.testapp.delete('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=401, headers=headers)

    def test_update_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        id = clientid
        self.session().get_client_by_id.return_value = retrieved_client
        self.session().insert_client = mock.MagicMock()
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(id), {'descr': 'blue'}, status=200, headers=headers)
        out = res.json
        assert out['descr'] == 'blue'

    def test_update_client_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch_json('/clientadm/clients/', {'descr': 'blue'}, status=404, headers=headers)

    def test_update_client_malformed_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch_json('/clientadm/clients/{}'.format('foo'), {'descr': 'blue'}, status=400, headers=headers)

    def test_update_client_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch('/clientadm/clients/{}'.format('foo'), 'bar', status=400, headers=headers)

    def test_update_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        id = clientid
        self.session().get_client_by_id.side_effect = KeyError()
        self.session().insert_client = mock.MagicMock()
        self.testapp.patch_json('/clientadm/clients/{}'.format(id), {'descr': 'blue'}, status=404, headers=headers)

    def test_update_client_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        id = clientid
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        self.session().get_client_by_id.return_value = client
        self.session().insert_client = mock.MagicMock()
        self.testapp.patch_json('/clientadm/clients/{}'.format(id), {'descr': 'blue'}, status=401, headers=headers)

    def test_update_client_change_timestamp(self):
        headers = {'Authorization': 'Bearer user_token'}
        id = clientid
        self.session().get_client_by_id.return_value = retrieved_client
        self.session().insert_client = mock.MagicMock()
        attrs = {'created': '2000-01-01T00:00:00+01:00'}
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(id),
                                      attrs, status=200, headers=headers)
        out = res.json
        assert out['created'] == date_created

    def test_update_client_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        id = clientid
        self.session().get_client_by_id.return_value = retrieved_client
        self.session().insert_client = mock.MagicMock()
        attrs = {'redirect_uri': testuri}
        self.testapp.patch_json('/clientadm/clients/{}'.format(id),
                                attrs, status=400, headers=headers)
