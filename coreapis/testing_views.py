from pyramid.view import view_config


def configure(config):
    config.add_route('test_open', '/open')
    config.add_route('test_client', '/client')
    config.add_route('test_user', '/user')
    config.add_route('test_scope', '/scope')
    config.add_route('test_crash', '/crash')
    config.scan(__name__)


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


@view_config(route_name='test_crash', renderer='json')
def test_crash(request):
    raise RuntimeError('Synthetic crash')
