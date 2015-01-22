from coreapis import cassandra_client
from coreapis.utils import now, LogWrapper, ValidationError, AlreadyExistsError, ts
import uuid
import valideer as V

FILTER_KEYS = {
    'owner': {'sel':  'owner = ?',
              'cast': uuid.UUID},
    'scope': {'sel':  'scopes contains ?',
              'cast': lambda u: u}
}


class ClientAdmController(object):
    def __init__(self, contact_points, keyspace, maxrows):
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('clientadm.ClientAdmController')
        self.maxrows = maxrows

    def get_clients(self, params):
        self.log.debug('get_clients', num_params=len(params))
        selectors, values = [], []
        for k, v in FILTER_KEYS.items():
            if k in params:
                self.log.debug('Filter key found', k=k)
                if params[k] == '':
                    self.log.debug('Missing filter value')
                    raise ValidationError('missing filter value')
                selectors.append(v['sel'])
                values.append(v['cast'](params[k]))
        self.log.debug('get_clients', selectors=selectors, values=values, maxrows=self.maxrows)
        return self.session.get_clients(selectors, values, self.maxrows)

    def get_client(self, clientid):
        self.log.debug('Get client', clientid=clientid)
        client = self.session.get_client_by_id(uuid.UUID(clientid))
        return client

    def validate_client(self, client):
        self.log.debug('validate client', client=client)
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
        validator = V.parse(schema, additional_properties=False)
        return validator.validate(client)

    def client_exists(self, clientid):
        try:
            self.session.get_client_by_id(clientid)
            return True
        except:
            return False

    def get_owner(self, clientid):
        try:
            client = self.session.get_client_by_id(uuid.UUID(clientid))
            return client['owner']
        except:
            return None

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def insert_client(self, client):
        self.session.insert_client(client['id'], client['client_secret'], client['name'],
                                   client['descr'], client['redirect_uri'],
                                   client['scopes'], client['scopes_requested'],
                                   client['status'], client['type'], client['created'],
                                   client['updated'], client['owner'])
        return client

    def add_client(self, client, userid):
        self.log.debug('add client', userid=userid)
        try:
            client = self.validate_client(client)
        except V.ValidationError as ex:
            self.log.debug('client is invalid: {}'.format(ex))
            raise ValidationError(ex)
        self.log.debug('client is ok')
        if 'id' in client:
            clientid = client['id']
            if self.client_exists(clientid):
                self.log.debug('client already exists', clientid=clientid)
                raise AlreadyExistsError('client already exists')
        else:
            client['id'] = uuid.uuid4()
        if not 'owner' in client:
            client['owner'] = userid
        ts_now = now()
        client['created'] = ts_now
        client['updated'] = ts_now
        self.insert_client(client)
        return client

    def update_client(self, clientid, attrs):
        self.log.debug('update client', clientid=clientid)
        try:
            client = self.session.get_client_by_id(uuid.UUID(clientid))
            for k, v in attrs.items():
                if k not in  ['created', 'updated']:
                    client[k] = v
            client = self.validate_client(client)
        except V.ValidationError as ex:
            self.log.debug('client is invalid: {}'.format(ex))
            raise ValidationError(ex)
        client['updated'] = now()
        self.insert_client(client)
        return client

    def delete_client(self, clientid):
        self.log.debug('Delete client', clientid=clientid)
        self.session.delete_client(uuid.UUID(clientid))
