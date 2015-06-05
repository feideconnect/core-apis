import functools
from coreapis.utils import LogWrapper, get_feideids, failsafe, translatable, parse_datetime
from coreapis.cache import Cache
from coreapis import cassandra_client
from . import BaseBackend
from eventlet.greenpool import GreenPool
import requests


class FsBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(FsBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.fsbackend')
        self.timer = config.get_settings().get('timer')
        self.base_url = config.get_settings().get('fs_base_url')
        self.fs_user = config.get_settings().get('fs_username')
        self.fs_pass = config.get_settings().get('fs_password')
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)
        self.org_enabled = Cache(300)

    def is_org_enabled(self, realm):
        return self.org_enabled.get(realm, functools.partial(self.session.org_use_fs_groups, realm))

    def get_members(self, user, groupid, show_all):
        return []

    def _get_member_groups(self, show_all, feideid):
        realm = feideid.split('@', 1)[1]
        if not self.is_org_enabled(realm):
            self.log.debug('fs groups disabled for organization', realm=realm)
            return []
        url = '{}/feide:{}/groups'.format(self.base_url, feideid)
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
