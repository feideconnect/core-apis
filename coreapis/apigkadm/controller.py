from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import now, LogWrapper, ValidationError, AlreadyExistsError, ts
import uuid
import valideer as V
import re


class APIGKAdmController(CrudControllerBase):
    FILTER_KEYS = {
        'owner': {'sel':  'owner = ?',
                  'cast': uuid.UUID},
    }
    schema = {
        '+name': 'string',
        'owner': V.AdaptTo(uuid.UUID),
        'id': re.compile('^[a-z][a-z0-9\-]{2,14}$'),
        'created': V.AdaptBy(ts),
        'descr': V.Nullable('string', ''),
        'status': V.Nullable(['string'], []),
        'updated': V.AdaptBy(ts),
        '+endpoints': V.HomogeneousSequence(item_schema='string', min_length=1),
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

    def __init__(self, contact_points, keyspace, maxrows):
        super(APIGKAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('apigkadm.APIGKAdmController')

    def get(self, id):
        self.log.debug('Get apigk', id=id)
        apigk = self.session.get_apigk(id)
        return apigk

    def delete(self, id):
        self.log.debug('Delete apigk', id=id)
        self.session.delete_apigk(id)

    def _list(self, selectors, values, maxrows):
        return self.session.get_apigks(selectors, values, maxrows)

    def _insert(self, apigk):
        return self.session.insert_apigk(apigk)
