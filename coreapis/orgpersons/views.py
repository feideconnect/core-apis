import threading
import uuid
from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPBadRequest, HTTPNotFound, HTTPForbidden)
from coreapis.ldap.controller import LDAPController
from coreapis.utils import get_max_replies, get_user
from .controller import OrgPersonController

HDR_DP_CLIENTID = 'x-dataporten-clientid'
HDR_DP_USERID_SEC = 'x-dataporten-userid-sec'


def configure(config):
    settings = config.get_settings()
    ldap_controller = LDAPController(settings)
    mainthread = threading.current_thread()
    config.add_settings(ldap_controller=ldap_controller)
    threading.Thread(target=lambda: ldap_controller.health_check_thread(mainthread)).start()
    op_controller = OrgPersonController(settings)
    config.add_settings(op_controller=op_controller)
    config.add_request_method(lambda r: r.registry.settings['op_controller'], 'op_controller',
                              reify=True)
    config.add_request_method(lambda r: r.registry.settings['ldap_controller'], 'ldap_controller',
                              reify=True)
    config.add_route('search_users', '/orgs/{orgid}/users/', request_method='GET')
    config.add_route('lookup_user', '/users/{feideid}', request_method='GET')
    config.scan(__name__)


def get_header(request, headerid):
    try:
        return request.headers[headerid]
    except KeyError:
        raise HTTPBadRequest('No {} header given'.format(headerid))


def get_clientid(request):
    clientid = get_header(request, HDR_DP_CLIENTID)
    try:
        return uuid.UUID(clientid)
    except ValueError:
        raise HTTPBadRequest('malformed client id: {}'.format(clientid))


def validate_prefix(prefix):
    if prefix != 'feide':
        raise HTTPBadRequest("Only feide identities supported")


def get_userrealm(request):
    userid_sec = get_header(request, HDR_DP_USERID_SEC)
    prefix, principalname = userid_sec.split(':', 1)
    validate_prefix(prefix)
    return principalname.split('@', 1)[1]


@view_config(route_name='search_users', renderer='json')
def search_users(request):
    clientid = get_clientid(request)
    searchrealm = request.matchdict['orgid']
    subscopes = request.op_controller.get_subscopes(clientid, searchrealm)
    user = get_user(request)
    if user:
        userrealm = get_userrealm(request)
        if not ((userrealm == searchrealm and 'usersearchlocal' in subscopes) or
                'usersearchglobal' in subscopes):
            raise HTTPForbidden('Insufficient permissions, subscopes={}'.format(subscopes))
    elif 'systemsearch' not in subscopes:
        raise HTTPForbidden('Insufficient permissions, subscopes={}'.format(subscopes))
    query = request.params.get('q', None)
    max_replies = get_max_replies(request)
    return request.op_controller.search_users(searchrealm, query, max_replies)


@view_config(route_name='lookup_user', renderer='json')
def lookup_user(request):
    if get_user(request):
        raise HTTPForbidden('Lookup on behalf of user not supported')
    feideid = request.matchdict['feideid']
    prefix, principalname = feideid.split(':', 1)
    validate_prefix(prefix)
    clientid = get_clientid(request)
    _, searchrealm = principalname.split('@', 1)
    subscopes = request.op_controller.get_subscopes(clientid, searchrealm)
    if 'systemlookup' not in subscopes:
        raise HTTPForbidden('Insufficient permissions, subscopes={}'.format(subscopes))
    try:
        return request.op_controller.lookup_user(principalname)
    except KeyError:
        raise HTTPNotFound('User not found')
