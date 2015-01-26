from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPConflict, HTTPUnauthorized, HTTPNotModified
from pyramid.response import Response
from .controller import ClientAdmController
from coreapis.utils import AlreadyExistsError, get_userid
import json
import uuid


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    maxrows = config.get_settings().get('clientadm_maxrows')
    cadm_controller = ClientAdmController(contact_points, keyspace, maxrows)
    config.add_settings(cadm_controller=cadm_controller)
    config.add_request_method(lambda r: r.registry.settings.cadm_controller, 'cadm_controller',
                              reify=True)
    config.add_route('get_client', '/clients/{id}', request_method='GET')
    config.add_route('list_clients', '/clients/', request_method='GET')
    config.add_route('add_client', '/clients/', request_method='POST')
    config.add_route('delete_client', '/clients/{id}', request_method='DELETE')
    config.add_route('update_client', '/clients/{id}', request_method='PATCH')
    config.add_route('client_logo', '/clients/{id}/logo')
    config.scan(__name__)


@view_config(route_name='list_clients', renderer='json', permission='scope_clientadmin')
def list_clients(request):
    userid = str(get_userid(request))
    params = {}
    for k, v in request.params.items():
        if k == 'owner' and v != str(userid):
            raise HTTPUnauthorized
        params[k] = v
    params['owner'] = userid
    return request.cadm_controller.list(params)


@view_config(route_name='get_client', renderer='json', permission='scope_clientadmin')
def get_client(request):
    userid = get_userid(request)
    clientid = uuid.UUID(request.matchdict['id'])
    try:
        client = request.cadm_controller.get(clientid)
        owner = client.get('owner', None)
        if owner and owner != userid:
            raise HTTPUnauthorized
    except KeyError:
        raise HTTPNotFound
    return client


def allowed_attrs(attrs, operation):
    protected_keys = ['created', 'owner', 'scopes', 'updated']
    if operation != 'add':
        protected_keys.append('id')
    return {k: v for k, v in attrs.items() if k not in protected_keys}


@view_config(route_name='add_client', renderer='json', request_method='POST',
             permission='scope_clientadmin')
def add_client(request):
    userid = get_userid(request)
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        attrs = allowed_attrs(payload, 'add')
        client = request.cadm_controller.add(attrs, userid)
        request.response.status = '201 Created'
        request.response.location = "{}{}".format(request.url, client['id'])
        return client
    except AlreadyExistsError:
        raise HTTPConflict("client with this id already exists")


@view_config(route_name='delete_client', renderer='json', permission='scope_clientadmin')
def delete_client(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise HTTPBadRequest
    owner = request.cadm_controller.get_owner(clientid)
    if owner and owner != userid:
        raise HTTPUnauthorized
    request.cadm_controller.delete(clientid)
    return Response(status='204 No Content',
                    content_type='application/json; charset={}'.format(request.charset))


@view_config(route_name='update_client', renderer='json', permission='scope_clientadmin')
def update_client(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        owner = request.cadm_controller.get_owner(clientid)
        if owner and owner != userid:
            raise HTTPUnauthorized
        attrs = allowed_attrs(payload, 'update')
        client = request.cadm_controller.update(clientid, attrs)
        return client
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='client_logo')
def client_logo(request):
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
    except:
        raise HTTPBadRequest
    try:
        logo, updated = request.cadm_controller.get_logo(clientid)
        if logo is None:
            with open('data/default-client.png', 'rb') as fh:
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


@view_config(route_name='client_logo', request_method="POST", permission='scope_clientadmin',
             renderer="json")
def upload_logo(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
    except:
        raise HTTPBadRequest
    owner = request.cadm_controller.get_owner(clientid)
    if owner and owner != userid:
        raise HTTPUnauthorized

    input_file = request.POST['logo'].file
    input_file.seek(0)
    data = input_file.read()
    request.cadm_controller.update_logo(clientid, data)
    return 'OK'
