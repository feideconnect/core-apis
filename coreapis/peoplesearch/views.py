from pyramid.view import view_config
from pyramid.exceptions import HTTPNotFound
from pyramid.response import Response
import logging
from coreapis.utils import ValidationError
import base64
from .controller import validate_query, LDAPController, PeopleSearchController


def configure(config):
    key = base64.b64decode(config.get_settings().get('profile_token_secret'))
    timer = config.get_settings().get('timer')
    ldap_controller = LDAPController(timer)
    ps_controller = PeopleSearchController(key, timer, ldap_controller)
    config.add_settings(ldap_controller=ldap_controller, ps_controller=ps_controller)
    config.add_request_method(lambda r: r.registry.settings.ldap_controller, 'ldap_controller',
                              reify=True)
    config.add_request_method(lambda r: r.registry.settings.ps_controller, 'ps_controller',
                              reify=True)
    config.add_route('person_search', '/search/{org}/{name}')
    config.add_route('list_realms', '/orgs')
    config.add_route('profile_photo', '/people/profilephoto/{token}')


@view_config(route_name='person_search', renderer='json', permission='scope_personsearch')
def person_search(request):
    org = request.matchdict['org']
    search = request.matchdict['name']
    validate_query(search)
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if not request.ps_controller.valid_org(org):
        raise HTTPNotFound('Unknown org')
    return request.ps_controller.search(org, search)


@view_config(route_name='list_realms', renderer='json', permission='scope_personsearch')
def list_realms(request):
    return request.ps_controller.orgs()


@view_config(route_name='profile_photo')
def profilephoto(request):
    token = request.matchdict['token']
    image = request.ps_controller.profile_image(token)
    if image is None:
        raise HTTPNotFound()
    response = Response(image, charset=None)
    response.content_type = 'image/jpeg'
    return response
