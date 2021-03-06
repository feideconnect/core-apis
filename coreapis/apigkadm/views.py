from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPConflict, HTTPForbidden
from pyramid.response import Response
from coreapis.utils import (
    AlreadyExistsError, get_userid, get_payload, get_user, get_token,
    get_logo_bytes, get_max_replies, translation)
from .controller import APIGKAdmController


def configure(config):
    gkadm_controller = APIGKAdmController(config.get_settings())
    config.add_settings(gkadm_controller=gkadm_controller)
    config.add_request_method(lambda r: r.registry.settings['gkadm_controller'], 'gkadm_controller',
                              reify=True)
    config.add_route('get_apigk', '/apigks/{id}', request_method='GET')
    config.add_route('list_apigks', '/apigks/', request_method='GET')
    config.add_route('public_apigk_v1', '/v1/public/{id}', request_method='GET')
    config.add_route('list_public_apigks_v1', '/v1/public', request_method='GET')
    config.add_route('list_public_apigks', '/public', request_method='GET')
    config.add_route('add_apigk', '/apigks/', request_method='POST')
    config.add_route('delete_apigk', '/apigks/{id}', request_method='DELETE')
    config.add_route('update_apigk', '/apigks/{id}', request_method='PATCH')
    config.add_route('apigk_exists', '/apigks/{id}/exists')
    config.add_route('apigk_logo_v1', '/v1/apigks/{id}/logo')
    config.add_route('apigk_logo', '/apigks/{id}/logo')
    config.add_route('apigk_owner_clients', '/apigks/owners/{ownerid}/clients/')
    config.add_route('apigk_delegate_clients', '/apigks/delegates/{delegateid}/clients/')
    config.add_route('apigk_org_clients', '/apigks/orgs/{orgid}/clients/')
    config.scan(__name__)


def check(request):
    user = get_user(request)
    gkid = request.matchdict['id']
    token = get_token(request)
    try:
        gk = request.gkadm_controller.get(gkid)
        if not request.gkadm_controller.has_permission(gk, user, token):
            raise HTTPForbidden('Insufficient permissions')
        return gk
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='list_apigks', renderer='json', permission='scope_apigkadmin')
def list_apigks(request):
    user = get_user(request)
    organization = request.params.get('organization', None)
    delegated = request.params.get('delegated', 'false').lower() == 'true'
    show_all = request.params.get('showAll', 'false').lower() == 'true'
    if organization:
        if request.gkadm_controller.is_admin(user, organization):
            return request.gkadm_controller.list_by_organization(organization)
        else:
            raise HTTPForbidden('user is not admin for given organization')
    elif show_all:
        if request.gkadm_controller.is_platform_admin(user):
            return request.gkadm_controller.list_all()
        else:
            raise HTTPForbidden('user is not a platform administrator')
    elif delegated:
        token = get_token(request)
        return request.gkadm_controller.list_delegated(user['userid'], token)
    else:
        return request.gkadm_controller.list_by_owner(user['userid'])


@view_config(route_name='public_apigk_v1', renderer='json')
@translation
def public_apigk_v1(request):
    gkid = request.matchdict['id']
    try:
        gk = request.gkadm_controller.get(gkid)
        return request.gkadm_controller.get_public_info(gk)
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='list_public_apigks_v1', renderer='json')
@translation
def list_public_apigks_v1(request):
    query = request.params.get('query', None)
    max_replies = get_max_replies(request)
    return request.gkadm_controller.public_list(query, max_replies)


@view_config(route_name='list_public_apigks', renderer='json')
def list_public_apigks(request):
    return list_public_apigks_v1(request)


@view_config(route_name='get_apigk', renderer='json', permission='scope_apigkadmin')
@translation
def get_apigk(request):
    return check(request)


@view_config(route_name='apigk_exists', renderer='json', permission='scope_apigkadmin')
def apigk_exists(request):
    gkid = request.matchdict['id']
    try:
        request.gkadm_controller.get(gkid)
        return True
    except KeyError:
        return False


@view_config(route_name='add_apigk', renderer='json', request_method='POST',
             permission='scope_apigkadmin')
def add_apigk(request):
    payload = get_payload(request)
    user = get_user(request)
    token = get_token(request)
    controller = request.gkadm_controller
    privileges = controller.get_privileges(user)
    attrs = request.gkadm_controller.allowed_attrs(payload, 'add', privileges)
    if 'organization' in attrs:
        if not controller.is_admin(user, attrs['organization']):
            raise HTTPForbidden('Not administrator for organization')
    elif not controller.has_add_permission(user, token):
        raise HTTPForbidden('Insufficient permissions')
    try:
        apigk = controller.add(attrs, user, privileges)
    except AlreadyExistsError:
        raise HTTPConflict("apigk with this id already exists")
    request.response.status = 201
    request.response.location = "{}{}".format(request.url, apigk['id'])
    return apigk


@view_config(route_name='delete_apigk', renderer='json', permission='scope_apigkadmin')
def delete_apigk(request):
    gk = check(request)
    user = get_user(request)
    token = get_token(request)
    request.gkadm_controller.delete(gk, user, token)
    return Response(status=204, content_type=False)


@view_config(route_name='update_apigk', renderer='json', permission='scope_apigkadmin')
def update_apigk(request):
    gk = check(request)
    payload = get_payload(request)
    controller = request.gkadm_controller
    user = get_user(request)
    privileges = controller.get_privileges(user)
    attrs = controller.allowed_attrs(payload, 'update', privileges)
    apigk = controller.update(gk['id'], attrs, user, privileges)
    return apigk


@view_config(route_name='apigk_logo_v1', renderer="logo")
def apigk_logo_v1(request):
    apigkid = request.matchdict['id']
    try:
        logo, updated = request.gkadm_controller.get_logo(apigkid)
        return logo, updated, 'data/default-apigk.png'
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='apigk_logo', renderer="logo")
def apigk_logo(request):
    return apigk_logo_v1(request)


@view_config(route_name='apigk_logo_v1', request_method="POST", permission='scope_apigkadmin',
             renderer="json")
def upload_logo_v1(request):
    gk = check(request)
    data = get_logo_bytes(request)
    request.gkadm_controller.update_logo(gk['id'], data)
    return 'OK'


@view_config(route_name='apigk_logo', request_method="POST", permission='scope_apigkadmin',
             renderer="json")
def upload_logo(request):
    return upload_logo_v1(request)


@view_config(route_name='apigk_owner_clients', renderer='json', permission='scope_apigkadmin')
@translation
def apigk_owner_clients(request):
    userid = get_userid(request)
    ownerid = request.matchdict['ownerid']
    if ownerid == 'me':
        ownerid = str(userid)
    if ownerid != str(userid):
        raise HTTPForbidden('wrong owner')
    return request.gkadm_controller.get_gkowner_clients(userid)


@view_config(route_name='apigk_delegate_clients', renderer='json', permission='scope_apigkadmin')
@translation
def apigk_delegate_clients(request):
    userid = get_userid(request)
    delegateid = request.matchdict['delegateid']
    if delegateid == 'me':
        delegateid = str(userid)
    if delegateid != str(userid):
        raise HTTPForbidden('wrong delegateid')
    token = get_token(request)
    return request.gkadm_controller.get_gkdelegate_clients(userid, token)


@view_config(route_name='apigk_org_clients', renderer='json', permission='scope_apigkadmin')
@translation
def apigk_org_clients(request):
    user = get_user(request)
    orgid = request.matchdict['orgid']
    if not request.gkadm_controller.is_admin(user, orgid):
        raise HTTPForbidden('No access')
    return request.gkadm_controller.get_gkorg_clients(orgid)
