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
        self.timer = config.get_settings().get('timer')
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
        backend = method.__self__.prefix
        call = method.__name__
        with self.timer.time('groups.{}.{}'.format(call, backend)):
            with Timeout(self.timeout):
                try:
                    return method(*args, **kwargs)
                except Timeout:
                    self.log.warn("Timeout in group backend", backend=backend,
                                  method=call)
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

    def get_member_groups(self, user, show_all):
        with self.timer.time('groups.get_member_groups'):
            return list(self._call_backends(lambda x: x.get_member_groups, user, show_all))

    def get_membership(self, user, groupid):
        return self._backend(groupid).get_membership(user, groupid)

    def get_group(self, user, groupid):
        return self._backend(groupid).get_group(user, groupid)

    def get_logo(self, groupid):
        return self._backend(groupid).get_logo(groupid)

    def get_members(self, user, groupid, show_all):
        return self._backend(groupid).get_members(user, groupid, show_all)

    def get_groups(self, user, query):
        with self.timer.time('groups.get_groups'):
            return list(self._call_backends(lambda x: x.get_groups, user, query))

    def grouptypes(self):
        types = {}
        for backend in self.backends.values():
            for gtype in backend.grouptypes():
                types[gtype['id']] = gtype
        return list(types.values())
