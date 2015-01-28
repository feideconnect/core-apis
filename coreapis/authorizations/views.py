from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound
from pyramid.response import Response
from .controller import AuthorizationController
from coreapis.utils import get_userid
import uuid


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    authz_controller = AuthorizationController(contact_points, keyspace)
    config.add_settings(authz_controller=authz_controller)
    config.add_request_method(lambda r: r.registry.settings.authz_controller, 'authz_controller',
                              reify=True)
    config.add_route('list_authz', '/', request_method='GET')
    config.add_route('delete_authz', '/{id}', request_method='DELETE')
    config.scan(__name__)


@view_config(route_name="list_authz", permission="scope_authzinfo", renderer="json")
def list(request):
    userid = get_userid(request)
    return request.authz_controller.list(userid)


@view_config(route_name="delete_authz", permission="scope_authzinfo")
def delete(request):
    userid = get_userid(request)
    clientid = request.matchdict['id']
    try:
        clientid = uuid.UUID(clientid)
    except ValueError:
        raise HTTPNotFound
    request.authz_controller.delete(userid, clientid)
    return Response(status=204, content_type=False)
