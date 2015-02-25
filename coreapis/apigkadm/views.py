from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPConflict, HTTPForbidden, HTTPNotModified
from pyramid.response import Response
from .controller import APIGKAdmController
from coreapis.utils import AlreadyExistsError, get_userid, get_payload


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
    config.scan(__name__)


def allowed_attrs(attrs, operation):
    protected_keys = ['created', 'owner', 'scopes', 'updated']
    if operation != 'add':
        protected_keys.append('id')
    return {k: v for k, v in attrs.items() if k not in protected_keys}


@view_config(route_name='list_apigks', renderer='json', permission='scope_apigkadmin')
def list_apigks(request):
    userid = str(get_userid(request))
    params = {}
    for k, v in request.params.items():
        params[k] = v
    params['owner'] = userid
    return request.gkadm_controller.list(params)


@view_config(route_name='list_public_apigks', renderer='json')
def list_public_apigks(request):
    return request.gkadm_controller.public_list()


@view_config(route_name='get_apigk', renderer='json', permission='scope_apigkadmin')
def get_apigk(request):
    userid = get_userid(request)
    gkid = request.matchdict['id']
    try:
        apigk = request.gkadm_controller.get(gkid)
        owner = apigk.get('owner', None)
        if owner and owner != userid:
            raise HTTPForbidden('Not owner')
    except KeyError:
        raise HTTPNotFound()
    return apigk


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
        apigk = request.gkadm_controller.add(attrs, userid)
        request.response.status = 201
        request.response.location = "{}{}".format(request.url, apigk['id'])
        return apigk
    except AlreadyExistsError:
        raise HTTPConflict("apigk with this id already exists")


@view_config(route_name='delete_apigk', renderer='json', permission='scope_apigkadmin')
def delete_apigk(request):
    userid = get_userid(request)
    gkid = request.matchdict['id']
    owner = request.gkadm_controller.get_owner(gkid)
    if owner and owner != userid:
        raise HTTPForbidden('Not owner')
    request.gkadm_controller.delete(gkid)
    return Response(status=204, content_type=False)


@view_config(route_name='update_apigk', renderer='json', permission='scope_apigkadmin')
def update_apigk(request):
    userid = get_userid(request)
    gkid = request.matchdict['id']
    payload = get_payload(request)
    try:
        owner = request.gkadm_controller.get_owner(gkid)
        if owner and owner != userid:
            raise HTTPForbidden('Not owner')
        attrs = allowed_attrs(payload, 'update')
        apigk = request.gkadm_controller.update(gkid, attrs)
        return apigk
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='apigk_logo')
def apigk_logo(request):
    apigkid = request.matchdict['id']
    try:
        logo, updated = request.gkadm_controller.get_logo(apigkid)
        if logo is None:
            with open('data/default-apigk.png', 'rb') as fh:
                logo = fh.read()
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


@view_config(route_name='apigk_logo', request_method="POST", permission='scope_apigkadmin',
             renderer="json")
def upload_logo(request):
    userid = get_userid(request)
    apigkid = request.matchdict['id']
    owner = request.gkadm_controller.get_owner(apigkid)
    if owner and owner != userid:
        raise HTTPForbidden('Not owner')

    if 'logo' in request.POST:
        input_file = request.POST['logo'].file
    else:
        input_file = request.body_file_seekable
    input_file.seek(0)
    data = input_file.read()
    request.gkadm_controller.update_logo(apigkid, data)
    return 'OK'


@view_config(route_name='apigk_owner_clients', renderer='json', permission='scope_apigkadmin')
def apigk_owner_clients(request):
    userid = str(get_userid(request))
    ownerid = request.matchdict['ownerid']
    if ownerid != userid:
        raise HTTPForbidden('wrong owner')
    return request.gkadm_controller.get_gkowner_clients(ownerid)
