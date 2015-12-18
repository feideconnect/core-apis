import logging

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound

from .controller import GkController


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    gk_controller = GkController(contact_points, keyspace)
    config.add_settings(gk_controller=gk_controller)
    config.add_request_method(lambda r: r.registry.settings.gk_controller, 'gk_controller',
                              reify=True)
    config.add_route('gk_info', '/info/{backend}')
    config.scan(__name__)


@view_config(route_name='gk_info', renderer='json', request_param="method=OPTIONS")
def options(request):
    if not request.gk_controller.allowed_dn(request.headers['Gate-Keeper-Dn']):
        raise HTTPForbidden('client certificate not authorized')
    backend = request.matchdict['backend']
    try:
        headers = request.gk_controller.options(backend)
        for header, value in headers.items():
            request.response.headers['X-FeideConnect-' + header] = value
        return ''
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='gk_info', renderer='json')
def info(request):
    if not request.gk_controller.allowed_dn(request.headers['Gate-Keeper-Dn']):
        raise HTTPForbidden('client certificate not authorized')
    backend = request.matchdict['backend']
    if not request.has_permission('scope_gk_{}'.format(backend)):
        logging.debug('not authorized')
        raise HTTPForbidden('Unauthorized: scope_gk_{} failed permission check'.format(backend))
    client = request.environ['FC_CLIENT']
    user = request.environ.get('FC_USER', None)
    scopes = request.environ['FC_SCOPES']
    try:
        headers = request.gk_controller.info(backend, client, user, scopes)
        if headers is None:
            raise HTTPForbidden('token with user required')
        for header, value in headers.items():
            request.response.headers['X-FeideConnect-' + header] = value
        return ''
    except KeyError:
        raise HTTPNotFound()
