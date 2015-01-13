from coreapis import cassandra_client
from coreapis.utils import ValidationError, LogWrapper
import uuid

LIMIT    = 100

filter_keys = {
    'owner': { 'sel':  'owner = ?',
               'cast': lambda u: uuid.UUID(u) },
    'scope': { 'sel':  'scopes contains ?',
               'cast': lambda u: u }
}

class ClientAdmController(object):
    def __init__(self, contact_points, keyspace, maxrows):
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('clientadm.ClientAdmController')
        self.maxrows = maxrows

    def get_clients(self, params):
        self.log.debug('get_clients', num_params=len(params))
        
        selectors, values = [], []
        for k, v in filter_keys.items():
            if params.has_key(k):
                self.log.debug('Filter key found', k=k)
                if v == '':
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
