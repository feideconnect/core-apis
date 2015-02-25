from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from .utils import www_authenticate, ValidationError, LogWrapper
import logging
import traceback

log = LogWrapper('error_views')


@forbidden_view_config(renderer='json')
def forbidden(request):
    if 'FC_CLIENT' in request.environ:
        auth = www_authenticate(request.registry.settings.realm, 'invalid_scope', 'Supplied token does not give access to perform the request')
        request.response.status_code = 403
    else:
        auth = www_authenticate(request.registry.settings.realm)
        request.response.status_code = 401
    request.response.headers['WWW-Authenticate'] = auth
    return {'message': 'Not authorized'}


@notfound_view_config(renderer='json')
def notfound(request):
    request.response.status_code = 404
    return {'message': 'Requested resource was not found'}


@view_config(context=Exception, renderer='json')
def exception_handler(context, request):
    request.response.status_code = 500
    exception = traceback.format_exc()
    log.error('unhandled exception', exception=exception)
    return {'message': 'Internal server error'}


@view_config(context=ValidationError, renderer='json')
def validation_error(context, request):
    request.response.status_code = 400
    exception = traceback.format_exc()
    log.error('validation error', exception=exception)
    return {'message': context.message}
