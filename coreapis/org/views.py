from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound
from .controller import OrgController
from coreapis.utils import pick_lang


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('peoplesearch.cache_keyspace')
    timer = config.get_settings().get('timer')
    org_controller = OrgController(contact_points, keyspace, timer)
    config.add_settings(org_controller=org_controller)
    config.add_request_method(lambda r: r.registry.settings.org_controller, 'org_controller',
                              reify=True)
    config.add_route('org', '/{realm}')
    config.add_route('orgs', '/')
    config.scan(__name__)


@view_config(route_name='org', request_method='GET', renderer='json')
def get_org(request):
    realm = request.matchdict['realm']
    try:
        data = request.org_controller.show_org(realm)
        data = pick_lang(request, data)
        return data
    except KeyError:
        raise HTTPNotFound('No org with realm {} was found'.format(realm))


@view_config(route_name='orgs', request_method='GET', renderer='json')
def list_org(request):
    data = request.org_controller.list_orgs()
    data = pick_lang(request, data)
    return data
