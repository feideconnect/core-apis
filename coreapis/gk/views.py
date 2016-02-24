import logging

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound

from .controller import GkController


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    authz = config.get_settings().get('cassandra_authz')
    gk_controller = GkController(contact_points, keyspace, authz)
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
    prefix = request.registry.settings.gk_header_prefix
    try:
        headers = request.gk_controller.options(backend)
        for header, value in headers.items():
            request.response.headers[prefix + header] = value
        return ''
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='gk_info', renderer='json')
def info(request):
    if not request.gk_controller.allowed_dn(request.headers['Gate-Keeper-Dn']):
        raise HTTPForbidden('client certificate not authorized')
    backend = request.matchdict['backend']
    prefix = request.registry.settings.gk_header_prefix
    if not request.has_permission('scope_gk_{}'.format(backend)):
        logging.debug('provided token misses scopes to access this api')
        raise HTTPForbidden('Unauthorized: scope_gk_{} failed permission check'.format(backend))
    client = request.environ['FC_CLIENT']
    user = request.environ.get('FC_USER', None)
    scopes = request.environ['FC_SCOPES']
    subtokens = request.environ['FC_SUBTOKENS']
    try:
        headers = request.gk_controller.info(backend, client, user, scopes, subtokens)
        if headers is None:
            raise HTTPForbidden('token with user required')
        for header, value in headers.items():
            request.response.headers[prefix + header] = value
        return ''
    except KeyError:
        raise HTTPNotFound()
