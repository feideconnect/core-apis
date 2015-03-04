from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts, ValidationError, public_userinfo
from coreapis.peoplesearch.tokens import decrypt_token
import uuid
import valideer as V


def valid_member_type(mtype):
    if mtype == "member" or mtype == "admin":
        return True
    return False


def valid_member_id(mid):
    if not mid.startswith('p:'):
        return False
    p, uid = mid.split(':', 1)
    uuid.UUID(uid)
    return True


class AdHocGroupAdmController(CrudControllerBase):
    FILTER_KEYS = {
        'owner': {'sel':  'owner = ?',
                  'cast': lambda x: x},
    }
    schema = {
        '+name': 'string',
        'owner': V.AdaptTo(uuid.UUID),
        'id': V.AdaptTo(uuid.UUID),
        'created': V.AdaptBy(ts),
        'descr': V.Nullable('string'),
        'updated': V.AdaptBy(ts),
        '+public': 'boolean',
        'invitation_token': V.Nullable('string'),
    }
    member_schema = [{
        'token': V.String(min_length=24),
        'id': valid_member_id,
        'type': valid_member_type,
    }]
    del_member_schema = [valid_member_id]

    def __init__(self, contact_points, keyspace, maxrows, key, ps_controller):
        super(AdHocGroupAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('adhocgroupadm.AdHocGroupAdmController')
        self.key = key
        self.ps_controller = ps_controller

    def format_group(self, group):
        res = {}
        res.update(group)
        res['owner'] = public_userinfo(self.session.get_user_by_id(group['owner']))
        del res['invitation_token']
        return res

    def get(self, id):
        self.log.debug('Get group', id=id)
        group = self.session.get_group(id)
        return group

    def delete(self, groupid):
        self.log.debug('Delete group', id=groupid)
        for member in self.session.get_group_members(groupid):
            self.session.del_group_member(groupid, member['userid'])
        self.session.delete_group(groupid)

    def list(self, userid, params):
        groups = self.session.get_groups(['owner = ?'], [userid], self.maxrows)
        seen_groups = set([group['id'] for group in groups])
        memberships = self.session.get_group_memberships(userid, "admin", "normal", self.maxrows)
        for mem in memberships:
            groupid = mem['groupid']
            if not groupid in seen_groups:
                groups.append(self.get(groupid))
                seen_groups.add(groupid)
        return groups

    def add(self, item, userid):
        res = super(AdHocGroupAdmController, self).add(item, userid)
        self.add_member(res['id'], userid, 'admin', 'normal')
        return res

    def _insert(self, group):
        if not group.get('invitation_token', None):
            group['invitation_token'] = str(uuid.uuid4())
        return self.session.insert_group(group)

    def get_logo(self, groupid):
        return self.session.get_group_logo(groupid)

    def _save_logo(self, groupid, data, updated):
        self.session.save_logo('group', groupid, data, updated)

    def is_owner(self, group, userid):
        return group['owner'] == userid

    def is_admin(self, group, userid):
        try:
            membership = self.session.get_membership_data(group['id'], userid)
        except KeyError:
            return False
        if membership['type'] == 'admin' and membership['status'] == 'normal':
            return True
        return False

    def is_member(self, group, userid):
        try:
            membership = self.session.get_membership_data(group['id'], userid)
        except KeyError:
            return False
        if membership['type'] == 'admin' or membership['type'] == 'member':
            return True
        return False

    def is_owner_or_admin(self, group, userid):
        return self.is_owner(group, userid) or self.is_admin(group, userid)

    def is_owner_or_member(self, group, userid):
        return self.is_owner(group, userid) or self.is_member(group, userid)

    def has_permission(self, group, userid, permission):
        if permission == "update":
            return self.is_owner(group, userid)
        if permission == "delete":
            return self.is_owner(group, userid)
        if permission == "view":
            return self.is_owner_or_member(group, userid)
        if permission == "view_details":
            return self.is_owner_or_admin(group, userid)
        if permission == "view_members":
            return self.is_owner_or_member(group, userid)
        if permission == "edit_members":
            return self.is_owner_or_admin(group, userid)

    def get_members(self, groupid):
        res = []
        for member in self.session.get_group_members(groupid):
            user = public_userinfo(self.session.get_user_by_id(member['userid']))
            user['type'] = member['type']
            user['status'] = member['status']
            res.append(user)
        return res

    def add_member(self, groupid, userid, mtype, status):
        self.session.add_group_member(groupid, userid, mtype, status)

    def add_member_from_token(self, groupid, token, mtype):
        userid_sec = decrypt_token(token, self.key)
        try:
            userid = self.session.get_userid_by_userid_sec(userid_sec)
        except KeyError:
            userid = uuid.uuid4()
            p = 'p:{}'.format(uuid.uuid4())
            feideid = userid_sec.split(':', 1)[1]
            realm = feideid.split('@', 1)[1]
            person = self.ps_controller.get_user(feideid)
            source = 'ps:{}'.format(realm)
            name = {source: person['name']}
            userid_sec = set([userid_sec, p])
            self.session.insert_user(userid, None, name, None, None, source, userid_sec)
        self.add_member(groupid, userid, mtype, 'unconfirmed')

    def update_group_member(self, groupid, mid, mtype):
        try:
            userid = self.session.get_userid_by_userid_sec(mid)
            self.session.get_membership_data(groupid, userid)
        except KeyError as ex:
            raise ValidationError(str(ex))
        self.session.set_group_member_type(groupid, userid, mtype)

    def add_members(self, groupid, data):
        validator = V.parse(self.member_schema, additional_properties=False)
        try:
            adapted = validator.validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for member in adapted:
            if 'token' in member:
                self.add_member_from_token(groupid, member['token'], member['type'])
            elif 'id' in member:
                self.update_group_member(groupid, member['id'], member['type'])
            else:
                raise ValidationError('id or token must be given')

    def del_members(self, groupid, data):
        validator = V.parse(self.del_member_schema, additional_properties=False)
        try:
            adapted = validator.validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for member in adapted:
            userid = self.session.get_userid_by_userid_sec(member)
            self.session.del_group_member(groupid, userid)

    def get_memberships(self, userid, mtype=None, status=None):
        memberships = self.session.get_group_memberships(userid, mtype, status, self.maxrows)
        res = []
        for mem in memberships:
            try:
                group = self.get(mem['groupid'])
                mem['group'] = self.format_group(group)
                del mem['userid']
                res.append(mem)
            except KeyError:
                pass
        return res

    def leave_groups(self, userid, data):
        try:
            groups = V.parse([V.AdaptTo(uuid.UUID)]).validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for groupid in groups:
            self.session.del_group_member(groupid, userid)

    def confirm_groups(self, userid, data):
        try:
            groups = V.parse([V.AdaptTo(uuid.UUID)]).validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for groupid in groups:
            self.session.get_membership_data(groupid, userid)  # Raises KeyError if not member
        for groupid in groups:
            self.session.set_group_member_status(groupid, userid, 'normal')

    def invitation_token(self, groupid, userid, token):
        try:
            self.session.get_membership_data(groupid, userid)
            return None
        except KeyError:
            pass
        group = self.get(groupid)
        if group['invitation_token'] != token:
            return None
        self.add_member(groupid, userid, "member", "normal")
        return {
            'groupid': groupid,
            'type': 'member',
            'status': 'normal',
        }
