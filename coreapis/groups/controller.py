from coreapis import cassandra_client
from coreapis.utils import LogWrapper, ValidationError
from eventlet.greenpool import GreenPool
from eventlet.timeout import Timeout
from functools import partial
from itertools import chain


class DummyBackend(object):
    def __init__(self, prefix):
        self.prefix = prefix

    def get_member_groups(self, userid, show_all):
        return ["{}:1".format(self.prefix), "{}:2".format(self.prefix)]

    def get_groups(self, userid, show_all):
        return ["{}:1".format(self.prefix), "{}:2".format(self.prefix), "{}:3".format(self.prefix)]

    def grouptypes(self):
        return ['dummy', 'voot:voot!']


class GroupsController(object):

    def __init__(self, contact_points, keyspace, maxrows):
        self.maxrows = maxrows
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('groups.GroupsController')
        self.backends = {}
        self.pool = GreenPool()
        self.backends["foo"] = DummyBackend("foo")
        self.backends["bar"] = DummyBackend("bar")
        self.timeout = 0.2

    def _backend(self, groupid):
        if not ':' in groupid:
            raise ValidationError('Malformed group id')
        grouptype, subid = groupid.split(':', 1)
        if not grouptype in self.backends:
            raise KeyError('bad group id')
        return self.backends[grouptype]

    def _backend_call(self, method):
        with Timeout(self.timeout):
            return method()

    def get_member_groups(self, userid, show_all):
        return list(chain(*self.pool.imap(self._backend_call,
                                          (partial(backend.get_member_groups, userid, show_all) for backend in self.backends.values()))))

    def get_membership(self, userid, groupid):
        return self._backend(groupid).get_membership(userid, groupid)

    def get_group(self, userid, groupid):
        return self._backend(groupid).get_group(userid, groupid)

    def get_logo(self, groupid):
        return self._backend(groupid).get_logo(groupid)

    def get_members(self, userid, groupid):
        return self._backend(groupid).get_members(userid, groupid)

    def get_groups(self, userid, query):
        return list(chain(*self.pool.imap(self._backend_call,
                                          (partial(backend.get_groups, userid, query) for backend in self.backends.values()))))

    def grouptypes(self):
        types = []
        for backend in self.backends.values():
            types.extend(backend.grouptypes())
        return sorted(set(types))
