from pyramid.authentication import IAuthenticationPolicy
from pyramid.authorization import IAuthorizationPolicy
import pyramid.security


def get_client(request):
    return request.environ.get('FC_CLIENT', None)


def get_user(request):
    return request.environ.get('FC_USER', None)


def get_scopes(request):
    return request.environ.get('FC_SCOPES', None)


def get_userid(request):
    client = get_client(request)
    user = get_user(request)
    if client and user:
        return '{}___{}'.format(client, user)
    elif client:
        return client
    return None


class TokenAuthenticationPolicy(object):
    def __init__(self):
        pass

    def authenticated_userid(self, request):
        return get_userid(request)

    def unauthenticated_userid(self, request):
        return get_userid(request)

    def effective_principals(self, request):
        if self.authenticated_userid(request):
            principals = [pyramid.security.Everyone, pyramid.security.Authenticated]
            principals += ['scope_{}'.format(scope) for scope in get_scopes(request)]
            principals += ['client', 'client_{}'.format(get_client(request))]
            user = get_user(request)
            if user:
                principals += ['user', 'user_{}'.format(user)]
        else:
            principals = []
        return principals

    def remember(self, request, principal, **kw):
        pass

    def forget(self, request):
        pass


class TokenAuthorizationPolicy(object):
    """ An object representing a Pyramid authorization policy. """
    def permits(self, context, principals, permission):
        return permission in principals

    def principals_allowed_by_permission(self, context, permission):
        raise NotImplementedError()
