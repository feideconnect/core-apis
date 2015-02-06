from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPUnauthorized, HTTPNotModified, HTTPConflict
from pyramid.response import Response
from .controller import AdHocGroupAdmController
from coreapis.utils import get_userid
import json
import uuid
import base64


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    maxrows = config.get_settings().get('adhocgroupadm_maxrows', 100)
    key = base64.b64decode(config.get_settings().get('profile_token_secret'))
    ahgroupadm_controller = AdHocGroupAdmController(contact_points, keyspace, maxrows, key)
    config.add_settings(ahgroupadm_controller=ahgroupadm_controller)
    config.add_request_method(lambda r: r.registry.settings.ahgroupadm_controller,
                              'ahgroupadm_controller', reify=True)
    config.add_route('group_memberships', '/memberships')
    config.add_route('get_group', '/{id}', request_method='GET')
    config.add_route('list_groups', '/', request_method='GET')
    config.add_route('add_group', '/', request_method='POST')
    config.add_route('delete_group', '/{id}', request_method='DELETE')
    config.add_route('update_group', '/{id}', request_method='PATCH')
    config.add_route('ahgroup_logo', '/{id}/logo')
    config.add_route('ahgroup_members', '/{id}/members')
    config.scan(__name__)


def allowed_attrs(attrs, operation):
    protected_keys = ['created', 'owner', 'scopes', 'updated', 'id']
    return {k: v for k, v in attrs.items() if k not in protected_keys}


def get_groupid(request):
    groupid = request.matchdict['id']
    try:
        groupid = uuid.UUID(groupid)
    except ValueError:
        raise HTTPNotFound
    return groupid


def check(request, permission):
    userid = get_userid(request)
    groupid = get_groupid(request)
    try:
        group = request.ahgroupadm_controller.get(groupid)
    except KeyError:
        raise HTTPNotFound
    if not request.ahgroupadm_controller.has_permission(group, userid, permission):
        raise HTTPUnauthorized
    return userid, group


@view_config(route_name='list_groups', renderer='json', permission='scope_adhocgroupadmin')
def list_groups(request):
    params = {}
    params['owner'] = get_userid(request)
    return request.ahgroupadm_controller.list(params)


@view_config(route_name='get_group', renderer='json', permission='scope_adhocgroupadmin')
def get_group(request):
    userid, group = check(request, "view")
    return group


@view_config(route_name='add_group', renderer='json', request_method='POST',
             permission='scope_adhocgroupadmin')
def add_group(request):
    userid = get_userid(request)
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    attrs = allowed_attrs(payload, 'add')
    group = request.ahgroupadm_controller.add(attrs, userid)
    request.response.status = 201
    request.response.location = "{}{}".format(request.url, group['id'])
    return group


@view_config(route_name='delete_group', renderer='json', permission='scope_adhocgroupadmin')
def delete_group(request):
    userid, group = check(request, "delete")
    request.ahgroupadm_controller.delete(group['id'])
    return Response(status=204, content_type=False)


@view_config(route_name='update_group', renderer='json', permission='scope_adhocgroupadmin')
def update_group(request):
    userid, group = check(request, "update")
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    attrs = allowed_attrs(payload, 'update')
    group = request.ahgroupadm_controller.update(group['id'], attrs)
    return group


@view_config(route_name='ahgroup_logo')
def group_logo(request):
    groupid = get_groupid(request)
    try:
        logo, updated = request.ahgroupadm_controller.get_logo(groupid)
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


@view_config(route_name='ahgroup_logo', request_method="POST", permission='scope_adhocgroupadmin',
             renderer="json")
def upload_logo(request):
    userid, group = check(request, "update")

    if 'logo' in request.POST:
        input_file = request.POST['logo'].file
    else:
        input_file = request.body_file_seekable
    input_file.seek(0)
    data = input_file.read()
    request.ahgroupadm_controller.update_logo(group['id'], data)
    return 'OK'


@view_config(route_name='ahgroup_members', request_method="GET", permission='scope_adhocgroupadmin',
             renderer="json")
def group_members(request):
    userid, group = check(request, "view_members")
    return request.ahgroupadm_controller.get_members(group['id'])


@view_config(route_name='ahgroup_members', request_method="PATCH",
             permission='scope_adhocgroupadmin', renderer="json")
def add_group_members(request):
    userid, group = check(request, "edit_members")
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    return request.ahgroupadm_controller.add_members(group['id'], payload)


@view_config(route_name='ahgroup_members', request_method="DELETE",
             permission='scope_adhocgroupadmin')
def del_group_members(request):
    userid, group = check(request, "edit_members")
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    request.ahgroupadm_controller.del_members(group['id'], payload)
    return Response(status=204, content_type=False)


@view_config(route_name='group_memberships', request_method="GET",
             permission='scope_adhocgroupadmin', renderer="json")
def get_group_memberships(request):
    userid = get_userid(request)
    return request.ahgroupadm_controller.get_memberships(userid, request.params.get('type', None),
                                                         request.params.get('status', None))


@view_config(route_name='group_memberships', request_method="DELETE",
             permission='scope_adhocgroupadmin', renderer="json")
def leave_groups(request):
    userid = get_userid(request)
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    return request.ahgroupadm_controller.leave_groups(userid, payload)


@view_config(route_name='group_memberships', request_method="PATCH",
             permission='scope_adhocgroupadmin', renderer="json")
def confirm_groups(request):
    userid = get_userid(request)
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        return request.ahgroupadm_controller.confirm_groups(userid, payload)
    except KeyError:
        raise HTTPConflict('Not member of group')
