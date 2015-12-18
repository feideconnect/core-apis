import json
import urllib.parse
import uuid

from aniso8601 import parse_datetime
from eventlet.pools import Pool as EventletPool

from . import cassandra_client
from .utils import LogWrapper, Timer, RateLimiter, now, www_authenticate, init_request_id, ResourcePool, log_token

NULL_USER = uuid.UUID('00000000-0000-0000-0000-000000000000')


def mock_main(app, config):
    return MockAuthMiddleware(app, config['oauth_realm'])


def log_main(app, config):
    return LogMiddleware(app)


def cors_main(app, config):
    return CorsMiddleware(app)


def cassandra_main(app, config, client_max_share, client_max_rate, client_max_burst_size):
    contact_points = config['cassandra_contact_points'].split(', ')
    keyspace = config['cassandra_keyspace']
    log_timings = config.get('log_timings', 'false').lower() == 'true'
    if config.get('use_eventlets', '') == 'true':
        pool = EventletPool
    else:
        pool = ResourcePool
    timer = Timer(config['statsd_server'], int(config['statsd_port']),
                  config['statsd_prefix'], log_timings, pool)
    ratelimiter = RateLimiter(float(client_max_share),
                              int(client_max_burst_size),
                              float(client_max_rate))
    if config.get('use_eventlets', '') == 'true':
        use_eventlets = True
    else:
        use_eventlets = False
    return CassandraMiddleware(app, config['oauth_realm'], contact_points,
                               keyspace, timer, ratelimiter, use_eventlets)


class CorsMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        return self.app(environ, self.start_response(start_response))

    def start_response(self, orig):
        def wrapped(status, headers):
            myheaders = [
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'HEAD, GET, OPTIONS, POST, PATCH, DELETE'),
                ('Access-Control-Allow-Headers', 'Authorization, X-Requested-With, Origin, Accept, Content-Type'),
                ('Access-Control-Expose-Headers', 'Authorization, X-Requested-With, Origin'),
            ]
            myheaders.extend(headers)
            return orig(status, myheaders)
        return wrapped


class LogMiddleware(object):
    def __init__(self, app):
        self.app = app
        self.log = LogWrapper('access')

    def __call__(self, environ, start_response):
        init_request_id()

        def replace_start_response(status, headers):
            req_uri = urllib.parse.quote(environ.get('SCRIPT_NAME', '')
                                         + environ.get('PATH_INFO', ''))
            if environ.get('QUERY_STRING'):
                req_uri += '?'+environ['QUERY_STRING']
            method = environ['REQUEST_METHOD']
            self.log.info('access', uri=req_uri, method=method, status=status)
            return start_response(status, headers)
        return self.app(environ, replace_start_response)


class AuthMiddleware(object):
    def __init__(self, app, realm):
        self._app = app
        self.realm = realm
        self.log = LogWrapper('feideconnect.auth')

    def __call__(self, environ, start_response):
        token = self.get_token(environ)
        if token:
            try:
                user, client, scopes = self.lookup_token(token)
                self.log.debug('successfully looked up token', user=user['userid'] if user else None, client=client['id'],
                               scopes=scopes, accesstoken=log_token(token))
                environ["FC_USER"] = user
                environ["FC_CLIENT"] = client
                environ["FC_SCOPES"] = scopes
            except KeyError as ex:
                # Invalid token passed. Perhaps return 402?
                self.log.debug('failed to find token', accesstoken=log_token(token))
                headers = [
                    ('WWW-Authenticate', www_authenticate(self.realm, 'invalid_token', ex.args[0])),
                    ('Content-Type', 'application/json; charset=UTF-8'),
                ]
                start_response('401 Unauthorized', headers)
                return [json.dumps({'message': ex.args[0]}).encode('utf-8')]
        return self._app(environ, start_response)

    def get_token(self, environ):
        authorization = environ.get('HTTP_AUTHORIZATION')
        if authorization:
            if authorization.startswith('Bearer '):
                token = authorization.split(' ', 1)[1]
                return token
            else:
                self.log.debug('unhandled authorization scheme {}'.format(authorization.split()[0]))
        return None

    def lookup_token(self, token):
        raise KeyError("Not implemented")


class MockAuthMiddleware(AuthMiddleware):
    tokens = {
        'user_token': {
            'user': {
                "name": {"feide:example.com": "Dummy User"},
                "created": parse_datetime('2014-12-15T13:53:36Z'),
                "userid": uuid.UUID("00000000-0000-0000-0000-000000000001"),
                "selectedsource": "feide:example.com",
                "userid_sec_seen": {},
                "userid_sec": ["feide:test@example.com"],
                "email": {"feide:example.com": "dummy@example.com"}
            },

            'client': {
                "status": ["production"],
                "scopes": ["userinfo"],
                "updated": None,
                "name": "Dummy Client",
                "descr": "Dummy Client for dummy testing",
                "created": parse_datetime('2014-12-15T13:53:36Z'),
                "redirect_uri": ["https://sp.example.org/callback"],
                "scopes_requested": [],
                "owner": uuid.UUID("00000000-0000-0000-0000-000000000001"),
                "client_secret": uuid.UUID("00000000-0000-0000-0000-000000000003"),
                "type": "client",
                "id": uuid.UUID("00000000-0000-0000-0000-000000000002")
            },

            'scopes': ['api_ecampusrelay', 'clientadmin', 'apigkadmin', 'authzinfo',
                       'adhocgroupadmin', 'groups', 'orgadmin', 'peoplesearch', 'gk_nicegk'],
        },
        'client_token': {
            'client': {
                "status": ["production"],
                "scopes": ["userinfo"],
                "updated": None,
                "name": "Dummy Client",
                "descr": "Dummy Client for dummy testing",
                "created": parse_datetime('2014-12-15T13:53:36Z'),
                "redirect_uri": ["https://sp.example.org/callback"],
                "scopes_requested": [],
                "owner": uuid.UUID("00000000-0000-0000-0000-000000000001"),
                "client_secret": uuid.UUID("00000000-0000-0000-0000-000000000003"),
                "type": "client",
                "id": uuid.UUID("00000000-0000-0000-0000-000000000002")
            },

            'scopes': ['userinfo', 'longterm', 'test', 'clientadmin', 'apigkadmin', 'groups',
                       'peoplesearch', 'gk_unittest'],
        },
    }

    def lookup_token(self, token):
        if token in self.tokens:
            data = self.tokens[token]
            return data.get('user', None), data['client'], data['scopes']
        else:
            raise KeyError('Token not found')


class CassandraMiddleware(AuthMiddleware):
    def __init__(self, app, realm, contact_points, keyspace, timer, ratelimiter, use_eventlet):
        super(CassandraMiddleware, self).__init__(app, realm)
        self.timer = timer
        self.ratelimiter = ratelimiter
        self.session = cassandra_client.Client(contact_points, keyspace, use_eventlet)
        self.session.timer = timer

    def __call__(self, environ, start_response):
        if self.ratelimiter and not self.ratelimiter.check_rate(environ['REMOTE_ADDR']):
            headers = []
            start_response('429 Too many requests', headers)
            return ""
        else:
            return super(CassandraMiddleware, self).__call__(environ, start_response)

    def token_is_valid(self, token, token_string):
        for column in ('clientid', 'scope', 'validuntil'):
            if column not in token or token[column] is None:
                self.log.warn('token misses required column "{}"'.format(column),
                              accesstoken=log_token(token_string))
                return False

        if token['validuntil'] < now():
            self.log.debug('Expired token used', accesstoken=log_token(token_string))
            return False
        return True

    def lookup_token(self, token_string):
        token_uuid = uuid.UUID(token_string)
        with self.timer.time('auth.lookup_token'):
            token = self.session.get_token(token_uuid)
            if not self.token_is_valid(token, token_string):
                raise KeyError("Token is invalid")

            client = self.session.get_client_by_id(token['clientid'])
            if 'userid' in token and token['userid'] is not None and token['userid'] != NULL_USER:
                user = self.session.get_user_by_id(token['userid'])
            else:
                user = None
        return user, client, token['scope']
