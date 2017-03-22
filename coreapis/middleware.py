import base64
import json
import urllib.parse
import uuid

from aniso8601 import parse_datetime
from eventlet.pools import Pool as EventletPool

from . import cassandra_client
from .utils import (
    LogWrapper, Timer, RateLimiter, now, www_authenticate, init_request_id, request_id,
    ResourcePool, log_token, get_cassandra_authz)

NULL_USER = uuid.UUID('00000000-0000-0000-0000-000000000000')


def mock_main(app, config):
    return MockAuthMiddleware(app, config['oauth_realm'])


def log_main(app, config):
    return LogMiddleware(app)


def cors_main(app, config):
    return CorsMiddleware(app)


def ratelimit_main(app, config, client_max_share, client_max_rate, client_max_burst_size):
    ratelimiter = RateLimiter(float(client_max_share),
                              int(client_max_burst_size),
                              float(client_max_rate))
    return RateLimitMiddleware(app, ratelimiter)


def cassandra_main(app, config, cls=None):
    contact_points = config['cassandra_contact_points'].split(', ')
    keyspace = config['cassandra_keyspace']
    authz = get_cassandra_authz(config)
    log_timings = config.get('log_timings', 'false').lower() == 'true'
    use_eventlets = (config.get('use_eventlets', '') == 'true')
    if use_eventlets:
        pool = EventletPool
    else:
        pool = ResourcePool
    timer = Timer(config['statsd_server'], int(config['statsd_port']),
                  config['statsd_prefix'], log_timings, pool)
    if cls is None:
        cls = CassandraMiddleware
    return cls(app, config['oauth_realm'], contact_points,
               keyspace, timer, use_eventlets, authz)


def gatekeeped_mw_main(app, config, username, password):
    contact_points = config['cassandra_contact_points'].split(', ')
    keyspace = config['cassandra_keyspace']
    authz = get_cassandra_authz(config)
    log_timings = config.get('log_timings', 'false').lower() == 'true'
    use_eventlets = (config.get('use_eventlets', '') == 'true')
    if use_eventlets:
        pool = EventletPool
    else:
        pool = ResourcePool
    timer = Timer(config['statsd_server'], int(config['statsd_port']),
                  config['statsd_prefix'], log_timings, pool)
    return GatekeepedMiddleware(app, config['oauth_realm'], contact_points,
                                keyspace, timer, use_eventlets, authz, username, password)


def gk_main(app, config):
    return cassandra_main(app, config, GKMiddleware)


class CorsMiddleware(object):
    def __init__(self, app):
        self.app = app

    def __call__(self, environ, start_response):
        return self.app(environ, self.start_response(start_response))

    def start_response(self, orig):
        def wrapped(status, headers):
            myheaders = [
                ('Access-Control-Allow-Origin', '*'),
                ('Access-Control-Allow-Methods', 'HEAD, GET, OPTIONS, PUT, POST, PATCH, DELETE'),
                ('Access-Control-Allow-Headers',
                 'Authorization, X-Requested-With, Origin, Accept, Content-Type'),
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
            req_uri = urllib.parse.quote(environ.get('SCRIPT_NAME', '') +
                                         environ.get('PATH_INFO', ''))
            if environ.get('QUERY_STRING'):
                req_uri += '?'+environ['QUERY_STRING']
            method = environ['REQUEST_METHOD']
            self.log.info('access', uri=req_uri, method=method, status=status)
            headers.append(('X-Request-Id', str(request_id())))
            return start_response(status, headers)
        return self.app(environ, replace_start_response)


class AuthMiddleware(object):
    def __init__(self, app, realm):
        self._app = app
        self.realm = realm
        self.log = LogWrapper('dataporten.auth')

    def __call__(self, environ, start_response):
        token = self.get_token(environ)
        if token:
            try:
                tokendata = self.lookup_token(token)
                environ.update(tokendata)
                user = environ["FC_USER"]
                client = environ["FC_CLIENT"]
                scopes = environ["FC_SCOPES"]
                self.log.debug('successfully looked up token',
                               user=user['userid'] if user else None,
                               clientid=client['id'], scopes=scopes, accesstoken=log_token(token))
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
                       'peoplesearch', 'gk_unittest', 'clientadmin_loginstats'],
        },
    }

    def lookup_token(self, token):
        if token in self.tokens:
            data = self.tokens[token]
            return {
                'FC_USER': data.get('user', None),
                'FC_CLIENT': data['client'],
                'FC_SCOPES': data['scopes'],
            }
        else:
            raise KeyError('Token not found')


class GKMockAuthMiddleware(MockAuthMiddleware):
    def lookup_token(self, token):
        data = super(GKMockAuthMiddleware, self).lookup_token(token)
        data['FC_SUBTOKENS'] = {}
        return data


def get_client_address(environ):
    try:
        return environ['HTTP_X_FORWARDED_FOR'].split(',')[-1].strip()
    except KeyError:
        return environ['REMOTE_ADDR']


class RateLimitMiddleware(object):
    def __init__(self, app, ratelimiter):
        self._app = app
        self.ratelimiter = ratelimiter

    def __call__(self, environ, start_response):
        if not self.ratelimiter.check_rate(get_client_address(environ)):
            headers = []
            start_response('429 Too many requests', headers)
            return ""
        else:
            return self._app(environ, start_response)


class CassandraMiddleware(AuthMiddleware):
    def __init__(self, app, realm, contact_points, keyspace, timer,
                 use_eventlet, authz):
        super(CassandraMiddleware, self).__init__(app, realm)
        self.timer = timer
        self.session = cassandra_client.Client(contact_points, keyspace, use_eventlet, authz=authz)
        self.session.timer = timer

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

    def _lookup_token(self, token_string):
        try:
            token_uuid = uuid.UUID(token_string)
        except ValueError:
            raise KeyError("Token is invalid")
        with self.timer.time('auth.lookup_token'):
            token = self.session.get_token(token_uuid)
            if not self.token_is_valid(token, token_string):
                raise KeyError("Token is invalid")

            client = self.session.get_client_by_id(token['clientid'])
            if 'userid' in token and token['userid'] is not None and token['userid'] != NULL_USER:
                user = self.session.get_user_by_id(token['userid'])
            else:
                user = None
            return token, client, user

    def lookup_token(self, token_string):
        token, client, user = self._lookup_token(token_string)
        return {
            'FC_USER': user,
            'FC_CLIENT': client,
            'FC_SCOPES': token['scope'],
        }


class GKMiddleware(CassandraMiddleware):
    def lookup_token(self, token_string):
        token, client, user = self._lookup_token(token_string)
        if 'subtokens' not in token or not token['subtokens']:
            raise KeyError("Token is invalid")
        return {
            'FC_USER': user,
            'FC_CLIENT': client,
            'FC_SCOPES': token['scope'],
            'FC_SUBTOKENS': token['subtokens'],
        }


class GatekeepedMiddleware(object):
    def __init__(self, app, realm, contact_points, keyspace, timer,
                 use_eventlet, authz, username, password):
        self._app = app
        self.realm = realm
        self.credentials = str(base64.b64encode('{}:{}'.format(username, password).encode('UTF-8')), 'UTF-8')
        self.log = LogWrapper('dataporten.auth')
        self.session = cassandra_client.Client(contact_points, keyspace, use_eventlet, authz=authz)
        self.session.timer = timer

    def __call__(self, environ, start_response):
        authorization = self.get_authorization(environ)
        if authorization is not None:
            if authorization == self.credentials:
                userid = environ.get('HTTP_X_DATAPORTEN_USERID', None)
                clientid = environ.get('HTTP_X_DATAPORTEN_CLIENTID')
                gatekeeper = environ.get('HTTP_X_DATAPORTEN_GATEKEEPER')
                scopes = [gatekeeper]
                subscopestr = environ.get('HTTP_X_DATAPORTEN_SCOPES')
                if subscopestr:
                    subscopes = subscopestr.split(',')
                    scopes = ["{}_{}".format(gatekeeper, s) for s in subscopes]
                else:
                    scopes = []
                scopes.append(gatekeeper)
                if userid:
                    user = self.session.get_user_by_id(uuid.UUID(userid))
                else:
                    user = None
                client = self.session.get_client_by_id(uuid.UUID(clientid))
                token = environ.get('HTTP_X_DATAPORTEN_TOKEN')
                environ.update({
                    'FC_USER': user,
                    'FC_CLIENT': client,
                    'FC_SCOPES': scopes,
                    'FC_TOKEN': token
                })
                self.log.debug('successfully authenticated request', user=userid, clientid=clientid,
                               scopes=scopes, accesstoken=log_token(token))
            else:
                # Invalid token passed. Perhaps return 402?
                self.log.debug('invalid credentials')
                headers = [
                    ('WWW-Authenticate', www_authenticate(self.realm, authtype='Basic')),
                    ('Content-Type', 'application/json; charset=UTF-8'),
                ]
                start_response('401 Unauthorized', headers)
                return [json.dumps({'message': 'Invalid credentials'}).encode('utf-8')]
        return self._app(environ, start_response)

    def get_authorization(self, environ):
        authorization = environ.get('HTTP_AUTHORIZATION')
        if authorization:
            authtype, sep, value = authorization.partition(' ')
            if authtype == 'Basic':
                return value
            else:
                self.log.debug('unhandled authorization scheme {}'.format(authorization.split()[0]))
        return None
