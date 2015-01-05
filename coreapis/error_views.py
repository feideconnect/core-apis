from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from .utils import www_authenticate
import logging


@forbidden_view_config(renderer='json')
def forbidden(request):
    if 'FC_CLIENT' in request.environ:
        auth = www_authenticate(request.registry.settings.realm, 'invalid_scope', 'Supplied token does not give access to perform the request')
    else:
        auth = www_authenticate(request.registry.settings.realm)
    request.response.headers['WWW-Authenticate'] = auth
    request.response.status_code = 401
    return {'message': 'Not authorized'}


@notfound_view_config(renderer='json')
def notfound(request):
    request.response.status_code = 404
    return {'message': 'Requested resource was not found'}


@view_config(context=Exception, renderer='json')
def exception_handler(context, request):
    request.response.status_code = 500
    logging.exception('unhandled exception')
    return {'message': 'Internal server error'}
