import functools

import eventlet
from eventlet.greenpool import GreenPool
requests = eventlet.import_patched('requests')

from coreapis.utils import LogWrapper, get_feideids, failsafe, translatable, parse_datetime
from coreapis.cache import Cache
from coreapis import cassandra_client
from . import BaseBackend


class FsBackend(BaseBackend):
    def __init__(self, prefix, maxrows, settings):
        super(FsBackend, self).__init__(prefix, maxrows, settings)
        self.log = LogWrapper('groups.fsbackend')
        self.timer = settings.get('timer')
        self.base_url = settings.get('fs_base_url')
        self.fs_user = settings.get('fs_username')
        self.fs_pass = settings.get('fs_password')
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.session = cassandra_client.Client(contact_points, keyspace, True, authz=authz)
        self.org_enabled = Cache(300)

    def is_org_enabled(self, realm):
        return self.org_enabled.get(realm, functools.partial(self.session.org_use_fs_groups, realm))

    def get_members(self, user, groupid, show_all, include_member_ids):
        gid_parts = groupid.split(':')
        if len(gid_parts) < 4:
            raise KeyError('invalid group id')
        realm = gid_parts[3]
        if not self.is_org_enabled(realm):
            self.log.debug('fs groups disabled for organization', realm=realm)
            raise KeyError('not enabled')
        url = '{}/group/{}/members'.format(self.base_url, 'fc:' + self._intid(groupid))
        response = requests.get(url, auth=(self.fs_user, self.fs_pass))
        response.raise_for_status()
        response_data = response.json()
        found = False
        for entry in response_data:
            if entry.get('userid', None) in user['userid_sec']:
                found = True
                break
        if not found:
            self.log.debug('user is not member of group, refusing member list',
                           group=groupid, userid=user['userid'])
            raise KeyError('not member')
        retval = []
        for entry in response_data:
            output = {}
            for key in ('name', 'membership'):
                if key in entry:
                    output[key] = entry[key]
            if output:
                retval.append(output)
        return retval

    def _get_member_groups(self, show_all, feideid):
        realm = feideid.split('@', 1)[1]
        if not self.is_org_enabled(realm):
            self.log.debug('fs groups disabled for organization', realm=realm)
            return []
        url = '{}/user/feide:{}/groups'.format(self.base_url, feideid)
        self.log.debug('requesting fs resource', url=url)
        with self.timer.time('fs.get_member_groups'):
            response = requests.get(url, auth=(self.fs_user, self.fs_pass))
            self.log.debug('got response from fs', status_code=response.status_code,
                           content_type=response.headers['content-type'])
        response.raise_for_status()
        result = []
        for group in response.json():
            if not 'membership' in group:
                continue
            if not group.get('id', '').startswith('fc:'):
                self.log.debug('Received invalid id from fs', id=group.get('id', '<field missing>'))
                continue
            group['id'] = self._groupid(group['id'].split(':', 1)[1])
            if 'parent' in group:
                if not group['parent'].startswith('fc:'):
                    self.log.debug('Received unexpected parent in group from fs',
                                   id=group['id'], parent=group['parent'])
                elif not group['parent'].startswith('fc:org'):
                    group['parent'] = self._groupid(group['parent'].split(':', 1)[1])
            membership = group['membership']
            if not show_all and not membership.get('active'):
                continue
            if 'displayName' in group:
                group['displayName'] = translatable(group['displayName'])
            if 'displayName' in membership:
                membership['displayName'] = translatable(membership['displayName'])
            if 'notAfter' in membership:
                membership['notAfter'] = parse_datetime(membership['notAfter'])
            if 'notBefore' in membership:
                membership['notBefore'] = parse_datetime(membership['notBefore'])
            result.append(group)
        return result

    def get_member_groups(self, user, show_all):
        result = []
        pool = GreenPool()
        func = failsafe(functools.partial(self._get_member_groups, show_all))
        for res in pool.imap(func, get_feideids(user)):
            if res:
                result.extend(res)
        return result

    def grouptypes(self):
        return [
            {
                'id': 'fc:emne',
                'displayName': translatable({
                    'nb': 'Emne',
                    'en': 'Subject',
                }),
            },
            {
                'id': 'fc:klasse',
                'displayName': translatable({
                    'nb': 'Klasse',
                    'en': 'Class',
                }),
            },
            {
                'id': 'fc:kull',
                'displayName': translatable({
                    'nb': 'Kull',
                    'en': 'Year',
                }),
            },
            {
                'id': 'fc:prg',
                'displayName': translatable({
                    'nb': 'Program',
                    'en': 'Program',
                }),
            },
        ]
