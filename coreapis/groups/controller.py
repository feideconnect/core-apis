from coreapis.utils import LogWrapper, ValidationError
from eventlet.greenpool import GreenPool, GreenPile
from eventlet.timeout import Timeout
from .adhoc_backend import AdHocGroupBackend
from . import BaseBackend
from .tests import MockBackend
import traceback


class DummyBackend(BaseBackend):
    def __init__(self, prefix, maxrows):
        super(DummyBackend, self).__init__(prefix, maxrows)

    def _format_group(self, foo):
        return {
            'id': self._groupid(foo),
            'displayName': 'Group {}'.format(foo),
        }

    def get_membership(self, userid, groupid):
        pass

    def get_group(self, userid, groupid):
        pass

    def get_members(self, userid, groupid, show_all):
        pass

    def get_member_groups(self, userid, show_all):
        return [self._format_group(1), self._format_group(2)]

    def get_groups(self, userid, query):
        return [self._format_group(1), self._format_group(2), self._format_group(3)]

    def grouptypes(self):
        return [{'id': 'voot:voot!', 'displayName': 'Dummy group type'}]


class GroupsController(object):

    def __init__(self, config):
        maxrows = config.get_settings().get('groups_maxrows', 100)
        self.maxrows = maxrows
        self.log = LogWrapper('groups.GroupsController')
        self.backends = {}
        self.pool = GreenPool()
        adhoc_prefix = config.get_settings().get('groups_adhoc_backend', None)
        if adhoc_prefix:
            self.backends[adhoc_prefix] = AdHocGroupBackend(adhoc_prefix, maxrows, config)
        mock_prefix = config.get_settings().get('groups_mock_backend', None)
        if mock_prefix:
            self.backends[mock_prefix] = MockBackend(mock_prefix, maxrows)
        self.timeout = 0.2

    def _backend(self, groupid):
        if not ':' in groupid:
            raise ValidationError('Malformed group id')
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
