from coreapis import cassandra_client
from coreapis.utils import now, LogWrapper, ValidationError, AlreadyExistsError
from datetime import datetime
import uuid
import valideer as V

FILTER_KEYS = {
    'owner': {'sel':  'owner = ?',
              'cast': uuid.UUID},
    'scope': {'sel':  'scopes contains ?',
              'cast': lambda u: u}
}


def ts(d):
    return datetime.strptime(d, "%Y-%m-%d %H:%M:%S%z")


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

    def get_client(self, id):
        self.log.debug('Get client', id=id)
        client = self.session.get_client_by_id(uuid.UUID(id))
        return client

    def validate_client(self, client):
        schema = {
            '+name': 'string',
            '+owner': V.AdaptBy(uuid.UUID),
            '+redirect_uri': ['string'],
            '+scopes': ['string'],
            'id': V.Nullable(V.AdaptBy(uuid.UUID)),
            'client_secret': V.Nullable('string', ''),
            'created': V.AdaptBy(ts),
            'descr': V.Nullable('string', ''),
            'scopes_requested': V.Nullable(['string'], []),
            'status': V.Nullable(['string'], []),
            'type': V.Nullable('string', ''),
            'updated': V.AdaptBy(ts),
        }
        validator = V.parse(schema, additional_properties=False)
        return validator.validate(client)

    def client_exists(self, id):
        try:
            self.session.get_client_by_id(id)
            return True
        except:
            return False

    def add_client(self, client):
        self.log.debug('add client')
        try:
            client = self.validate_client(client)
        except V.ValidationError as ex:
            self.log.debug('client is invalid: {}'.format(ex))
            raise ValidationError(ex)
        self.log.debug('client is ok')
        if 'id' in client:
            id = client['id']
            if self.client_exists(id):
                self.log.debug('client already exists', id=id)
                raise AlreadyExistsError('client already exists')
        else:
            client['id'] = uuid.uuid4()
        ts = now()
        client['created'] = ts
        client['updated'] = ts

        self.session.insert_client(client['id'], client['client_secret'], client['name'],
                                   client['descr'], client['redirect_uri'],
                                   client['scopes'], client['scopes_requested'],
                                   client['status'], client['type'], ts, client['owner'])
        return client

    def delete_client(self, id):
        self.log.debug('Delete client', id=id)
        self.session.delete_client(uuid.UUID(id))
