from unittest import TestCase
from copy import deepcopy
import mock
import uuid
from aniso8601 import parse_datetime

from coreapis.clientadm import controller
from coreapis.clientadm.tests.helper import (
    userid_own, clientid, testgk, othergk, post_body_minimal, retrieved_gk_client, testscope,
    retrieved_user, date_created, mock_get_apigk, mock_get_clients_by_scope,
    mock_get_clients_by_scope_requested, baduris)


class TestController(TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.session.get_apigk.side_effect = mock_get_apigk
        settings = {
            'cassandra_contact_points': [],
            'cassandra_keyspace': 'keyspace',
            'clientadm_scopedefs_file': 'scopedefs.json.example',
            'clientadm_maxrows': 100
        }
        self.controller = controller.ClientAdmController(settings)

    def test_is_valid_uri(self):
        res = [controller.is_valid_uri(uri) for uri in baduris]
        assert True not in res

    def test_has_permission(self):
        assert self.controller.has_permission(retrieved_gk_client, None) is False
        other_user = deepcopy(retrieved_user)
        other_user['userid'] = uuid.uuid4()
        assert self.controller.has_permission(retrieved_gk_client, other_user) is False
        assert self.controller.has_permission(retrieved_gk_client, retrieved_user) is True
        client = deepcopy(retrieved_gk_client)
        client['organization'] = 'test:org'
        is_platform_admin = mock.MagicMock()
        self.controller.is_platform_admin = is_platform_admin
        is_platform_admin.return_value = False
        is_org_admin = mock.MagicMock()
        self.controller.is_org_admin = is_org_admin
        is_org_admin.return_value = False
        assert self.controller.has_permission(client, retrieved_user) is False
        is_org_admin.return_value = True
        assert self.controller.has_permission(client, retrieved_user) is True
        is_platform_admin.return_value = True
        is_org_admin.return_value = False
        assert self.controller.has_permission(client, retrieved_user) is True

    def test_add_with_owner(self):
        testuid = uuid.UUID(userid_own)
        post_body = deepcopy(post_body_minimal)
        post_body['owner'] = userid_own
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock()
        res = self.controller.add(post_body, testuid)
        assert res['owner'] == testuid

    def test_add_with_malformed_scopedefs(self):
        testuid = uuid.UUID(userid_own)
        post_body = deepcopy(post_body_minimal)
        self.controller.scopedefs = {testscope: {}}
        self.session.get_client_by_id.side_effect = KeyError
        self.session.insert_client = mock.MagicMock()
        res = self.controller.add(post_body, testuid)
        assert res['scopes'] == []

    def test_add_with_only_subscope(self):
        testuid = uuid.UUID(userid_own)
        post_body = deepcopy(post_body_minimal)
        post_body['scopes_requested'] = ['gk_foo_bar']
        res = self.controller.add(post_body, testuid)
        assert 'gk_foo_bar' not in res['scopes_requested']

    def test_update_with_ts(self):
        id = clientid
        self.session.get_client_by_id.return_value = deepcopy(retrieved_gk_client)
        self.session.insert_client = mock.MagicMock()
        attrs = {'created': '2000-01-01T00:00:00+01:00'}
        res = self.controller.update(id, attrs)
        assert res['created'] == parse_datetime(date_created)

    def test_get_gkscope_clients(self):
        self.session.get_clients_by_scope.return_value = []
        self.session.get_clients_by_scope_requested.return_value = [retrieved_gk_client]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testgk, 'gk_bar'])
        assert testgk in res[0]['scopes_requested']

    def test_get_gkscope_clients_no_match(self):
        self.session.get_clients_by_scope.return_value = []
        self.session.get_clients_by_scope_requested.return_value = []
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testgk, 'gk_bar'])
        assert res == []

    def test_get_gkscope_clients_no_scopes(self):
        self.session.get_clients_by_scope.return_value = []
        self.session.get_clients_by_scope_requested.return_value = [retrieved_gk_client]
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([])
        assert res == []

    def test_get_gkscope_clients_testgk(self):
        self.session.get_clients_by_scope.side_effect = mock_get_clients_by_scope
        self.session.get_clients_by_scope_requested.side_effect \
            = mock_get_clients_by_scope_requested
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testgk])
        assert testgk in res[0]['scopes'] or testgk in res[0]['scopes_requested']

    def test_get_gkscope_clients_othergk(self):
        self.session.get_clients_by_scope.side_effect = mock_get_clients_by_scope
        self.session.get_clients_by_scope_requested.side_effect \
            = mock_get_clients_by_scope_requested
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([othergk])
        assert othergk in res[0]['scopes'] or othergk in res[0]['scopes_requested']

    def test_get_gkscope_clients_bothscopes(self):
        self.session.get_clients_by_scope.side_effect = mock_get_clients_by_scope
        self.session.get_clients_by_scope_requested.side_effect \
            = mock_get_clients_by_scope_requested
        self.session.get_user_by_id.return_value = retrieved_user
        res = self.controller.get_gkscope_clients([testgk, othergk])
        assert len(res) == 3
