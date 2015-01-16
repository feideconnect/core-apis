from coreapis import cassandra_client
from coreapis.utils import now, LogWrapper, ValidationError, AlreadyExistsError
from datetime import datetime
import uuid

FILTER_KEYS = {
    'owner': {'sel':  'owner = ?',
              'cast': uuid.UUID},
    'scope': {'sel':  'scopes contains ?',
              'cast': lambda u: u}
}

def is_text(d):
    return type(d) == str

def is_uuid(d):
    try:
        uuid.UUID(d)
        return True
    except:
        return False

def is_ts(d):
    try:
        datetime.strptime(d, "%Y-%m-%d %H:%M:%S%z")
        return True
    except:
        return False

def is_typed_list(d, p):
    if not type(d) == list:
        return False
    for e in d:
        if not p(e):
            return False
    return True

def is_text_list(d):
    return is_typed_list(d, is_text)

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
        needed_attrs = {
            'name': {'validator': is_text},
            'owner': {'validator': is_uuid},
            'redirect_uri': {'validator': is_text_list},
            'scopes': {'validator': is_text_list},
        }
        allowed_attrs = {
            'id': {'validator': is_uuid},  # normally filled in when creating
            'client_secret': {'validator': is_text, 'default': ''},
            'created': {'validator': is_ts}, # insert_client fills in
            'descr': {'validator': is_text, 'default': ''},
            'scopes_requested': {'validator': is_text_list, 'default': []},
            'status': {'validator': is_text_list, 'default': []},
            'type': {'validator': is_text, 'default': ''},
            'updated': {'validator': is_ts}, # insert_client fills in
        }

        allowed_attrs.update(needed_attrs)
        for k in needed_attrs.keys():
            if not k in client:
                self.log.debug('missing attribute', attr=k)
                return False
        for k, v in client.items():
            if not k in allowed_attrs:
                self.log.debug('illegal attribute', attr=k)
                return False
            validator = allowed_attrs[k]['validator']
            if not validator(v):
                self.log.debug('invalid attribute', attr=k, value=v)
                return False
        for k, v in allowed_attrs.items():
            if not k in client:
                if 'default' in v:
                    client[k] = v['default']
        return True

    def client_exists(self, id):
        try:
            self.session.get_client_by_id(id)
            return True
        except:
            return False

    def add_client(self, client):
        self.log.debug('add client')
        if not self.validate_client(client):
            self.log.debug('client is invalid')
            raise ValidationError('client is invalid')
        self.log.debug('client is ok')
        if 'id' in client:
            id = uuid.UUID(client['id'])
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
                                   client['status'], client['type'], ts, uuid.UUID(client['owner']))
        return client
