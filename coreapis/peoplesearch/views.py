import datetime
from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPNotModified
from pyramid.response import Response
import base64
from .controller import validate_query, LDAPController, PeopleSearchController
from coreapis.utils import now


def configure(config):
    key = base64.b64decode(config.get_settings().get('profile_token_secret'))
    contact_points = config.get_settings().get('peoplesearch.cassandra_contact_points').split(', ')
    keyspace = config.get_settings().get('peoplesearch.cache_keyspace')
    cache_update_seconds = int(config.get_settings().get('peoplesearch.cache_update_seconds', 3600))
    timer = config.get_settings().get('timer')
    ldap_controller = LDAPController(timer)
    ps_controller = PeopleSearchController(key, timer, ldap_controller, contact_points, keyspace,
                                           cache_update_seconds)
    config.add_settings(ldap_controller=ldap_controller, ps_controller=ps_controller)
    config.add_request_method(lambda r: r.registry.settings.ldap_controller, 'ldap_controller',
                              reify=True)
    config.add_request_method(lambda r: r.registry.settings.ps_controller, 'ps_controller',
                              reify=True)
    config.add_route('person_search', '/search/{org}/{name}')
    config.add_route('list_realms', '/orgs')
    config.add_route('profile_photo', '/people/profilephoto/{token}')
    config.scan(__name__)


@view_config(route_name='person_search', renderer='json', permission='scope_peoplesearch')
def person_search(request):
    org = request.matchdict['org']
    search = request.matchdict['name']
    validate_query(search)
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if not request.ps_controller.valid_org(org):
        raise HTTPNotFound('Unknown org')
    return request.ps_controller.search(org, search)


@view_config(route_name='list_realms', renderer='json', permission='scope_peoplesearch')
def list_realms(request):
    return request.ps_controller.orgs()


def cache_date_min(a, b):
    if a and not b:
        return a
    if b and not a:
        return b
    return min(a, b)


@view_config(route_name='profile_photo')
def profilephoto(request):
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
