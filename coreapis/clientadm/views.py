from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPConflict, HTTPUnauthorized
from pyramid.response import Response
from .controller import ClientAdmController
from coreapis.utils import AlreadyExistsError
import json

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
    config.scan(__name__)

def get_userid(request):
    try:
        return request.environ['FC_USER']['userid']
    except:
        return None

@view_config(route_name='list_clients', renderer='json', permission='scope_clientadmin')
def list_clients(request):
    userid = str(get_userid(request))
    params = {}
    for k, v in request.params.items():
        if k == 'owner' and v != str(userid):
            raise HTTPUnauthorized
        params[k] = v
    params['owner'] = userid
    return request.cadm_controller.get_clients(params)

@view_config(route_name='get_client', renderer='json', permission='scope_clientadmin')
def get_client(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    try:
        client = request.cadm_controller.get_client(clientid)
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
    return {k:v for k, v in attrs.items() if k not in protected_keys}

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
        client = request.cadm_controller.add_client(attrs, userid)
        request.response.status = '201 Created'
        request.response.location = "{}{}".format(request.url, client['id'])
        return client
    except AlreadyExistsError:
        raise HTTPConflict("client with this id already exists")
    except:
        raise HTTPBadRequest

@view_config(route_name='delete_client', renderer='json', permission='scope_clientadmin')
def delete_client(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    owner = request.cadm_controller.get_owner(clientid)
    if owner and owner != userid:
        raise HTTPUnauthorized
    try:
        request.cadm_controller.delete_client(clientid)
        return Response(status='204 No Content',
                        content_type='application/json; charset={}'.format(request.charset))
    except ValueError: # clientid not a valid UUID
        raise HTTPBadRequest

@view_config(route_name='update_client', renderer='json', permission='scope_clientadmin')
def update_client(request):
    clientid = request.matchdict['id']
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        attrs = allowed_attrs(payload, 'update')
        client = request.cadm_controller.update_client(clientid, attrs)
        return client
    except KeyError:
        raise HTTPNotFound
    except:
        raise HTTPBadRequest
