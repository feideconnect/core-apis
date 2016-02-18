from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPForbidden
from .controller import GroupsController
from coreapis.utils import get_user, translation


def configure(config):
    groups_controller = GroupsController(config.get_settings())
    config.add_settings(groups_controller=groups_controller)
    config.add_request_method(lambda r: r.registry.settings.groups_controller,
                              'groups_controller', reify=True)
    config.add_route('my_groups_v1', '/v1/me/groups')
    config.add_route('my_groups', '/me/groups')
    config.add_route('my_membership_v1', '/v1/me/groups/{groupid}')
    config.add_route('my_membership', '/me/groups/{groupid}')
    config.add_route('group_v1', '/v1/groups/{groupid}')
    config.add_route('group', '/groups/{groupid}')
    config.add_route('group_logo_v1', '/v1/groups/{groupid}/logo')
    config.add_route('group_logo', '/groups/{groupid}/logo')
    config.add_route('group_members_v1', '/v1/groups/{groupid}/members')
    config.add_route('group_members', '/groups/{groupid}/members')
    config.add_route('groups_v1', '/v1/groups')
    config.add_route('groups', '/groups')
    config.add_route('grouptypes_v1', '/v1/grouptypes')
    config.add_route('grouptypes', '/grouptypes')
    config.scan(__name__)


@view_config(route_name='my_groups_v1', renderer='json', permission='scope_groups')
@translation
def my_groups_v1(request):
    user = get_user(request)
    if not user:
        raise HTTPForbidden('This resource requires a personal token')
    if request.params.get('showAll', 'false').lower() == 'true':
        show_all = True
    else:
        show_all = False
    return request.groups_controller.get_member_groups(user, show_all,
                                                       request.has_permission)


@view_config(route_name='my_groups', renderer='json', permission='scope_groups')
def my_groups(request):
    return my_groups_v1(request)


@view_config(route_name='my_membership_v1', renderer='json', permission='scope_groups')
@translation
def get_membership_v1(request):
    user = get_user(request)
    if not user:
        raise HTTPForbidden('This resource requires a personal token')
    groupid = request.matchdict['groupid']
    try:
        return request.groups_controller.get_membership(user, groupid,
                                                        request.has_permission)
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='my_membership', renderer='json', permission='scope_groups')
def get_membership(request):
    return get_membership_v1(request)


@view_config(route_name='group_v1', renderer='json', permission='scope_groups')
@translation
def get_group_v1(request):
    user = get_user(request)
    groupid = request.matchdict['groupid']
    try:
        return request.groups_controller.get_group(user, groupid,
                                                   request.has_permission)
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='group', renderer='json', permission='scope_groups')
def get_group(request):
    return get_group_v1(request)


@view_config(route_name='group_logo_v1', renderer='logo')
def group_logo_v1(request):
    groupid = request.matchdict['groupid']
    try:
        logo, updated = request.groups_controller.get_logo(groupid,
                                                           request.has_permission)
        return logo, updated, 'data/default-client.png'
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='group_logo', renderer='logo')
def group_logo(request):
    return group_logo_v1(request)


@view_config(route_name='group_members_v1', request_method="GET", permission='scope_groups',
             renderer="json")
def group_members_v1(request):
    user = get_user(request)
    groupid = request.matchdict['groupid']
    if request.params.get('showAll', 'false').lower() == 'true':
        show_all = True
    else:
        show_all = False
    try:
        return request.groups_controller.get_members(user, groupid, show_all,
                                                     request.has_permission)
    except KeyError:
        raise HTTPNotFound


@view_config(route_name='group_members', request_method="GET", permission='scope_groups',
             renderer="json")
def group_members(request):
    return group_members_v1(request)


@view_config(route_name='groups_v1', renderer='json', permission='scope_groups')
@translation
def list_groups_v1(request):
    user = get_user(request)
    query = request.params.get('query', None)
    return request.groups_controller.get_groups(user, query,
                                                request.has_permission)


@view_config(route_name='groups', renderer='json', permission='scope_groups')
def list_groups(request):
    return list_groups_v1(request)


@view_config(route_name='grouptypes_v1', renderer='json', permission='scope_groups')
@translation
def grouptypes_v1(request):
    return request.groups_controller.grouptypes()


@view_config(route_name='grouptypes', renderer='json', permission='scope_groups')
def grouptypes(request):
    return grouptypes_v1(request)
