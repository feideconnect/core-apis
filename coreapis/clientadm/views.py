from pyramid.view import view_config
from pyramid.exceptions import HTTPNotFound
from .controller import ClientAdmController


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    maxrows = config.get_settings().get('clientadm_maxrows')
    cadm_controller = ClientAdmController(contact_points, keyspace, maxrows)
    config.add_settings(cadm_controller=cadm_controller)
    config.add_request_method(lambda r: r.registry.settings.cadm_controller, 'cadm_controller',
                              reify=True)
    config.add_route('list_clients', '/clients/')
    config.add_route('get_client', '/clients/{id}')
    config.scan(__name__)

@view_config(route_name='list_clients', renderer='json', permission='scope_clientadm')
def list_clients(request):
    return request.cadm_controller.get_clients(request.params)

@view_config(route_name='get_client', renderer='json', permission='scope_clientadm')
def get_client(request):
    id = request.matchdict['id']
    client = request.cadm_controller.get_client(id)
    if not client:
        raise HTTPNotFound()
    return client
