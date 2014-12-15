def mock_main(app, config):
    return MockAuthMiddleware(app)


class AuthMiddleware(object):
    def __init__(self, app):
        self._app = app

    def __call__(self, environ, start_response):
        token = self.get_token(environ)
        if token:
            try:
                user, client, scopes = self.lookup_token(token)
                environ["FC_USER"] = user
                environ["FC_CLIENT"] = client
                environ["FC_SCOPES"] = scopes
            except KeyError:
                pass  # Invalid token passed. Perhaps return 402?
        return self._app(environ, start_response)

    def get_token(self, environ):
        authorization = environ.get('HTTP_AUTHORIZATION')
        if authorization and authorization.startswith('bearer '):
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
