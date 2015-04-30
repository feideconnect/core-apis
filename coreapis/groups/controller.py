from coreapis.utils import LogWrapper
from eventlet.greenpool import GreenPool, GreenPile
from eventlet.timeout import Timeout
import traceback
from paste.deploy.util import lookup_object

BACKEND_CONFIG_KEY = 'groups_backend_'
ID_PREFIX = 'fc'


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
                grouptype = key[len(BACKEND_CONFIG_KEY):]
                prefix = ID_PREFIX + ':' + grouptype
                self.backends[grouptype] = lookup_object(value)(prefix, maxrows, config)
        self.id_handlers = {}
        for backend in self.backends.values():
            self.id_handlers.update(backend.get_id_handlers())

    def _backend(self, groupid, perm_checker):
        parts = groupid.split(':', 2)
        if parts[0] != ID_PREFIX:
            raise KeyError('This group does not belong to us')
        if len(parts) < 3:
            raise KeyError('Malformed group id')
        prefix, grouptype, subid = parts
        handler = '{}:{}'.format(prefix, grouptype)
        if not handler in self.id_handlers:
            raise KeyError('bad group id')
        res = self.id_handlers[handler]
        if not res.permissions_ok(perm_checker):
            raise KeyError('No access to backend')
        return res

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

    def _call_backends(self, func, perm_checker, *args, **kwargs):
        pile = GreenPile(self.pool)
        for backend in (backend for backend in self.backends.values()
                        if backend.permissions_ok(perm_checker)):
            pile.spawn(self._backend_call, func(backend), *args, **kwargs)
        for result in pile:
            if result:
                for value in result:
                    yield value

    def get_member_groups(self, user, show_all, perm_checker):
        with self.timer.time('groups.get_member_groups'):
            return list(self._call_backends(lambda x: x.get_member_groups,
                                            perm_checker, user, show_all))

    def get_membership(self, user, groupid, perm_checker):
        return self._backend(groupid, perm_checker).get_membership(user, groupid)

    def get_group(self, user, groupid, perm_checker):
        return self._backend(groupid, perm_checker).get_group(user, groupid)

    def get_logo(self, groupid, perm_checker):
        return self._backend(groupid, perm_checker).get_logo(groupid)

    def get_members(self, user, groupid, show_all, perm_checker):
        return self._backend(groupid, perm_checker).get_members(user, groupid, show_all)

    def get_groups(self, user, query, perm_checker):
        with self.timer.time('groups.get_groups'):
            return list(self._call_backends(lambda x: x.get_groups, perm_checker,
                                            user, query))

    def grouptypes(self):
        types = {}
        for backend in self.backends.values():
            for gtype in backend.grouptypes():
                types[gtype['id']] = gtype
        return list(types.values())
