import time
import functools
from coreapis.utils import LogWrapper, get_feideids, failsafe, translatable
from coreapis import cassandra_client
from . import BaseBackend
from eventlet.greenpool import GreenPool
import requests


class Cache(object):
    def __init__(self, expiry):
        self.log = LogWrapper('groups.fs_backend.cache')
        self.data = dict()
        self.expiry = expiry

    def _set(self, key, value):
        self.data[key] = (time.time(), value)
        return value

    def _update(self, key, getter):
        return self._set(key, getter())

    def get(self, key, getter):
        if not key in self.data:
            self.log.debug('cache miss', key=key)
            return self._update(key, getter)
        ts, cached = self.data.get(key)
        if ts + self.expiry < time.time():
            self.log.debug('cache expired', key=key)
            return self._update(key, getter)
        self.log.debug('cache hit', key=key)
        return cached


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

    def _get_member_groups(self, feideid):
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
        result = response.json()
        for group in result:
            if 'displayName' in group:
                group['displayName'] = translatable(group['displayName'])
            if 'membership' in group and 'displayName' in group['membership']:
                group['membership']['displayName'] = translatable(group['membership']['displayName'])
        return result

    def get_member_groups(self, user, show_all):
        result = []
        pool = GreenPool()
        for res in pool.imap(failsafe(self._get_member_groups), get_feideids(user)):
            if res:
                result.extend(res)
        return result

    def grouptypes(self):
        return [
        ]
