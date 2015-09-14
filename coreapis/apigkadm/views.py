from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPConflict, HTTPForbidden
from pyramid.response import Response
from .controller import APIGKAdmController
from coreapis.utils import AlreadyExistsError, get_userid, get_payload, get_user, translation


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    maxrows = config.get_settings().get('apigkadm_maxrows')
    gkadm_controller = APIGKAdmController(contact_points, keyspace, maxrows)
    config.add_settings(gkadm_controller=gkadm_controller)
    config.add_request_method(lambda r: r.registry.settings.gkadm_controller, 'gkadm_controller',
                              reify=True)
    config.add_route('get_apigk', '/apigks/{id}', request_method='GET')
    config.add_route('list_apigks', '/apigks/', request_method='GET')
    config.add_route('list_public_apigks', '/public', request_method='GET')
    config.add_route('add_apigk', '/apigks/', request_method='POST')
    config.add_route('delete_apigk', '/apigks/{id}', request_method='DELETE')
    config.add_route('update_apigk', '/apigks/{id}', request_method='PATCH')
    config.add_route('apigk_exists', '/apigks/{id}/exists')
    config.add_route('apigk_logo', '/apigks/{id}/logo')
    config.add_route('apigk_owner_clients', '/apigks/owners/{ownerid}/clients/')
    config.add_route('apigk_org_clients', '/apigks/orgs/{orgid}/clients/')
    config.scan(__name__)


def allowed_attrs(attrs, operation):
    protected_keys = ['created', 'owner', 'scopes', 'updated']
    if operation != 'add':
        protected_keys.append('id')
        protected_keys.append('organization')
    return {k: v for k, v in attrs.items() if k not in protected_keys}


def check(request):
    user = get_user(request)
    gkid = request.matchdict['id']
    try:
        gk = request.gkadm_controller.get(gkid)
        if not request.gkadm_controller.has_permission(gk, user):
            raise HTTPForbidden('Insufficient permissions')
        return gk
    except KeyError:
        raise HTTPNotFound()


@view_config(route_name='list_apigks', renderer='json', permission='scope_apigkadmin')
def list_apigks(request):
    user = get_user(request)
    organization = request.params.get('organization', None)
    if organization:
        if request.gkadm_controller.is_org_admin(user, organization):
            return request.gkadm_controller.list_by_organization(organization)
        else:
            raise HTTPForbidden('user is not admin for given organization')
    else:
        return request.gkadm_controller.list_by_owner(user['userid'])


@view_config(route_name='list_public_apigks', renderer='json')
@translation
def list_public_apigks(request):
    return request.gkadm_controller.public_list()


@view_config(route_name='get_apigk', renderer='json', permission='scope_apigkadmin')
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
    userid = get_userid(request)
    payload = get_payload(request)
    try:
        attrs = allowed_attrs(payload, 'add')
        if 'organization' in attrs:
            user = get_user(request)
            if not request.gkadm_controller.is_org_admin(user, attrs['organization']):
                raise HTTPForbidden('Not administrator for organization')
        apigk = request.gkadm_controller.add(attrs, userid)
        request.response.status = 201
        request.response.location = "{}{}".format(request.url, apigk['id'])
        return apigk
    except AlreadyExistsError:
        raise HTTPConflict("apigk with this id already exists")


@view_config(route_name='delete_apigk', renderer='json', permission='scope_apigkadmin')
def delete_apigk(request):
    gk = check(request)
    user = get_user(request)
    request.gkadm_controller.delete(gk, user)
    return Response(status=204, content_type=False)


@view_config(route_name='update_apigk', renderer='json', permission='scope_apigkadmin')
def update_apigk(request):
    gk = check(request)
    payload = get_payload(request)
    attrs = allowed_attrs(payload, 'update')
    apigk = request.gkadm_controller.update(gk['id'], attrs)
    return apigk


@view_config(route_name='apigk_logo', renderer="logo")
def apigk_logo(request):
    apigkid = request.matchdict['id']
    try:
        logo, updated = request.gkadm_controller.get_logo(apigkid)
        return logo, updated, 'data/default-apigk.png'
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='apigk_logo', request_method="POST", permission='scope_apigkadmin',
             renderer="json")
def upload_logo(request):
    gk = check(request)

    if 'logo' in request.POST:
        input_file = request.POST['logo'].file
    else:
        input_file = request.body_file_seekable
    input_file.seek(0)
    data = input_file.read()
    request.gkadm_controller.update_logo(gk['id'], data)
    return 'OK'


@view_config(route_name='apigk_owner_clients', renderer='json', permission='scope_apigkadmin')
def apigk_owner_clients(request):
    userid = get_userid(request)
    ownerid = request.matchdict['ownerid']
    if ownerid == 'me':
        ownerid = str(userid)
    if ownerid != str(userid):
        raise HTTPForbidden('wrong owner')
    return request.gkadm_controller.get_gkowner_clients(userid)


@view_config(route_name='apigk_org_clients', renderer='json', permission='scope_apigkadmin')
def apigk_org_clients(request):
    user = get_user(request)
    orgid = request.matchdict['orgid']
    if not request.gkadm_controller.is_org_admin(user, orgid):
        raise HTTPForbidden('No access')
    return request.gkadm_controller.get_gkorg_clients(orgid)
