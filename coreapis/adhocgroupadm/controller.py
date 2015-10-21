from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts, ValidationError, public_userinfo, ResourceError
from coreapis.peoplesearch.tokens import decrypt_token
import uuid
import valideer as V
import base64


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

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        maxrows = settings.get('adhocgroupadm_maxrows', 100)
        key = base64.b64decode(settings.get('profile_token_secret'))
        ps_controller = settings.get('ps_controller')
        max_add_members = int(settings.get('adhocgroupadm_max_add_members', '50'))
        super(AdHocGroupAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('adhocgroupadm.AdHocGroupAdmController')
        self.key = key
        self.ps_controller = ps_controller
        self.max_add_members = max_add_members

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
        self.add_member(res['id'], userid, 'admin', 'normal', None)
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
            added_by = member.get('added_by', None)
            if added_by:
                user['added_by'] = public_userinfo(self.session.get_user_by_id(added_by))
            res.append(user)
        return res

    def add_member(self, groupid, memberid, mtype, status, added_by):
        self.session.add_group_member(groupid, memberid, mtype, status, added_by)

    def add_member_from_token(self, groupid, token, mtype, callerid):
        memberid_sec = decrypt_token(token, self.key)
        try:
            memberid = self.session.get_userid_by_userid_sec(memberid_sec)
        except KeyError:
            memberid = uuid.uuid4()
            p = 'p:{}'.format(uuid.uuid4())
            feideid = memberid_sec.split(':', 1)[1]
            realm = feideid.split('@', 1)[1]
            person = self.ps_controller.get_user(feideid)
            source = 'ps:{}'.format(realm)
            name = {source: person['name']}
            memberid_sec = set([memberid_sec, p])
            self.session.insert_user(memberid, None, name, None, None, source, memberid_sec)
        added_by = None
        if callerid != memberid:
            added_by = callerid
        self.add_member(groupid, memberid, mtype, 'unconfirmed', added_by)

    def update_group_member(self, groupid, mid, mtype):
        try:
            userid = self.session.get_userid_by_userid_sec(mid)
            self.session.get_membership_data(groupid, userid)
        except KeyError as ex:
            raise ValidationError(str(ex))
        self.session.set_group_member_type(groupid, userid, mtype)

    def add_members(self, groupid, data, callerid):
        validator = V.parse(self.member_schema, additional_properties=False)
        try:
            adapted = validator.validate(data)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        members = len(self.session.get_group_members(groupid))
        to_add = len([member for member in adapted if 'token' in member])
        if to_add > 0 and to_add + members > self.max_add_members:
            raise ResourceError("Can not add more than {} members".format(self.max_add_members))
        for member in adapted:
            if 'token' in member:
                self.add_member_from_token(groupid, member['token'], member['type'], callerid)
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
        self.add_member(groupid, userid, "member", "normal", None)
        return {
            'groupid': groupid,
            'type': 'member',
            'status': 'normal',
        }
