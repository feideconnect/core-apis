import threading
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPNotModified, HTTPForbidden
from pyramid.response import Response
from coreapis.utils import get_user, get_max_replies
from coreapis.ldap.controller import LDAPController
from .controller import validate_query, PeopleSearchController


def configure(config):
    settings = config.get_settings()
    ldap_controller = LDAPController(settings)
    mainthread = threading.current_thread()
    threading.Thread(target=lambda: ldap_controller.health_check_thread(mainthread)).start()
    ps_controller = PeopleSearchController(ldap_controller, settings)
    config.add_settings(ldap_controller=ldap_controller, ps_controller=ps_controller)
    config.add_request_method(lambda r: r.registry.settings['ldap_controller'], 'ldap_controller',
                              reify=True)
    config.add_request_method(lambda r: r.registry.settings['ps_controller'], 'ps_controller',
                              reify=True)
    config.add_route('person_search_v1', '/v1/search/{org}/{name}')
    config.add_route('person_search', '/search/{org}/{name}')
    config.add_route('admin_search', '/admin_search/{org}/{name}')
    config.add_route('list_realms_v1', '/v1/orgs')
    config.add_route('list_realms', '/orgs')
    config.add_route('profile_photo_v1', '/v1/people/profilephoto/{token}')
    config.add_route('profile_photo', '/people/profilephoto/{token}')
    config.scan(__name__)


@view_config(route_name='person_search_v1', renderer='json', permission='scope_peoplesearch')
def person_search_v1(request):
    user = get_user(request)
    if not user:
        raise HTTPForbidden('This resource requires a personal token')
    org = request.matchdict['org']
    search = request.matchdict['name']
    max_replies = get_max_replies(request)
    validate_query(search)
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if not request.ps_controller.valid_org(org):
        raise HTTPNotFound('Unknown org')
    return request.ps_controller.search(org, search, user, max_replies)


@view_config(route_name='admin_search', renderer='json', permission='scope_orgadmin')
def admin_search(request):
    user = get_user(request)
    if not user:
        raise HTTPForbidden('This resource requires a personal token')
    if not request.ps_controller.is_platform_admin:
        raise HTTPForbidden('Insufficient access')

    org = request.matchdict['org']
    search = request.matchdict['name']
    max_replies = get_max_replies(request)
    sameorg = (request.params.get('sameorg', 'false') == 'true')
    validate_query(search)
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if not request.ps_controller.valid_org(org):
        raise HTTPNotFound('Unknown org')
    return request.ps_controller.admin_search(org, search, sameorg, max_replies)


@view_config(route_name='person_search', renderer='json', permission='scope_peoplesearch')
def person_search(request):
    return person_search_v1(request)


@view_config(route_name='list_realms_v1', renderer='json', permission='scope_peoplesearch')
def list_realms_v1(request):
    return request.ps_controller.orgs()


@view_config(route_name='list_realms', renderer='json', permission='scope_peoplesearch')
def list_realms(request):
    return list_realms_v1(request)


def cache_date_min(a, b):
    if a and not b:
        return a
    if b and not a:
        return b
    return min(a, b)


@view_config(route_name='profile_photo_v1')
def profilephoto_v1(request):
    token = request.matchdict['token']
    user = request.ps_controller.decrypt_profile_image_token(token)
    image, etag, last_modified = \
        request.ps_controller.profile_image(user)
    if request.if_none_match and etag in request.if_none_match:
        raise HTTPNotModified()
    if request.if_modified_since and request.if_modified_since >= last_modified:
        raise HTTPNotModified()
    response = Response(image, charset=None)
    response.content_type = 'image/jpeg'
    response.cache_control = 'public, max-age=3600'
    response.last_modified = last_modified
    response.etag = etag
    return response


@view_config(route_name='profile_photo')
def profilephoto(request):
    return profilephoto_v1(request)
