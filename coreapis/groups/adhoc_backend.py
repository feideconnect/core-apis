from functools import partial
import uuid

from coreapis import cassandra_client
from coreapis.utils import LogWrapper, public_userinfo, failsafe, translatable
from . import BaseBackend, Pool

ADHOC_TYPE = 'voot:ad-hoc'


def basic(group, membership):
    if group['owner'] == membership['userid']:
        return 'owner'
    if membership['type'] == 'admin':
        return 'admin'
    return 'member'


def format_membership(group, membership):
    return {
        'basic': basic(group, membership),
    }


def query_match(query, group):
    if not query:
        return True
    if query in group['displayName']:
        return True
    if query in group.get('description', ''):
        return True
    return False


class AdHocGroupBackend(BaseBackend):
    def __init__(self, prefix, maxrows, settings):
        super(AdHocGroupBackend, self).__init__(prefix, maxrows, settings)
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.timer = settings.get('timer')
        self.session = cassandra_client.Client(contact_points, keyspace, True, authz=authz)
        self.session.timer = self.timer
        self.log = LogWrapper('groups.adhocgroupbackend')

    def _intid(self, groupid):
        intid = super(AdHocGroupBackend, self)._intid(groupid)
        try:
            intid = uuid.UUID(intid)
        except ValueError:
            raise KeyError('Bad group id')
        return intid

    def format_group(self, group, membership):
        data = {
            'id': self._groupid(str(group['id'])),
            'displayName': group['name'],
            'type': ADHOC_TYPE,
        }
        if group.get('public', False):
            data['public'] = True
        if group.get('descr', ''):
            data['description'] = group['descr']
        if membership:
            data['membership'] = format_membership(group, membership)
        return data

    def _get(self, userid, groupid):
        intgroupid = self._intid(groupid)
        group = self.session.get_group(intgroupid)
        try:
            membership = self.session.get_membership_data(intgroupid, userid)
            return group, membership
        except KeyError:
            if not group['public'] and not group['owner'] == userid:
                raise KeyError("Group access denied")
            return group, None

    def get_membership(self, user, groupid):
        userid = user['userid']
        group, membership = self._get(userid, groupid)
        if membership is None:
            raise KeyError("Not member of group")
        return dict(basic=basic(group, membership))

    def get_group(self, user, groupid):
        userid = user['userid']
        group, _ = self._get(userid, groupid)
        return self.format_group(group, None)

    def _handle_member(self, group, member):
        if member['status'] not in ('normal', 'unconfirmed'):
            tmpl = 'skipping group with unhandled membership status {}'
            self.log.debug(tmpl.format(member['status']))
            return None
        user = self.session.get_user_by_id(member['userid'])
        return {
            'membership': format_membership(group, member),
            'name': public_userinfo(user)['name']
        }

    def get_members(self, user, groupid, show_all, include_member_ids):
        userid = user['userid']
        group, membership = self._get(userid, groupid)
        if membership is None:
            raise KeyError("Not member of group")
        member_ids = self.session.get_group_members(group['id'])
        pool = Pool()
        members = pool.imap(failsafe(partial(self._handle_member, group)), member_ids)
        return [member for member in members if member]

    def get_member_groups(self, user, show_all):
        userid = user['userid']
        pool = Pool()
        membership_list = self.session.get_group_memberships(userid, None, None, self.maxrows)
        memberships = {membership['groupid']: membership for membership in membership_list}
        groups = pool.imap(failsafe(self.session.get_group), memberships.keys())
        return [self.format_group(g, memberships[g['id']]) for g in groups if g]

    def get_groups(self, user, query):
        result = []
        self.log.debug("Getting ad hoc groups")
        seen_groupids = set()
        for group in self.get_member_groups(user, True):
            if query_match(query, group):
                seen_groupids.add(group['id'])
                result.append(group)
        for group in self.session.get_groups(['public = ?'], [True], self.maxrows):
            formatted = self.format_group(group, None)
            if (query_match(query, formatted) and
                    formatted['id'] not in seen_groupids):
                seen_groupids.add(formatted['id'])
                result.append(formatted)
        return result

    def grouptypes(self):
        return [
            {
                'id': ADHOC_TYPE,
                "displayName": translatable({
                    "en": "Ad-Hoc Group",
                    "nb": "Ad-Hoc gruppe",
                })
            }
        ]
