import uuid

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPForbidden
from pyramid.response import Response

from .controller import OrgController
from coreapis.utils import now, get_user, ValidationError, translation, get_logo_bytes


def valid_service(service):
    valid_services = ['auth', 'avtale', 'pilot']
    return service in valid_services


def configure(config):
    org_controller = OrgController(config.get_settings())
    config.add_settings(org_controller=org_controller)
    config.add_request_method(lambda r: r.registry.settings.org_controller, 'org_controller',
                              reify=True)
    config.add_route('org_v1', '/v1/{id}')
    config.add_route('org', '/{id}')
    config.add_route('orgs_v1', '/v1/')
    config.add_route('orgs', '/')
    config.add_route('org_logo_v1', '/v1/{id}/logo')
    config.add_route('org_logo', '/{id}/logo')
    config.add_route('org_mandatory_clients', '/{id}/mandatory_clients/')
    config.add_route('org_mandatory_client', '/{id}/mandatory_clients/{clientid}')
    config.add_route('org_services', '/{id}/services/')
    config.add_route('org_service', '/{id}/services/{service}')
    config.add_route('org_ldap_status', '/{id}/ldap_status')
    config.scan(__name__)


@view_config(route_name='org_v1', request_method='GET', renderer='json')
@translation
def get_org_v1(request):
    orgid = request.matchdict['id']
    try:
        return request.org_controller.show_org(orgid)
    except KeyError:
        raise HTTPNotFound('No org with id {} was found'.format(orgid))


@view_config(route_name='org', request_method='GET', renderer='json')
@translation
def get_org(request):
    return get_org_v1(request)


@view_config(route_name='orgs_v1', request_method='GET', renderer='json')
@translation
def list_org_v1(request):
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


@view_config(route_name='orgs', request_method='GET', renderer='json')
@translation
def list_org(request):
    return list_org_v1(request)


@view_config(route_name='org_logo_v1', renderer='logo')
def org_logo_v1(request):
    orgid = request.matchdict['id']
    try:
        logo, updated = request.org_controller.get_logo(orgid)
        if updated is None:
            updated = now()
        return logo, updated, 'data/default-organization.png'
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='org_logo', renderer='logo')
def org_logo(request):
    return org_logo_v1(request)


@view_config(route_name='org_logo_v1', request_method="POST", permission='scope_orgadmin',
             renderer="json")
def upload_logo_v1(request):
    orgid = check(request, needs_realm=False, needs_platform_admin=False)
    data = get_logo_bytes(request)
    request.org_controller.update_logo(orgid, data)
    return 'OK'


@view_config(route_name='org_logo', request_method="POST", permission='scope_orgadmin',
             renderer="json")
def upload_logo(request):
    return upload_logo_v1(request)


def check(request, needs_realm, needs_platform_admin):
    orgid = request.matchdict['id']
    user = get_user(request)
    try:
        if not request.org_controller.has_permission(user, orgid, needs_realm,
                                                     needs_platform_admin):
            raise HTTPForbidden('Insufficient privileges')
        return orgid
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='org_mandatory_clients', request_method="GET",
             permission='scope_orgadmin', renderer="json")
def list_mandatory_clients(request):
    orgid = check(request, needs_realm=True, needs_platform_admin=False)
    return request.org_controller.list_mandatory_clients(orgid)


@view_config(route_name='org_mandatory_client', permission='scope_orgadmin',
             request_method='PUT', renderer="json")
def add_mandatory_client(request):
    user = get_user(request)
    orgid = check(request, needs_realm=True, needs_platform_admin=False)
    clientid = request.matchdict['clientid']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise ValidationError('client id must be a valid uuid')
    request.org_controller.add_mandatory_client(user, orgid, clientid)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_mandatory_client', permission='scope_orgadmin',
             request_method='DELETE', renderer="json")
def del_mandatory_client(request):
    user = get_user(request)
    orgid = check(request, needs_realm=True, needs_platform_admin=False)
    clientid = request.matchdict['clientid']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise HTTPNotFound('invalid client id')
    request.org_controller.del_mandatory_client(user, orgid, clientid)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_services', request_method="GET",
             permission='scope_orgadmin', renderer="json")
def list_services(request):
    orgid = check(request, needs_realm=False, needs_platform_admin=False)
    return request.org_controller.list_services(orgid)


@view_config(route_name='org_service', request_method='PUT', renderer="json")
def add_service(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    service = request.matchdict['service']
    if not valid_service(service):
        raise ValidationError('payload must be a valid service')
    request.org_controller.add_service(user, orgid, service)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_service', permission='scope_orgadmin',
             request_method='DELETE', renderer="json")
def del_service(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    service = request.matchdict['service']
    if not valid_service(service):
        raise ValidationError('not a valid service')
    request.org_controller.del_service(user, orgid, service)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_ldap_status', permission='scope_orgadmin',
             request_method='GET', renderer="json")
def ldap_status(request):
    user = get_user(request)
    orgid = check(request, needs_realm=True, needs_platform_admin=False)
    return(request.org_controller.ldap_status(user, orgid))
