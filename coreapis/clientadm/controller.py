from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts
import uuid
import valideer as V


class ClientAdmController(CrudControllerBase):
    FILTER_KEYS = {
        'owner': {'sel':  'owner = ?',
                  'cast': uuid.UUID},
        'scope': {'sel':  'scopes contains ?',
                  'cast': lambda u: u}
    }
    schema = {
        # Required
        '+name': 'string',
        '+redirect_uri': V.HomogeneousSequence(item_schema='string', min_length=1),
        '+scopes_requested':  V.HomogeneousSequence(item_schema='string', min_length=1),
        # Maintained by clientadm API
        'created': V.AdaptBy(ts),
        'id': V.Nullable(V.AdaptTo(uuid.UUID)),
        'owner': V.AdaptTo(uuid.UUID),
        'updated': V.AdaptBy(ts),
        # Other attributes
        'client_secret': V.Nullable('string', ''),
        'descr': V.Nullable('string', ''),
        'scopes': V.Nullable(['string'], []),
        'status': V.Nullable(['string'], []),
        'type': V.Nullable('string', ''),
    }

    def __init__(self, contact_points, keyspace, maxrows):
        super(ClientAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('clientadm.ClientAdmController')

    def _list(self, selectors, values, maxrows):
        return self.session.get_clients(selectors, values, maxrows)

    def get(self, clientid):
        self.log.debug('Get client', clientid=clientid)
        client = self.session.get_client_by_id(clientid)
        return client

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client):
        self.session.insert_client(client['id'], client['client_secret'], client['name'],
                                   client['descr'], client['redirect_uri'],
                                   client['scopes'], client['scopes_requested'],
                                   client['status'], client['type'], client['created'],
                                   client['updated'], client['owner'])
        return client

    def delete(self, clientid):
        self.log.debug('Delete client', clientid=clientid)
        self.session.delete_client(clientid)
