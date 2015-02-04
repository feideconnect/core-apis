from coreapis.utils import LogWrapper
from eventlet.greenpool import GreenPool, GreenPile
from eventlet.timeout import Timeout
import traceback
from paste.deploy.util import lookup_object

BACKEND_CONFIG_KEY = 'groups_backend_'


class GroupsController(object):

    def __init__(self, config):
        maxrows = config.get_settings().get('groups_maxrows', 100)
        self.maxrows = maxrows
        self.log = LogWrapper('groups.GroupsController')
        self.backends = {}
        self.pool = GreenPool()
        self.timeout = int(config.get_settings().get('groups_timeout_backend', '3000')) / 1000
        for key, value in config.get_settings().items():
            if key.startswith(BACKEND_CONFIG_KEY):
                prefix = key[len(BACKEND_CONFIG_KEY):]
                self.backends[prefix] = lookup_object(value)(prefix, maxrows, config)

    def _backend(self, groupid):
        if not ':' in groupid:
            raise KeyError('Malformed group id')
        grouptype, subid = groupid.split(':', 1)
        if not grouptype in self.backends:
            raise KeyError('bad group id')
        return self.backends[grouptype]

    def _backend_call(self, method, *args, **kwargs):
        with Timeout(self.timeout):
            try:
                return method(*args, **kwargs)
            except Timeout:
                self.log.warn("Timeout in group backend", backend=str(method.__self__),
                              method=method.__name__)
            except:
                exception = traceback.format_exc()
                self.log.error('unhandled exception in group backend', exception=exception)
        return []

    def _call_backends(self, func, *args, **kwargs):
        pile = GreenPile(self.pool)
        for backend in self.backends.values():
            pile.spawn(self._backend_call, func(backend), *args, **kwargs)
        for result in pile:
            if result:
                for value in result:
                    yield value

    def get_member_groups(self, userid, show_all):
        return list(self._call_backends(lambda x: x.get_member_groups, userid, show_all))

    def get_membership(self, userid, groupid):
        return self._backend(groupid).get_membership(userid, groupid)

    def get_group(self, userid, groupid):
        return self._backend(groupid).get_group(userid, groupid)

    def get_logo(self, groupid):
        return self._backend(groupid).get_logo(groupid)

    def get_members(self, userid, groupid, show_all):
        return self._backend(groupid).get_members(userid, groupid, show_all)

    def get_groups(self, userid, query):
        return list(self._call_backends(lambda x: x.get_groups, userid, query))

    def grouptypes(self):
        types = {}
        for backend in self.backends.values():
            for gtype in backend.grouptypes():
                types[gtype['id']] = gtype
        return list(types.values())
