from pyramid.view import view_config
from .controller import UserInfoController
from coreapis.utils import get_user


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    ldap_controller = config.get_settings().get('ldap_controller')
    userinfo_controller = UserInfoController(contact_points, keyspace, ldap_controller)
    config.add_settings(userinfo_controller=userinfo_controller)
    config.add_request_method(lambda r: r.registry.settings.userinfo_controller,
                              'userinfo_controller', reify=True)
    config.add_route('get_userinfo', '/userinfo')
    config.scan(__name__)


@view_config(route_name='get_userinfo', request_method="GET",
             permission='scope_userinfo', renderer="json")
def get_userinfo(request):
    user = get_user(request)
    return request.userinfo_controller.get_userinfo(user, request.has_permission)
