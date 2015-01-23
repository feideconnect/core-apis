from unittest import TestCase
from copy import deepcopy
import mock
import uuid
from aniso8601 import parse_datetime

from coreapis.clientadm import controller
from coreapis.clientadm.tests.helper import (
    userid_own, clientid, post_body_minimal, retrieved_client, date_created)

# A few branches that aren't exercised from the view tests
# This is functionality that regular users are not authorized to use

class TestController(TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.session = Client()
        self.controller = controller.ClientAdmController([], 'keyspace', 100)

    def test_add_with_owner(self):
        testuid = uuid.UUID(userid_own)
        post_body = deepcopy(post_body_minimal)
        post_body['owner'] = userid_own
        self.session.insert_client = mock.MagicMock() 
        res = self.controller.add_client(post_body, testuid)
        assert res['owner'] == testuid

    def test_update_with_ts(self):
        id = clientid
        self.session.get_client_by_id.return_value = deepcopy(retrieved_client)
        self.session.insert_client = mock.MagicMock() 
        attrs = {'created': '2000-01-01T00:00:00+01:00'}
        res = self.controller.update_client(id, attrs)
        assert res['created'] == parse_datetime(date_created)
