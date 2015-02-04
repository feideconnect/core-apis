import unittest
import mock
import uuid
import datetime
from coreapis.utils import now


class TokenValidationTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        from coreapis.middleware import CassandraMiddleware
        self.middleware = CassandraMiddleware(None, 'test realm', None, None, None, None, False)
        self.token = {
            'clientid': uuid.uuid4(),
            'userid': uuid.uuid4(),
            'access_token': uuid.uuid4(),
            'validuntil': now() + datetime.timedelta(days=5),
            'scope': ['foo'],
        }

    def tearDown(self):
        pass

    def test_token_valid(self):
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is True

    def test_expired_token(self):
        self.token['validuntil'] -= datetime.timedelta(days=10)
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False

    def test_bad_client(self):
        self.token['clientid'] = None
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False
        del self.token['clientid']
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False

    def test_bad_scope(self):
        self.token['scope'] = None
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False
        del self.token['scope']
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False

    def test_bad_validuntil(self):
        self.token['validuntil'] = None
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False
        del self.token['validuntil']
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is False

    def test_no_userid(self):
        self.token['userid'] = None
        assert self.middleware.token_is_valid(self.token, self.token['access_token']) is True
