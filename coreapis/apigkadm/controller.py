from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.clientadm.controller import ClientAdmController
from coreapis.utils import LogWrapper, ts, public_userinfo
import uuid
import valideer as V
import re
from urllib.parse import urlparse


def valid_endpoint(value):
    url = urlparse(value)
    if url.scheme not in ('http', 'https'):
        return False
    if url.netloc == '':
        return False
    if ''.join(url[2:]) != '':
        return False
    if url.username or url.password:
        return False
    return True


class APIGKAdmController(CrudControllerBase):
    schema = {
        '+name': 'string',
        'owner': V.AdaptTo(uuid.UUID),
        'organization': V.Nullable('string'),
        '+id': re.compile('^[a-z][a-z0-9\-]{2,14}$'),
        'created': V.AdaptBy(ts),
        'descr': V.Nullable('string'),
        'status': V.Nullable(['string']),
        'updated': V.AdaptBy(ts),
        '+endpoints': V.HomogeneousSequence(valid_endpoint, min_length=1),
        '+requireuser': 'boolean',
        'httpscertpinned': V.Nullable('string'),
        'expose': {
            'clientid': 'boolean',
            'userid': 'boolean',
            'scopes': 'boolean',
            'groups': 'boolean',
            'userid-sec': V.AnyOf('boolean', ['string']),
        },
        'scopedef': V.Nullable({}),
        '+trust': {
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
        self.cadm_controller = ClientAdmController(contact_points, keyspace, None, maxrows)

    def has_permission(self, apigk, user):
        if user is None:
            return False
        org = apigk.get('organization', None)
        if org:
            return self.is_org_admin(user, org)
        else:
            if apigk['owner'] == user['userid']:
                return True
            return False

    def get(self, id):
        self.log.debug('Get apigk', id=id)
        apigk = self.session.get_apigk(id)
        return apigk

    def delete(self, id):
        self.log.debug('Delete apigk', id=id)
        self.session.delete_apigk(id)

    def list_by_owner(self, owner):
        selectors = ['owner = ?']
        values = [owner]
        owned = self.session.get_apigks(selectors, values, self.maxrows)
        return [gk for gk in owned if not gk['organization']]

    def list_by_organization(self, organization):
        selectors = ['organization = ?']
        values = [organization]
        return self.session.get_apigks(selectors, values, self.maxrows)

    def _insert(self, apigk):
        return self.session.insert_apigk(apigk)

    def get_logo(self, gkid):
        return self.session.get_apigk_logo(gkid)

    def _save_logo(self, gkid, data, updated):
        self.session.save_logo('apigk', gkid, data, updated)

    def public_list(self):
        res = self.session.get_apigks([], [], self.maxrows)
        owner_ids = set(r['owner'] for r in res)
        owners = {ownerid: self.session.get_user_by_id(ownerid) for ownerid in owner_ids}
        return [{
            'id': r['id'],
            'name': r['name'],
            'descr': r['descr'],
            'scopedef': r['scopedef'],
            'expose': r['expose'],
            'owner': public_userinfo(owners[r['owner']]),
        } for r in res]

    def get_gkowner_clients(self, ownerid):
        gkscopes = ['gk_{}'.format(r['id']) for r in self.list_by_owner(ownerid)]
        return self.cadm_controller.get_gkscope_clients(gkscopes)

    def get_gkorg_clients(self, orgid):
        gkscopes = ['gk_{}'.format(r['id']) for r in self.list_by_organization(orgid)]
        return self.cadm_controller.get_gkscope_clients(gkscopes)
