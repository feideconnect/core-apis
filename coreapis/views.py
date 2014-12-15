from pyramid.view import view_config


def configure(config):
    config.add_route('test_open', '/open')
    config.add_route('test_client', '/client')
    config.add_route('test_user', '/user')


@view_config(route_name='test_open', renderer='json')
def test_open(request):
    return {'status': 'open'}


@view_config(route_name='test_client', renderer='json', permission='client')
def test_client(request):
    return {'status': 'open'}


@view_config(route_name='test_user', renderer='json', permission='user')
def test_user(request):
    return {'status': 'open'}
