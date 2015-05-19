from coreapis.utils import LogWrapper, get_feideids, failsafe, translatable
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

    def get_members(self, user, groupid, show_all):
        return []

    def _get_member_groups(self, feideid):
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
