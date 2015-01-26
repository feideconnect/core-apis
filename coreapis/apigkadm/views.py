from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPConflict, HTTPUnauthorized, HTTPNotModified
from pyramid.response import Response
from .controller import APIGKAdmController
from coreapis.utils import AlreadyExistsError, get_userid
import json


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
    config.add_route('add_apigk', '/apigks/', request_method='POST')
    config.add_route('delete_apigk', '/apigks/{id}', request_method='DELETE')
    config.add_route('update_apigk', '/apigks/{id}', request_method='PATCH')
    config.add_route('apigk_logo', '/apigks/{id}/logo')
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
        if k == 'owner' and v != str(userid):
            raise HTTPUnauthorized
        params[k] = v
    params['owner'] = userid
    return request.gkadm_controller.list(request.params)


@view_config(route_name='get_apigk', renderer='json', permission='scope_apigkadmin')
def get_apigk(request):
    userid = get_userid(request)
    gkid = request.matchdict['id']
    try:
        apigk = request.gkadm_controller.get(gkid)
        owner = apigk.get('owner', None)
        if owner and owner != userid:
            raise HTTPUnauthorized
    except KeyError:
        raise HTTPNotFound()
    return apigk


@view_config(route_name='add_apigk', renderer='json', request_method='POST',
             permission='scope_apigkadmin')
def add_apigk(request):
    userid = get_userid(request)
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
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
        raise HTTPUnauthorized
    request.gkadm_controller.delete(gkid)
    return Response(status=204,
                    content_type='application/json; charset={}'.format(request.charset))


@view_config(route_name='update_apigk', renderer='json', permission='scope_apigkadmin')
def update_apigk(request):
    userid = get_userid(request)
    gkid = request.matchdict['id']
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        owner = request.gkadm_controller.get_owner(gkid)
        if owner and owner != userid:
            raise HTTPUnauthorized
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
            with open('data/default-logo.png', 'rb') as fh:
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
        raise HTTPUnauthorized

    input_file = request.POST['logo'].file
    input_file.seek(0)
    data = input_file.read()
    request.gkadm_controller.update_logo(apigkid, data)
    return 'OK'
