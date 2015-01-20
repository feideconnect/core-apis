from coreapis import cassandra_client
from coreapis.utils import now, LogWrapper, ValidationError, AlreadyExistsError, ts
import uuid
import valideer as V
import re

FILTER_KEYS = {
    'owner': {'sel':  'owner = ?',
              'cast': uuid.UUID},
}


class APIGKAdmController(object):
    def __init__(self, contact_points, keyspace, maxrows):
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('apigkadm.APIGKAdmController')
        self.maxrows = maxrows

    def get_apigks(self, params):
        self.log.debug('get_apigks', num_params=len(params))
        selectors, values = [], []
        for k, v in FILTER_KEYS.items():
            if k in params:
                self.log.debug('Filter key found', k=k)
                if params[k] == '':
                    self.log.debug('Missing filter value')
                    raise ValidationError('missing filter value')
                selectors.append(v['sel'])
                values.append(v['cast'](params[k]))
        self.log.debug('get_apigks', selectors=selectors, values=values, maxrows=self.maxrows)
        return self.session.get_apigks(selectors, values, self.maxrows)

    def get_apigk(self, id):
        self.log.debug('Get apigk', id=id)
        apigk = self.session.get_apigk(id)
        return apigk

    def validate_apigk(self, apigk):
        schema = {
            '+name': 'string',
            '+owner': V.AdaptTo(uuid.UUID),
            'id': re.compile('^[a-z][a-z0-9\-]{2,14}$'),
            'created': V.AdaptBy(ts),
            'descr': V.Nullable('string', ''),
            'status': V.Nullable(['string'], []),
            'updated': V.AdaptBy(ts),
            '+endpoints': ['string'],
            '+requireuser': 'boolean',
            'httpscertpinned': V.Nullable('string'),
            'expose': {
                'clientid': 'boolean',
                'userid': 'boolean',
                'scopes': 'boolean',
                'groups': 'boolean',
                'userid-sec': V.AnyOf('boolean', ['string']),
            },
            'scopedef': {},
            'trust': {
                '+type': 'string',
                'token': 'string',
                'username': 'string',
                'password': 'string',
            }
        }
        validator = V.parse(schema, additional_properties=False)
        return validator.validate(apigk)

    def apigk_exists(self, id):
        try:
            self.session.get_apigk(id)
            return True
        except:
            return False

    def add_apigk(self, apigk):
        self.log.debug('add apigk')
        try:
            apigk = self.validate_apigk(apigk)
        except V.ValidationError as ex:
            self.log.debug('apigk is invalid: {}'.format(ex))
            raise ValidationError(ex)
        self.log.debug('apigk is ok')
        if 'id' in apigk:
            id = apigk['id']
            if self.apigk_exists(id):
                self.log.debug('apigk already exists', id=id)
                raise AlreadyExistsError('apigk already exists')
        else:
            apigk['id'] = uuid.uuid4()
        ts = now()
        apigk['created'] = ts
        apigk['updated'] = ts

        self.session.insert_apigk(apigk)
        return apigk

    def delete_apigk(self, id):
        self.log.debug('Delete apigk', id=id)
        self.session.delete_apigk(uuid.UUID(id))

    def update_apigk(self, id, attrs):
        self.log.debug('update apigk')
        try:
            apigk = self.session.get_apigk(id)
            for k, v in attrs.items():
                apigk[k] = v
            apigk = self.validate_apigk(apigk)
        except V.ValidationError as ex:
            self.log.debug('apigk is invalid: {}'.format(ex))
            raise ValidationError(ex)
        apigk['updated'] = now()
        self.session.insert_apigk(apigk)
