import unittest
import mock
import uuid
from aniso8601 import parse_datetime
from datetime import timedelta
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.clientadm.tests.helper import (
    userid_own, userid_other, clientid, date_created, testscope, otherscope, testuri,
    post_body_minimal, post_body_other_owner, post_body_maximal, retrieved_client,
    retrieved_user, testgk, othergk, nullscopedefgk, httptime, mock_get_apigk)


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
        }, enabled_components='clientadm', clientadm_scopedefs_file='scopedefs.json.example', clientadm_maxrows=100)
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client()
        self.session.get_apigk.side_effect = mock_get_apigk
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        res = self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=200,
                               headers=headers)
        out = res.json
        assert 'foo' in out

    def test_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError()
        self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=404,
                         headers=headers)

    def test_get_client_unauthenticated(self):
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=200)
        out = res.json
        assert out['descr'] == 'green'

    def test_get_client_missing_user(self):
        headers = {'Authorization': 'Bearer client_token'}
        self.session.get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        self.testapp.get('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=404,
                         headers=headers)

    def test_list_clients(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_scope(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/?scope=userlist', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/clientadm/clients/?owner={}'.format(uuid.UUID(userid_own)),
                               status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_clients_by_other_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_clients.return_value = [{'foo': 'bar'}]
        self.testapp.get('/clientadm/clients/?owner={}'.format(uuid.UUID(userid_other)), status=401,
                         headers=headers)

    def test_bad_client_filter(self):
        headers = {'Authorization': 'Bearer user_token'}
        res = self.testapp.get('/clientadm/clients/?scope=', status=400, headers=headers)
        out = res.json
        assert out['message'] == 'missing filter value'

    def test_post_client_minimal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock()
        res = self.testapp.post_json('/clientadm/clients/', post_body_minimal, status=201,
                                     headers=headers)
        out = res.json
        assert out['name'] == 'per'

    def test_post_client_maximal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.insert_client = mock.MagicMock()
        self.session.get_client_by_id.side_effect = KeyError()
        res = self.testapp.post_json('/clientadm/clients/', post_body_maximal, status=201,
                                     headers=headers)
        out = res.json
        assert out['owner'] == userid_own

    def test_post_client_other_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock()
        res = self.testapp.post_json('/clientadm/clients/', post_body_other_owner, status=201,
                                     headers=headers)
        out = res.json
        assert out['owner'] == userid_own

    def test_post_client_duplicate(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.insert_client = mock.MagicMock()
        self.session.get_client_by_id.return_value = {'foo': 'bar'}
        self.testapp.post_json('/clientadm/clients/', post_body_maximal, status=409,
                               headers=headers)

    def test_post_client_scope_given(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes'] = [testscope]
        self.session.insert_client = mock.MagicMock()
        res = self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)
        out = res.json
        assert out['scopes'] == []

    def test_post_client_autoscope_requested(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [otherscope]
        self.session.insert_client = mock.MagicMock()
        res = self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)
        out = res.json
        assert out['scopes'] == [otherscope]

    def test_post_client_invalid_scope_requested(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = ['nosuchthing']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_gkscope_does_not_exist(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = ['gk_nosuchthing']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_gksubscope_given(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [testgk + '_foo']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=201, headers=headers)

    def test_post_client_gksubscope_does_not_exist(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [testgk + '_bar']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_gksubscope_no_subscopedefs(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError
        body = deepcopy(post_body_minimal)
        body['scopes_requested'] = [othergk + '_bar']
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_missing_name(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = 'foo'
        self.testapp.post('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_uuid(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['id'] = 'foo'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_text_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_post_client_unknown_attr(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session.insert_client = mock.MagicMock()
        self.testapp.post_json('/clientadm/clients/', body, status=400, headers=headers)

    def test_delete_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = {'foo': 'bar', 'owner': uuid.UUID(userid_own)}
        self.testapp.delete('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=204,
                            headers=headers)

    def test_delete_client_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/clientadm/clients/', status=404, headers=headers)

    def test_delete_client_malformed_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/clientadm/clients/{}'.format('foo'), status=400, headers=headers)

    def test_delete_client_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = {'foo': 'bar',
                                                      'owner': uuid.UUID(userid_other)}
        self.testapp.delete('/clientadm/clients/{}'.format(uuid.UUID(clientid)), status=401,
                            headers=headers)

    def test_update_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock()
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(clientid), {'descr': 'blue'},
                                      status=200, headers=headers)
        out = res.json
        assert out['descr'] == 'blue'

    def test_update_client_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch_json('/clientadm/clients/', {'descr': 'blue'}, status=404,
                                headers=headers)

    def test_update_client_malformed_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch_json('/clientadm/clients/{}'.format('foo'), {'descr': 'blue'},
                                status=400, headers=headers)

    def test_update_client_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.patch('/clientadm/clients/{}'.format('foo'), 'bar', status=400,
                           headers=headers)

    def test_update_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.side_effect = KeyError()
        self.session.insert_client = mock.MagicMock()
        self.testapp.patch_json('/clientadm/clients/{}'.format(clientid), {'descr': 'blue'},
                                status=404, headers=headers)

    def test_update_client_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        self.testapp.patch_json('/clientadm/clients/{}'.format(clientid), {'descr': 'blue'},
                                status=401, headers=headers)

    def test_update_client_change_timestamp(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock()
        attrs = {'created': '2000-01-01T00:00:00+01:00'}
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(clientid),
                                      attrs, status=200, headers=headers)
        out = res.json
        assert out['created'] == date_created

    def test_update_client_change_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes'] = [testscope]
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        attrs = {'scopes': [otherscope]}
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(clientid),
                                      attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes'] == [testscope]

    def test_update_client_gkowner_changes_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [testgk]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        attrs = {'scopes': [testgk]}
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(clientid),
                                      attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes'] == [testgk]

    def test_update_client_gkscope_lacking_scopedef(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        attrs = {'scopes_requested': [nullscopedefgk]}
        res = self.testapp.patch_json('/clientadm/clients/{}'.format(clientid),
                                      attrs, status=200, headers=headers)
        out = res.json
        assert out['scopes_requested'] == [nullscopedefgk]

    def test_update_client_stranger_changes_scopes(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['scopes_requested'] = [othergk]
        client['owner'] = userid_other
        self.session.get_client_by_id.return_value = client
        self.session.insert_client = mock.MagicMock()
        attrs = {'scopes': [othergk]}
        self.testapp.patch_json('/clientadm/clients/{}'.format(clientid),
                                attrs, status=401, headers=headers)

    def test_update_client_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock()
        attrs = {'redirect_uri': testuri}
        self.testapp.patch_json('/clientadm/clients/{}'.format(clientid),
                                attrs, status=400, headers=headers)

    def test_get_client_logo(self):
        updated = parse_datetime(date_created)
        date_older = updated - timedelta(minutes=1)
        headers = {'Authorization': 'Bearer user_token', 'If-Modified-Since': httptime(date_older)}
        self.session.get_client_logo.return_value = b'mylittlelogo', updated
        res = self.testapp.get('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), status=200,
                               headers=headers)
        out = res.body
        assert b'mylittlelogo' in out

    def test_get_client_logo_null(self):
        updated = parse_datetime(date_created)
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_logo.return_value = None, updated
        res = self.testapp.get('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), status=200,
                               headers=headers)
        out = res.body
        assert b'PNG' == out[1:4]

    def test_get_client_logo_not_modified(self):
        updated = parse_datetime(date_created)
        date_newer = updated + timedelta(minutes=1)
        headers = {'Authorization': 'Bearer user_token', 'If-Modified-Since': httptime(date_newer)}
        self.session.get_client_logo.return_value = b'mylittlelogo', updated
        self.testapp.get('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), status=304,
                         headers=headers)

    def test_get_client_logo_bad_id(self):
        updated = parse_datetime(date_created)
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_logo.return_value = None, updated
        self.testapp.get('/clientadm/clients/{}/logo'.format('foo'), status=400, headers=headers)

    def test_get_client_logo_missing_client(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_logo.side_effect = KeyError()
        self.testapp.get('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), status=404,
                         headers=headers)

    def test_get_client_logo_default_logo_file_not_found(self):
        m = mock.mock_open()
        with mock.patch('coreapis.clientadm.views.open', m, create=True):
            updated = parse_datetime(date_created)
            headers = {'Authorization': 'Bearer user_token'}
            m.side_effect = FileNotFoundError()
            self.session.get_client_logo.return_value = None, updated
            self.testapp.get('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), status=500,
                             headers=headers)

    def test_post_client_logo_multipart(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.save_logo = mock.MagicMock()
        with open('data/default-client.png', 'rb') as fh:
            logo = fh.read()
            res = self.testapp.post('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), '',
                                    status=200, headers=headers,
                                    upload_files=[('logo', 'logo.png', logo)])
            out = res.json
            assert out == 'OK'

    def test_post_client_logo_body(self):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.save_logo = mock.MagicMock()
        with open('data/default-client.png', 'rb') as fh:
            logo = fh.read()
            res = self.testapp.post('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), logo,
                                    status=200, headers=headers)
            out = res.json
            assert out == 'OK'

    def test_post_client_logo_bad_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        self.session.get_client_by_id.return_value = client
        logo = b'mylittlelogo'
        self.testapp.post('/clientadm/clients/{}/logo'.format('foo'), logo, status=400,
                          headers=headers)

    def test_post_client_logo_bad_data(self):
        headers = {'Authorization': 'Bearer user_token', 'Content-Type': 'image/png'}
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        logo = b'mylittlelogo'
        self.testapp.post('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), logo,
                          status=400, headers=headers)

    def test_post_client_logo_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        client = deepcopy(retrieved_client)
        client['owner'] = uuid.UUID(userid_other)
        self.session.get_client_by_id.return_value = client
        logo = b'mylittlelogo'
        self.testapp.post('/clientadm/clients/{}/logo'.format(uuid.UUID(clientid)), logo,
                          status=401, headers=headers)

    def test_list_public_scopes(self):
        res = self.testapp.get('/clientadm/scopes/', status=200)
        assert 'userinfo' in res.json
        assert 'apigkadm' not in res.json
