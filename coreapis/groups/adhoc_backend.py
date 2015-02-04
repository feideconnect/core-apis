from coreapis import cassandra_client
from coreapis.utils import LogWrapper, public_userinfo
from . import BaseBackend
import uuid

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


class AdHocGroupBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(AdHocGroupBackend, self).__init__(prefix, maxrows)
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)
        self.log = LogWrapper('groups.adhocgroupbackend')

    def _intid(self, groupid):
        if not ':' in groupid:
            raise KeyError('Bad group id')
        try:
            intid = uuid.UUID(groupid.split(':', 1)[1])
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
        membership = self.session.get_membership_data(intgroupid, userid)
        if len(membership) == 0:
            if not group['public'] and not group['owner'] == userid:
                raise KeyError("Group access denied")
            membership = None
        else:
            membership = membership[0]
        return group, membership

    def get_membership(self, userid, groupid):
        group, membership = self._get(userid, groupid)
        if membership is None:
            raise KeyError("Not member of group")
        return dict(basic=basic(group, membership))

    def get_group(self, userid, groupid):
        group, membership = self._get(userid, groupid)
        return self.format_group(group, None)

    def get_members(self, userid, groupid, show_all):
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

    def get_member_groups(self, userid, show_all):
        for membership in self.session.get_group_memberships(userid, None, None, self.maxrows):
            group = self.session.get_group(membership['groupid'])
            yield self.format_group(group, membership)

    def get_groups(self, userid, query):
        seen_groupids = set()
        for group in self.get_member_groups(userid, True):
            if query is None or query in group['displayName'] or ('description' in group and query in group['description']):
                seen_groupids.add(group['id'])
                yield group
        for group in self.session.get_groups(['public = ?'], [True], self.maxrows):
            formatted = self.format_group(group, None)
            if query is None or query in formatted['displayName'] or ('description' in formatted and query in formatted['description']):
                if formatted['id'] not in seen_groupids:
                    seen_groupids.add(formatted['id'])
                    yield formatted

    def grouptypes(self):
        return [
            {
                'id': adhoc_type,
                "displayName": {
                    "en": "Ad-Hoc Group",
                    "nb": "Ad-Hoc gruppe",
                }
            }
        ]
