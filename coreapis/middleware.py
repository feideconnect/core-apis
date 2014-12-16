import uuid
from . import cassandra_client
from .utils import LogWrapper, Timer


def mock_main(app, config):
    return MockAuthMiddleware(app)


def cassandra_main(app, config, contact_points, keyspace):
    contact_points = contact_points.split(', ')
    timer = Timer(config['statsd_server'], int(config['statsd_port']),
                  config['statsd_prefix'])
    return CassandraMiddleware(app, contact_points,
                               keyspace, timer)


class AuthMiddleware(object):
    def __init__(self, app):
        self._app = app
        self.log = LogWrapper('feideconnect.auth')

    def __call__(self, environ, start_response):
        token = self.get_token(environ)
        if token:
            try:
                user, client, scopes = self.lookup_token(token)
                self.log.debug('successfully looked up token', user=user, client=client, scopes=scopes)
                environ["FC_USER"] = user
                environ["FC_CLIENT"] = client
                environ["FC_SCOPES"] = scopes
            except KeyError:
                self.log.debug('failed to find token', token=token)
                pass  # Invalid token passed. Perhaps return 402?
        else:
            self.log.debug('unhandled authorization scheme')
        return self._app(environ, start_response)

    def get_token(self, environ):
        authorization = environ.get('HTTP_AUTHORIZATION')
        if authorization and authorization.startswith('Bearer '):
            token = authorization.split(' ', 1)[1]
            return token
        return None

    def lookup_token(self, token):
        raise KeyError("Not implemented")


class MockAuthMiddleware(AuthMiddleware):
    tokens = {
        'user': {
            'user': {
                "name": {"feide:example.com": "Dummy User"},
                "created": "2014-12-16T09:15:57",
                "userid": "00000000-0000-0000-0000-000000000001",
                "selectedsource": "feide:example.com",
                "userid_sec_seen": {},
                "userid_sec": [],
                "email": {"feide:example.com": "dummy@example.com"}
            },

            'client': {
                "status": ["production"],
                "scopes": ["userinfo"],
                "updated": None,
                "name": "Dummy Client",
                "descr": "Dummy Client for dummy testing",
                "created": "2014-12-15T12:26:07",
                "redirect_uri": ["https://sp.example.org/callback"],
                "scopes_requested": [],
                "owner": "00000000-0000-0000-0000-000000000001",
                "client_secret": "00000000-0000-0000-0000-000000000003",
                "type": "client",
                "id": "00000000-0000-0000-0000-000000000002"
            },

            'scopes': ['api_ecampusrelay'],
        },
        'client': {
            'client': {
                "status": ["production"],
                "scopes": ["userinfo"],
                "updated": None,
                "name": "Dummy Client",
                "descr": "Dummy Client for dummy testing",
                "created": "2014-12-15T12:26:07",
                "redirect_uri": ["https://sp.example.org/callback"],
                "scopes_requested": [],
                "owner": "00000000-0000-0000-0000-000000000001",
                "client_secret": "00000000-0000-0000-0000-000000000003",
                "type": "client",
                "id": "00000000-0000-0000-0000-000000000002"
            },

            'scopes': ['userinfo', 'longterm'],
        },
    }

    def lookup_token(self, token):
        if token in self.tokens:
            data = self.tokens[token]
            return data.get('user', None), data['client'], data['scopes']
        else:
            raise KeyError('Token not found')


class CassandraMiddleware(AuthMiddleware):
    def __init__(self, app, contact_points, keyspace, timer):
        super(CassandraMiddleware, self).__init__(app)
        self.timer = timer
        self.session = cassandra_client.create_session(contact_points, keyspace)

    def lookup_token(self, token_string):
        token_uuid = uuid.UUID(token_string)
        with self.timer.time('auth.lookup_token'):
            token = cassandra_client.get_token(self.session, token_uuid)
            if 'clientid' not in token:
                self.log.warn('token misses required column "client"', token=token_string)
                raise KeyError('Invalid token')
            if 'scope' not in token:
                self.log.warn('token misses required column "scope"', token=token_string)
                raise KeyError('Invalid token')
            client = cassandra_client.get_client_by_id(self.session, token['clientid'])
            if 'userid' in token:
                user = cassandra_client.get_user_by_id(self.session, token['userid'])
            else:
                user = None
        return user, client, token['scope']
