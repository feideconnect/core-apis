from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPForbidden
from pyramid.response import Response
import uuid
from .controller import OrgController
from coreapis.utils import now, get_user, get_payload, ValidationError, translation


def configure(config):
    org_controller = OrgController(config.get_settings())
    config.add_settings(org_controller=org_controller)
    config.add_request_method(lambda r: r.registry.settings.org_controller, 'org_controller',
                              reify=True)
    config.add_route('org', '/{id}')
    config.add_route('orgs', '/')
    config.add_route('org_logo', '/{id}/logo')
    config.add_route('org_mandatory_clients', '/{id}/mandatory_clients/')
    config.add_route('org_mandatory_client', '/{id}/mandatory_clients/{clientid}')
    config.add_route('org_ldap_status', '/{id}/ldap_status')
    config.scan(__name__)


@view_config(route_name='org', request_method='GET', renderer='json')
@translation
def get_org(request):
    orgid = request.matchdict['id']
    try:
        return request.org_controller.show_org(orgid)
    except KeyError:
        raise HTTPNotFound('No org with id {} was found'.format(orgid))


@view_config(route_name='orgs', request_method='GET', renderer='json')
@translation
def list_org(request):
    peoplesearch = None
    if 'peoplesearch' in request.params:
        peoplesearch = request.params['peoplesearch']
        if peoplesearch == 'true':
            peoplesearch = True
        elif peoplesearch == 'false':
            peoplesearch = False
        else:
            peoplesearch = None
    return request.org_controller.list_orgs(peoplesearch)


@view_config(route_name='org_logo', renderer='logo')
def org_logo(request):
    orgid = request.matchdict['id']
    try:
        logo, updated = request.org_controller.get_logo(orgid)
        if updated is None:
            updated = now()
        return logo, updated, 'data/default-organization.png'
    except KeyError:
        raise HTTPNotFound


def check(request):
    orgid = request.matchdict['id']
    user = get_user(request)
    if not request.org_controller.has_permission(user, orgid):
        raise HTTPForbidden('Insufficient priviledges')
    return orgid


@view_config(route_name='org_mandatory_clients', request_method="GET",
             permission='scope_orgadmin', renderer="json")
def list_mandatory_clients(request):
    orgid = check(request)
    return request.org_controller.list_mandatory_clients(orgid)


@view_config(route_name='org_mandatory_clients', permission='scope_orgadmin',
             request_method='POST', renderer="json")
def add_mandatory_clients(request):
    user = get_user(request)
    orgid = check(request)
    payload = get_payload(request)
    try:
        clientid = uuid.UUID(payload)
    except ValueError:
        raise ValidationError('playload must be only a client id')
    request.org_controller.add_mandatory_client(user, orgid, clientid)
    request.response.status = 201
    request.response.location = request.route_path('org_mandatory_client', id=orgid,
                                                   clientid=clientid)
    return clientid


@view_config(route_name='org_mandatory_client', permission='scope_orgadmin',
             request_method='DELETE', renderer="json")
def del_mandatory_clients(request):
    user = get_user(request)
    orgid = check(request)
    clientid = request.matchdict['clientid']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise HTTPNotFound('invalid client id')
    request.org_controller.del_mandatory_client(user, orgid, clientid)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_ldap_status', permission='scope_orgadmin',
             request_method='GET', renderer="json")
def ldap_status(request):
    user = get_user(request)
    orgid = check(request)
    return(request.org_controller.ldap_status(user, orgid))
