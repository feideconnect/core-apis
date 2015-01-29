from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts
import uuid
import valideer as V


class AdHocGroupAdmController(CrudControllerBase):
    FILTER_KEYS = {
        'owner': {'sel':  'owner = ?',
                  'cast': uuid.UUID},
    }
    schema = {
        '+name': 'string',
        'owner': V.AdaptTo(uuid.UUID),
        'id': V.AdaptTo(uuid.UUID),
        'created': V.AdaptBy(ts),
        'descr': V.Nullable('string'),
        'updated': V.AdaptBy(ts),
        '+public': 'boolean',
    }

    def __init__(self, contact_points, keyspace, maxrows):
        super(AdHocGroupAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('adhocgroupadm.AdHocGroupAdmController')

    def get(self, id):
        self.log.debug('Get group', id=id)
        group = self.session.get_group(id)
        return group

    def delete(self, id):
        self.log.debug('Delete group', id=id)
        self.session.delete_group(id)

    def _list(self, selectors, values, maxrows):
        return self.session.get_groups(selectors, values, maxrows)

    def _insert(self, group):
        return self.session.insert_group(group)

    def get_logo(self, groupid):
        return self.session.get_group_logo(groupid)

    def _save_logo(self, groupid, data, updated):
        self.session.save_logo('group', groupid, data, updated)

    def is_owner(self, group, userid):
        return group['owner'] == userid

    def is_admin(self, group, userid):
        pass

    def is_owner_or_admin(self, group, userid):
        return self.is_owner(group, userid) or self.is_admin(group, userid)

    def has_permission(self, group, userid, permission):
        if permission == "update":
            return self.is_owner(group, userid)
        if permission == "delete":
            return self.is_owner(group, userid)
        if permission == "view":
            return self.is_owner_or_admin(group, userid)
