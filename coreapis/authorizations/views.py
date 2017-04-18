import uuid

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPForbidden
from pyramid.response import Response

from .controller import AuthorizationController
from coreapis.utils import get_user, get_userid, get_token, translation, ForbiddenError


def configure(config):
    authz_controller = AuthorizationController(config.get_settings())
    config.add_settings(authz_controller=authz_controller)
    config.add_request_method(lambda r: r.registry.settings.authz_controller, 'authz_controller',
                              reify=True)
    config.add_route('list_authz', '/', request_method='GET')
    config.add_route('delete_authz', '/{id}', request_method='DELETE')
    config.add_route('delete_all_authz', '/all_users/{id}', request_method='DELETE')
    config.add_route('resources_owned', '/resources_owned', request_method='GET')
    config.add_route('consent_withdrawn', '/consent_withdrawn', request_method='POST')
    config.add_route('mandatory_clients', '/mandatory_clients/', request_method='GET')
    config.scan(__name__)


@view_config(route_name="list_authz", permission="scope_authzinfo", renderer="json")
def list(request):
    userid = get_userid(request)
    return request.authz_controller.list(userid)


@view_config(route_name="delete_authz", permission="scope_authzinfo")
def delete(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise HTTPNotFound
    request.authz_controller.delete(userid, clientid)
    return Response(status=204, content_type=False)


@view_config(route_name="delete_all_authz", permission="scope_authzinfo")
def delete_all(request):
    user = get_user(request)
    token = get_token(request)
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise HTTPNotFound
    try:
        request.authz_controller.delete_all(clientid, user, token)
    except ForbiddenError:
        raise HTTPForbidden('Insufficient permissions')
    return Response(status=204, content_type=False)


@view_config(route_name="resources_owned", permission="scope_authzinfo", renderer="json")
def resources_owned(request):
    userid = get_userid(request)
    return request.authz_controller.resources_owned(userid)


@view_config(route_name="consent_withdrawn", permission="scope_authzinfo", renderer="json")
def consent_withdrawn(request):
    userid = get_userid(request)
    if request.authz_controller.consent_withdrawn(userid):
        return 'OK'
    else:
        raise HTTPForbidden('User still owns resources')


@view_config(route_name='mandatory_clients', request_method="GET",
             permission='scope_authzinfo', renderer="json")
@translation
def mandatory_clients(request):
    user = get_user(request)
    return request.authz_controller.get_mandatory_clients(user)
