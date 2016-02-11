import uuid

from pyramid.view import view_config
from pyramid.httpexceptions import (
    HTTPNotFound, HTTPConflict, HTTPForbidden, HTTPBadRequest)
from pyramid.response import Response

from .controller import ClientAdmController
from coreapis.utils import (
    AlreadyExistsError, ForbiddenError, get_userid, get_payload, get_user, translation,
    get_logo_bytes)
from coreapis.id_providers import individual_has_permission


def get_clientid(request):
    try:
        clientid = request.matchdict['id']
        return uuid.UUID(clientid)
    except ValueError:
        raise HTTPNotFound('malformed client id')


def configure(config):
    cadm_controller = ClientAdmController(config.get_settings())
    config.add_settings(cadm_controller=cadm_controller)
    config.add_request_method(lambda r: r.registry.settings.cadm_controller, 'cadm_controller',
                              reify=True)
    config.add_route('get_client', '/clients/{id}', request_method='GET')
    config.add_route('list_clients', '/clients/', request_method='GET')
    config.add_route('public_clients_v1', '/v1/public/', request_method='GET')
    config.add_route('public_clients', '/public/', request_method='GET')
    config.add_route('add_client', '/clients/', request_method='POST')
    config.add_route('delete_client', '/clients/{id}', request_method='DELETE')
    config.add_route('update_client', '/clients/{id}', request_method='PATCH')
    config.add_route('update_gkscopes', '/clients/{id}/gkscopes', request_method='PATCH')
    config.add_route('client_logo_v1', '/v1/clients/{id}/logo')
    config.add_route('client_logo', '/clients/{id}/logo')
    config.add_route('list_scopes_v1', '/v1/scopes/')
    config.add_route('list_scopes', '/scopes/')
    config.add_route('orgauthorization', '/clients/{id}/orgauthorization/{realm}')
    config.add_route('realmclients', '/realmclients/targetrealm/{realm}/', request_method='GET')
    config.add_route('mandatory_clients_v1', '/v1/mandatory/', request_method='GET')
    config.scan(__name__)


def check(request):
    user = get_user(request)
    clientid = get_clientid(request)
    try:
        client = request.cadm_controller.get(clientid)
        if not request.cadm_controller.has_permission(client, user):
            raise HTTPForbidden('Insufficient permissions')
        return client
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='list_clients', renderer='json', permission='scope_clientadmin')
@translation
def list_clients(request):
    user = get_user(request)
    organization = request.params.get('organization', None)
    scope = request.params.get('scope', None)
    if organization:
        if request.cadm_controller.is_admin(user, organization):
            return request.cadm_controller.list_by_organization(organization, scope)
        else:
            raise HTTPForbidden('user is not admin for given organization')
    else:
        return request.cadm_controller.list_by_owner(user['userid'], scope)


@view_config(route_name='public_clients_v1', renderer='json')
@translation
def public_clients_v1(request):
    orgauthorization = request.params.get('orgauthorization', None)
    return request.cadm_controller.public_clients(orgauthorization)


@view_config(route_name='public_clients', renderer='json')
@translation
def public_clients(request):
    return public_clients_v1(request)


@view_config(route_name='get_client', renderer='json')
@translation
def get_client(request):
    user = get_user(request)
    clientid = get_clientid(request)
    try:
        client = request.cadm_controller.get(clientid)
        if not request.cadm_controller.has_permission(client, user) or \
           (not request.has_permission('scope_clientadmin')):
            return request.cadm_controller.get_public_info(client)
    except KeyError:
        raise HTTPNotFound
    return client


def allowed_attrs(attrs, operation):
    protected_keys = ['created', 'owner', 'scopes', 'updated', 'orgauthorization']
    if operation != 'add':
        protected_keys.append('id')
        protected_keys.append('organization')
    return {k: v for k, v in attrs.items() if k not in protected_keys}


@view_config(route_name='add_client', renderer='json', request_method='POST',
             permission='scope_clientadmin')
@translation
def add_client(request):
    userid = get_userid(request)
    payload = get_payload(request)
    user = get_user(request)
    attrs = allowed_attrs(payload, 'add')
    if 'organization' in attrs:
        if not request.cadm_controller.is_admin(user, attrs['organization']):
            raise HTTPForbidden('Not administrator for organization')
    elif not individual_has_permission(user, 'add_client'):
        raise HTTPForbidden('Not authenticated by approved entity')
    try:
        client = request.cadm_controller.add(attrs, userid)
    except AlreadyExistsError:
        raise HTTPConflict("client with this id already exists")
    request.response.status = '201 Created'
    request.response.location = "{}{}".format(request.url, client['id'])
    return client


@view_config(route_name='delete_client', renderer='json', permission='scope_clientadmin')
def delete_client(request):
    client = check(request)
    request.cadm_controller.delete(client['id'])
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='update_client', renderer='json', permission='scope_clientadmin')
@translation
def update_client(request):
    client = check(request)
    payload = get_payload(request)
    attrs = allowed_attrs(payload, 'update')
    client = request.cadm_controller.update(client['id'], attrs)
    return client


@view_config(route_name='update_gkscopes', renderer="json", permission='scope_clientadmin')
def update_gkscopes(request):
    user = get_user(request)
    clientid = get_clientid(request)
    payload = get_payload(request)
    scopes_add = payload.get('scopes_add', [])
    scopes_remove = payload.get('scopes_remove', [])
    try:
        request.cadm_controller.update_gkscopes(clientid, user, scopes_add, scopes_remove)
        return "OK"
    except ForbiddenError as err:
        raise HTTPForbidden(err.message)


@view_config(route_name='client_logo_v1', renderer="logo")
def client_logo_v1(request):
    clientid = get_clientid(request)
    try:
        logo, updated = request.cadm_controller.get_logo(clientid)
        return logo, updated, 'data/default-client.png'
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='client_logo', renderer="logo")
def client_logo(request):
    return client_logo_v1(request)


@view_config(route_name='client_logo_v1', request_method="POST", permission='scope_clientadmin',
             renderer="json")
def upload_logo_v1(request):
    client = check(request)
    data = get_logo_bytes(request)
    request.cadm_controller.update_logo(client['id'], data)
    return 'OK'


@view_config(route_name='client_logo', request_method="POST", permission='scope_clientadmin',
             renderer="json")
def upload_logo(request):
    return upload_logo_v1(request)


@view_config(route_name='list_scopes_v1', renderer="json")
def list_scopes_v1(request):
    return request.cadm_controller.list_public_scopes()


@view_config(route_name='list_scopes', renderer="json")
def list_scopes(request):
    return list_scopes_v1(request)


def check_orgauthz_params(request, owner_ok=True):
    user = get_user(request)
    clientid = get_clientid(request)
    realm = request.matchdict['realm']
    try:
        client = request.cadm_controller.get(clientid)
        if not request.cadm_controller.has_realm_permission(realm, user):
            if not owner_ok or not request.cadm_controller.has_permission(client, user):
                raise HTTPForbidden('Insufficient permissions')
        return client, realm
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='orgauthorization', request_method="GET", permission='scope_clientadmin',
             renderer="json")
def get_orgauthorization(request):
    client, realm = check_orgauthz_params(request)
    try:
        return request.cadm_controller.get_orgauthorization(client, realm)
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='orgauthorization', request_method="PATCH", permission='scope_clientadmin',
             renderer="json")
def update_orgauthorization(request):
    client, realm = check_orgauthz_params(request, owner_ok=False)
    scopes = get_payload(request)
    if not isinstance(scopes, list):
        raise HTTPBadRequest('Scopes must be a list')
    scopes = list(set(scopes))
    request.cadm_controller.update_orgauthorization(client, realm, scopes)
    return scopes


@view_config(route_name='orgauthorization', request_method="DELETE", permission='scope_clientadmin',
             renderer="json")
def delete_orgauthorization(request):
    client, realm = check_orgauthz_params(request)
    request.cadm_controller.delete_orgauthorization(client, realm)
    return Response(status='204 No Content', content_type=False)


@view_config(route_name='realmclients', request_method="GET", permission='scope_clientadmin',
             renderer="json")
@translation
def get_realmclients(request):
    realm = request.matchdict['realm']
    return request.cadm_controller.get_realmclients(realm)


@view_config(route_name='mandatory_clients_v1', request_method="GET",
             permission='scope_authzinfo', renderer="json")
@translation
def mandatory_clients(request):
    user = get_user(request)
    return request.cadm_controller.get_mandatory_clients(user)
