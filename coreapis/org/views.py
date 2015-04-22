from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPNotModified
from pyramid.response import Response
from .controller import OrgController
from coreapis.utils import pick_lang, now


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    timer = config.get_settings().get('timer')
    org_controller = OrgController(contact_points, keyspace, timer)
    config.add_settings(org_controller=org_controller)
    config.add_request_method(lambda r: r.registry.settings.org_controller, 'org_controller',
                              reify=True)
    config.add_route('org', '/{id}')
    config.add_route('orgs', '/')
    config.add_route('org_logo', '/{id}/logo')
    config.scan(__name__)


@view_config(route_name='org', request_method='GET', renderer='json')
def get_org(request):
    orgid = request.matchdict['id']
    try:
        data = request.org_controller.show_org(orgid)
        data = pick_lang(request, data)
        return data
    except KeyError:
        raise HTTPNotFound('No org with id {} was found'.format(orgid))


@view_config(route_name='orgs', request_method='GET', renderer='json')
def list_org(request):
    data = request.org_controller.list_orgs()
    data = pick_lang(request, data)
    return data


@view_config(route_name='org_logo')
def client_logo(request):
    orgid = request.matchdict['id']
    try:
        logo, updated = request.org_controller.get_logo(orgid)
        if logo is None:
            with open('data/default-organization.png', 'rb') as fh:
                logo = fh.read()
        if updated is None:
            updated = now()
    except KeyError:
        raise HTTPNotFound
    updated = updated.replace(microsecond=0)
    if request.if_modified_since and request.if_modified_since >= updated:
        raise HTTPNotModified
    response = Response(logo, charset=None)
    response.content_type = 'image/png'
    response.cache_control = 'public, max-age=3600'
    response.last_modified = updated
    return response
