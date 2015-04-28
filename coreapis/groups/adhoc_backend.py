from coreapis import cassandra_client
from coreapis.utils import LogWrapper, public_userinfo, failsafe, translatable
from . import BaseBackend
import uuid
from eventlet.greenpool import GreenPile, GreenPool

adhoc_type = 'voot:ad-hoc'


def basic(group, membership):
    if group['owner'] == membership['userid']:
        return 'owner'
    elif membership['type'] == 'admin':
        return 'admin'
    else:
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
    def __init__(self, prefix, maxrows, config):
        super(AdHocGroupBackend, self).__init__(prefix, maxrows, config)
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)
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
            'type': adhoc_type,
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
        group, membership = self._get(userid, groupid)
        return self.format_group(group, None)

    def get_members(self, user, groupid, show_all):
        userid = user['userid']
        group, membership = self._get(userid, groupid)
        if membership is None:
            raise KeyError("Not member of group")
        members = self.session.get_group_members(group['id'])
        result = []
        for member in members:
            try:
                if member['status'] not in ('normal', 'unconfirmed'):
                    self.log.debug('skipping group with unhandled membership status {}'.format(member['status']))
                    continue
                user = self.session.get_user_by_id(member['userid'])
                entry = {
                    'membership': format_membership(group, member),
                    'name': public_userinfo(user)['name']
                }
                result.append(entry)
            except KeyError:
                pass
        return result

    def get_member_groups(self, user, show_all):
        userid = user['userid']
        pool = GreenPool()
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
            if query_match(query, formatted):
                if formatted['id'] not in seen_groupids:
                    seen_groupids.add(formatted['id'])
                    result.append(formatted)
        return result

    def grouptypes(self):
        return [
            {
                'id': adhoc_type,
                "displayName": translatable({
                    "en": "Ad-Hoc Group",
                    "nb": "Ad-Hoc gruppe",
                })
            }
        ]
