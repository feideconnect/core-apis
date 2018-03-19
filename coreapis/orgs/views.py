import uuid

from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPForbidden, HTTPConflict
from pyramid.response import Response

from coreapis.utils import (now, get_user, ValidationError, AlreadyExistsError, translation,
                            get_payload, get_logo_bytes)
from .controller import OrgController


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
    config.add_route('org_geo_v1', '/v1/{id}/geo')
    config.add_route('org_geo', '/{id}/geo')
    config.add_route('org_mandatory_clients', '/{id}/mandatory_clients/')
    config.add_route('org_mandatory_client', '/{id}/mandatory_clients/{clientid}')
    config.add_route('org_services', '/{id}/services/')
    config.add_route('org_service', '/{id}/services/{service}')
    config.add_route('org_ldap_status', '/{id}/ldap_status')
    config.add_route('org_roles', '/{id}/roles/')
    config.add_route('org_role', '/{id}/roles/{identity}')
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


@view_config(route_name='orgs', request_method='POST', permission='scope_orgadmin', renderer='json')
def add_org(request):
    user = get_user(request)
    controller = request.org_controller
    privileges = controller.get_privileges(user)
    if not controller.is_platform_admin(user):
        raise HTTPForbidden('Insufficient privileges')
    payload = get_payload(request)
    attrs = controller.allowed_attrs(payload, 'add', privileges)
    try:
        org = controller.add_org(user, attrs)
    except AlreadyExistsError:
        raise HTTPConflict("client with this id already exists")
    request.response.status = '201 Created'
    request.response.location = "{}{}".format(request.url, org['id'])
    return org


@view_config(route_name='org', request_method='PATCH', permission='scope_orgadmin', renderer='json')
def update_org(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    payload = get_payload(request)
    controller = request.org_controller
    privileges = controller.get_privileges(user)
    attrs = request.org_controller.allowed_attrs(payload, 'update', privileges)
    org = controller.update_org(user, orgid, attrs)
    return org


@view_config(route_name='org', request_method='DELETE', renderer='json',
             permission='scope_orgadmin')
def delete_org(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    request.org_controller.delete_org(user, orgid)
    return Response(status='204 No Content', content_type=False)


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


@view_config(route_name='org_geo_v1', request_method='POST', permission='scope_orgadmin',
             renderer="json")
def upload_geo_v1(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=False)
    payload = get_payload(request)
    add = request.params.get('add', 'false').lower() == 'true'
    request.org_controller.update_geo(user, orgid, payload, add)
    return 'OK'


@view_config(route_name='org_geo', request_method='POST', permission='scope_orgadmin',
             renderer="json")
def upload_geo(request):
    return upload_geo_v1(request)


def check(request, needs_realm, needs_platform_admin):
    orgid = request.matchdict['id']
    user = get_user(request)
    try:
        org = request.org_controller.get(orgid)
    except KeyError:
        raise HTTPNotFound()
    if needs_realm and not org['realm']:
        raise HTTPNotFound('Org lacks realm')
    if not request.org_controller.has_permission(user, org, needs_platform_admin):
        raise HTTPForbidden('Insufficient privileges')
    return orgid


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
    request.org_controller.add_service(user, orgid, service)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_service', permission='scope_orgadmin',
             request_method='DELETE', renderer="json")
def del_service(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    service = request.matchdict['service']
    request.org_controller.del_service(user, orgid, service)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_roles', request_method='GET',
             permission='scope_orgadmin', renderer="json")
def list_org_roles(request):
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    return request.org_controller.list_org_roles(orgid)


@view_config(route_name='org_role', request_method='PUT',
             permission='scope_orgadmin', renderer="json")
def add_org_role(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    identity = request.matchdict['identity']
    rolenames = get_payload(request)
    request.org_controller.add_org_role(user, orgid, identity, rolenames)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_role', request_method='DELETE',
             permission='scope_orgadmin', renderer="json")
def del_org_role(request):
    user = get_user(request)
    orgid = check(request, needs_realm=False, needs_platform_admin=True)
    identity = request.matchdict['identity']
    request.org_controller.del_org_role(user, orgid, identity)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='org_ldap_status', permission='scope_orgadmin',
             request_method='GET', renderer="json")
def ldap_status(request):
    user = get_user(request)
    query_id = request.params.get('feideid', '')

    orgid = check(request, needs_realm=True, needs_platform_admin=True)
    return request.org_controller.ldap_status(user, orgid, query_id)
