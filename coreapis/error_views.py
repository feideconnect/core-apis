from pyramid.view import view_config, forbidden_view_config, notfound_view_config
from pyramid.httpexceptions import HTTPConflict

from .utils import www_authenticate, ValidationError, LogWrapper

log = LogWrapper('error_views')


@forbidden_view_config(renderer='json')
def forbidden(context, request):
    auth = None
    if 'FC_CLIENT' in request.environ:
        if context.detail.endswith('failed permission check'):
            auth = www_authenticate(request.registry.settings.realm,
                                    'invalid_scope',
                                    'Supplied token does not give access to perform the request')
        request.response.status_code = 403
        message = str(context)
    else:
        auth = www_authenticate(request.registry.settings.realm)
        request.response.status_code = 401
        message = 'Not authorized'
    if auth:
        request.response.headers['WWW-Authenticate'] = auth
    return {'message': message}


@notfound_view_config(renderer='json')
def notfound(context, request):
    if context and context.args and context.args[0]:
        message = context.args[0]
    else:
        message = 'Requested resource was not found'
    request.response.status_code = 404
    return {'message': message}


@view_config(context=Exception, renderer='json')
def exception_handler(context, request):
    request.response.status_code = 500
    log.exception('unhandled exception')
    return {'message': 'Internal server error'}


@view_config(context=ValidationError, renderer='json')
def validation_error(context, request):
    request.response.status_code = 400
    log.exception('validation error')
    return {'message': context.message}


@view_config(context=HTTPConflict, renderer='json')
def conflict_handler(context, request):
    request.response.status_code = 409
    log.exception('validation error')
    return {'message': context.message}
