from pyramid.view import view_config, forbidden_view_config
from .utils import www_authenticate


def configure(config):
    config.add_route('test_open', '/open')
    config.add_route('test_client', '/client')
    config.add_route('test_user', '/user')
    config.add_route('test_scope', '/scope')


@view_config(route_name='test_open', renderer='json')
def test_open(request):
    return {'status': 'open'}


@view_config(route_name='test_client', renderer='json', permission='client')
def test_client(request):
    return {'client': request.environ['FC_CLIENT']}


@view_config(route_name='test_user', renderer='json', permission='user')
def test_user(request):
    return {'user': request.environ['FC_USER']}


@view_config(route_name='test_scope', renderer='json', permission='scope_test')
def test_scope(request):
    return {'scopes': request.environ['FC_SCOPES']}


@forbidden_view_config(renderer='json')
def forbidden(request):
    if 'FC_CLIENT' in request.environ:
        auth = www_authenticate(request.registry.settings.realm, 'invalid_scope', 'Supplied token does not give access to perform the request')
    else:
        auth = www_authenticate(request.registry.settings.realm)
    request.response.headers['WWW-Authenticate'] = auth
    request.response.status_code = 401
    return {'message': 'Not authorized'}
