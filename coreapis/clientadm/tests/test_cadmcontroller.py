from unittest import TestCase
from copy import deepcopy
import mock
import uuid
from aniso8601 import parse_datetime

from coreapis.clientadm import controller
from coreapis.clientadm.tests.helper import (
    userid_own, clientid, testscope, otherscope, post_body_minimal, retrieved_client, retrieved_user,
    date_created, mock_get_clients_by_scope, mock_get_clients_by_scope_requested)

# A few cases that aren't exercised from the clientadm view tests

class TestController(TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.controller = controller.ClientAdmController([], 'keyspace', 100)

    def test_add_with_owner(self):
        testuid = uuid.UUID(userid_own)
        post_body = deepcopy(post_body_minimal)
        post_body['owner'] = userid_own
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock() 
        res = self.controller.add(post_body, testuid)
        assert res['owner'] == testuid

    def test_update_with_ts(self):
        id = clientid
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock() 
        attrs = {'created': '2000-01-01T00:00:00+01:00'}
        res = self.controller.update(id, attrs)
        assert res['created'] == parse_datetime(date_created)

    def test_get_gkscope_clients(self):
        self.session.get_clients_by_scope.return_value = []
        self.session.get_clients_by_scope_requested.return_value = [retrieved_client]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testscope, 'gk_bar'])
        assert testscope in res[0]['scopes_requested']

    def test_get_gkscope_clients_no_match(self):
        self.session.get_clients_by_scope.return_value = []
        self.session.get_clients_by_scope_requested.return_value = []
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testscope, 'gk_bar'])
        assert res == []

    def test_get_gkscope_clients_no_scopes(self):
        self.session.get_clients_by_scope.return_value = []
        self.session.get_clients_by_scope_requested.return_value = [retrieved_client]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([])
        assert res == []

    def test_get_gkscope_clients_testscope(self):
        self.session.get_clients_by_scope.side_effect = mock_get_clients_by_scope
        self.session.get_clients_by_scope_requested.side_effect = mock_get_clients_by_scope_requested
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testscope])
        assert testscope in res[0]['scopes'] or testscope in res[0]['scopes_requested']

    def test_get_gkscope_clients_otherscope(self):
        self.session.get_clients_by_scope.side_effect = mock_get_clients_by_scope
        self.session.get_clients_by_scope_requested.side_effect = mock_get_clients_by_scope_requested
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([otherscope])
        assert otherscope in res[0]['scopes'] or otherscope in res[0]['scopes_requested']

    def test_get_gkscope_clients_bothscopes(self):
        self.session.get_clients_by_scope.side_effect = mock_get_clients_by_scope
        self.session.get_clients_by_scope_requested.side_effect = mock_get_clients_by_scope_requested
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testscope, otherscope])
        assert len(res) == 3
