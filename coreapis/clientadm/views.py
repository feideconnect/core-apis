from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPConflict
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
    config.scan(__name__)

@view_config(route_name='list_clients', renderer='json', permission='scope_clientadm')
def list_clients(request):
    return request.cadm_controller.get_clients(request.params)

@view_config(route_name='get_client', renderer='json', permission='scope_clientadm')
def get_client(request):
    id = request.matchdict['id']
    try:
        client = request.cadm_controller.get_client(id)
    except KeyError:
        raise HTTPNotFound
    return client

@view_config(route_name='add_client', renderer='json', request_method='POST', permission='scope_clientadm')
def add_client(request):
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        client = request.cadm_controller.add_client(payload)
        request.response.status = '201 Created'
        request.response.location = "{}{}".format(request.url, client['id'])
        return client
    except AlreadyExistsError:
        raise HTTPConflict("client with this id already exists")
    except:
        raise HTTPBadRequest

@view_config(route_name='delete_client', renderer='json', permission='scope_clientadm')
def delete_client(request):
    id = request.matchdict['id']
    try:
        request.cadm_controller.delete_client(id)
        return Response(status = '204 No Content',
                        content_type='application/json; charset={}'.format(request.charset))
    except ValueError: # id not a valid UUID
        raise HTTPBadRequest
