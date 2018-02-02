import threading
import uuid
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPBadRequest, HTTPNotFound, HTTPForbidden, HTTPInternalServerError)
from coreapis.ldap.controller import LDAPController
from coreapis.utils import get_max_replies, get_user, ValidationError
from .controller import OrgPersonController

HDR_DP_CLIENTID = 'x-dataporten-clientid'

def configure(config):
    settings = config.get_settings()
    ldap_controller = LDAPController(settings)
    mainthread = threading.current_thread()
    config.add_settings(ldap_controller=ldap_controller)
    threading.Thread(target=lambda: ldap_controller.health_check_thread(mainthread)).start()
    op_controller = OrgPersonController(settings)
    config.add_settings(op_controller=op_controller)
    config.add_request_method(lambda r: r.registry.settings.op_controller, 'op_controller',
                              reify=True)
    config.add_request_method(lambda r: r.registry.settings.ldap_controller, 'ldap_controller',
                              reify=True)
    config.add_route('search_users', '/orgs/{orgid}/users/', request_method='GET')
    config.add_route('lookup_user', '/users/{feideid}', request_method='GET')
    config.scan(__name__)


def get_clientid(request):
    try:
        clientid = request.headers[HDR_DP_CLIENTID]
    except KeyError:
        raise HTTPBadRequest('No {} header given'.format(HDR_DP_CLIENTID))
    try:
        return uuid.UUID(clientid)
    except ValueError:
        raise HTTPBadRequest('malformed client id: {}'.format(clientid))

def check(request, orgid):
    user = get_user(request)
    clientid = get_clientid(request)
    try:
        if not request.op_controller.has_permission(clientid, orgid, user):
            raise HTTPForbidden('Insufficient permissions')
    except KeyError:
        raise HTTPNotFound()

@view_config(route_name='search_users', renderer='json')
def search_users(request):
    orgid = request.matchdict['orgid']
    check(request, orgid)
    query = request.params.get('q', None)
    max_replies = get_max_replies(request)
    return request.op_controller.search_users(orgid, query, max_replies)

@view_config(route_name='lookup_user', renderer='json')
def lookup_user(request):
    import sys
    feideid = request.matchdict['feideid']
    prefix, principalname = feideid.split(':', 1)
    if prefix != 'feide':
        raise HttpInternalServerError("Only feide identities supported")
    _, realm = principalname.split('@', 1)
    check(request, realm)
    try:
        return request.op_controller.lookup_user(principalname)
    except KeyError:
        raise HTTPNotFound('User not found')
