import uuid
from . import cassandra_client
from .utils import LogWrapper


def mock_main(app, config):
    return MockAuthMiddleware(app)


def cassandra_main(app, config, contact_points, keyspace):
    contact_points = contact_points.split(', ')
    return CassandraMiddleware(app, contact_points,
                               keyspace)


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
            'user': 'someuser',
            'client': 'someclient',
            'scopes': ['api_ecampusrelay'],
        },
        'client': {
            'client': 'someotherclient',
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
    def __init__(self, app, contact_points, keyspace):
        super(CassandraMiddleware, self).__init__(app)
        self.session = cassandra_client.create_session(contact_points, keyspace)

    def lookup_token(self, token_string):
        token_uuid = uuid.UUID(token_string)
        token = cassandra_client.get_token(self.session, token_uuid)
        self.log.debug('found token', **token)
        return token.get('userid', None), token['clientid'], token['scope']
