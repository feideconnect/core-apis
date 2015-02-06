from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts, ValidationError, public_userinfo
from coreapis.peoplesearch.tokens import decrypt_token
import uuid
import valideer as V


def valid_member_type(mtype):
    if mtype == "normal" or mtype == "admin":
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
    }
    member_schema = [{
        '+token': 'string',
        'type': valid_member_type,
    }]
    del_member_schema = [valid_member_id]

    def __init__(self, contact_points, keyspace, maxrows, key):
        super(AdHocGroupAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('adhocgroupadm.AdHocGroupAdmController')
        self.key = key

    def get(self, id):
        self.log.debug('Get group', id=id)
        group = self.session.get_group(id)
        return group

    def delete(self, id):
        self.log.debug('Delete group', id=id)
        self.session.delete_group(id)

    def _list(self, selectors, values, maxrows):
        return self.session.get_groups(selectors, values, maxrows)

    def add(self, item, userid):
        res = super(AdHocGroupAdmController, self).add(item, userid)
        self.add_member(res['id'], userid, 'admin', 'normal')
        return res

    def _insert(self, group):
        return self.session.insert_group(group)

    def get_logo(self, groupid):
        return self.session.get_group_logo(groupid)

    def _save_logo(self, groupid, data, updated):
        self.session.save_logo('group', groupid, data, updated)

    def is_owner(self, group, userid):
        return group['owner'] == userid

    def is_admin(self, group, userid):
        pass

    def is_owner_or_admin(self, group, userid):
        return self.is_owner(group, userid) or self.is_admin(group, userid)

    def has_permission(self, group, userid, permission):
        if permission == "update":
            return self.is_owner(group, userid)
        if permission == "delete":
            return self.is_owner(group, userid)
        if permission == "view":
            return self.is_owner_or_admin(group, userid)
        if permission == "view_members":
            return self.is_owner_or_admin(group, userid)
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

    def add_members(self, groupid, data):
        validator = V.parse(self.member_schema, additional_properties=False)
        try:
            adapted = validator.validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for member in adapted:
            userid_sec = decrypt_token(member['token'], self.key)
            user = self.session.get_user_by_userid_sec(userid_sec)
            self.add_member(groupid, user['userid'], member['type'], 'unconfirmed')

    def del_members(self, groupid, data):
        validator = V.parse(self.del_member_schema, additional_properties=False)
        try:
            adapted = validator.validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for member in adapted:
            user = self.session.get_user_by_userid_sec(member)
            self.session.del_group_member(groupid, user['userid'])

    def get_memberships(self, userid, mtype=None, status=None):
        memberships = self.session.get_group_memberships(userid, mtype, status, self.maxrows)
        res = []
        for mem in memberships:
            try:
                group = self.get(mem['groupid'])
                mem['group'] = group
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
            membership = self.session.get_membership_data(groupid, userid)
            if len(membership) == 0:
                raise KeyError("Not member")
        for groupid in groups:
            self.session.set_group_member_status(groupid, userid, 'normal')
