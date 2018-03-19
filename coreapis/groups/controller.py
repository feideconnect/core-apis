from eventlet.greenpool import GreenPool, GreenPile
from eventlet.timeout import Timeout
from paste.deploy.util import lookup_object

from coreapis.utils import LogWrapper, request_id, set_request_id

BACKEND_CONFIG_KEY = 'groups_backend_'
ID_PREFIX = 'fc'


class GroupsController(object):

    def __init__(self, settings):
        maxrows = settings.get('groups_maxrows', 100)
        self.maxrows = maxrows
        self.log = LogWrapper('groups.GroupsController')
        self.timer = settings.get('timer')
        self.backends = {}
        self.pool = GreenPool()
        self.timeout = int(settings.get('groups_timeout_backend', '3000')) / 1000
        for key, value in settings.items():
            if key.startswith(BACKEND_CONFIG_KEY):
                grouptype = key[len(BACKEND_CONFIG_KEY):]
                prefix = ID_PREFIX + ':' + grouptype
                self.backends[grouptype] = lookup_object(value)(prefix, maxrows, settings)
        self.id_handlers = {}
        for backend in self.backends.values():
            self.id_handlers.update(backend.get_id_handlers())

    def _backend(self, groupid, perm_checker):
        parts = groupid.split(':', 2)
        if parts[0] != ID_PREFIX:
            raise KeyError('This group does not belong to us')
        if len(parts) < 3:
            raise KeyError('Malformed group id')
        prefix, grouptype, _ = parts
        handler = '{}:{}'.format(prefix, grouptype)
        if handler not in self.id_handlers:
            raise KeyError('bad group id')
        res = self.id_handlers[handler]
        if not res.permissions_ok(perm_checker):
            raise KeyError('No access to backend')
        return res

    def _backend_call(self, method, reqid, *args, **kwargs):
        set_request_id(reqid)
        backend = method.__self__.prefix
        call = method.__name__
        with self.timer.time('groups.{}.{}'.format(call, backend.replace(':', '_'))):
            with Timeout(self.timeout):
                try:
                    return method(*args, **kwargs)
                except Timeout:
                    self.log.warn("Timeout in group backend", backend=backend,
                                  method=call)

                except: # pylint: disable=bare-except
                    self.log.exception('unhandled exception in group backend')

    def _call_backends(self, func, perm_checker, *args, **kwargs):
        pile = GreenPile(self.pool)
        reqid = request_id()
        for backend in (backend for backend in self.backends.values()
                        if backend.permissions_ok(perm_checker)):
            pile.spawn(self._backend_call, func(backend), reqid, *args, **kwargs)
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
        include_member_ids = perm_checker('scope_groups-memberids')
        backend = self._backend(groupid, perm_checker)
        return backend.get_members(user, groupid, show_all, include_member_ids)

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
