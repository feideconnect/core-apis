from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPUnauthorized, HTTPNotModified
from pyramid.response import Response
from .controller import GroupsController
from coreapis.utils import get_userid


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    maxrows = config.get_settings().get('groups_maxrows', 100)
    groups_controller = GroupsController(contact_points, keyspace, maxrows)
    config.add_settings(groups_controller=groups_controller)
    config.add_request_method(lambda r: r.registry.settings.groups_controller,
                              'groups_controller', reify=True)
    config.add_route('my_groups', '/me/groups')
    config.add_route('my_membership', '/me/groups/{groupid}')
    config.add_route('group', '/groups/{groupid}')
    config.add_route('group_logo', '/groups/{groupid}/logo')
    config.add_route('group_members', '/groups/{groupid}/members')
    config.add_route('groups', '/groups')
    config.add_route('grouptypes', '/grouptypes')
    config.scan(__name__)


@view_config(route_name='my_groups', renderer='json', permission='scope_groups')
def my_groups(request):
    userid = get_userid(request)
    if not userid:
        raise HTTPUnauthorized
    if request.params.get('showAll', 'false').lower() == 'true':
        show_all = True
    else:
        show_all = False
    return request.groups_controller.get_member_groups(userid, show_all)


@view_config(route_name='my_membership', renderer='json', permission='scope_groups')
def get_membership(request):
    userid = get_userid(request)
    if not userid:
        raise HTTPUnauthorized
    groupid = request.matchdict['groupid']
    return request.groups_controller.get_membership(userid, groupid)


@view_config(route_name='group', renderer='json', permission='scope_groups')
def get_group(request):
    userid = get_userid(request)
    groupid = request.matchdict['groupid']
    return request.groups_controller.get_group(userid, groupid)


@view_config(route_name='group_logo')
def group_logo(request):
    groupid = request.matchdict['groupid']
    try:
        logo, updated = request.groups_controller.get_logo(groupid)
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


@view_config(route_name='group_members', request_method="GET", permission='scope_groups',
             renderer="json")
def group_members(request):
    userid = get_userid(request)
    groupid = request.matchdict['groupid']
    if request.params.get('showAll', 'false').lower() == 'true':
        show_all = True
    else:
        show_all = False
    return request.groups_controller.get_members(userid, groupid, show_all)


@view_config(route_name='groups', renderer='json', permission='scope_groups')
def list_groups(request):
    userid = get_userid(request)
    query = request.params.get('query', None)
    return request.groups_controller.get_groups(userid, query)


@view_config(route_name='grouptypes', renderer='json', permission='scope_groups')
def grouptypes(request):
    return request.groups_controller.grouptypes()
