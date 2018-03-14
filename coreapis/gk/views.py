import logging

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPForbidden, HTTPNotFound

from .controller import GkController
from coreapis.utils import ValidationError, LogWrapper

LOG = LogWrapper('gk.views')


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


def get_dn_header(request):
    try:
        return request.headers['Gate-Keeper-Dn']
    except KeyError:
        raise ValidationError('Gate-Keeper-DN header missing')

@view_config(route_name='gk_info', renderer='json', request_param="method=OPTIONS")
def options(request):
    if not request.gk_controller.allowed_dn(get_dn_header(request)):
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
    if not request.gk_controller.allowed_dn(get_dn_header(request)):
        raise HTTPForbidden('client certificate not authorized')
    backend = request.matchdict['backend']
    prefix = request.registry.settings.gk_header_prefix
    client = request.environ.get('FC_CLIENT', None)
    user = request.environ.get('FC_USER', None)
    scopes = request.environ.get('FC_SCOPES', [])
    subtokens = request.environ.get('FC_SUBTOKENS', None)
    acr = request.environ.get('FC_ACR', None)
    try:
        headers = request.gk_controller.info(backend, client, user, scopes, subtokens, acr)
        if headers is None:
            raise HTTPForbidden('Token misses required scope, or is not associated with a user')
        for header, value in headers.items():
            request.response.headers[prefix + header] = value
        return ''
    except KeyError:
        raise HTTPNotFound()
