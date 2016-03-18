import base64
import random

from coreapis import cassandra_client
from coreapis.utils import LogWrapper
from coreapis.cache import Cache


def basic_auth(trust):
    username = trust['username']
    password = trust['password']
    base64string = base64.b64encode('{}:{}'.format(username, password).encode('UTF-8')).decode('UTF-8')
    return "Authorization", "Basic {}".format(base64string)


def auth_header(trust):
    ttype = trust['type']
    if ttype == 'basic':
        return basic_auth(trust)
    if ttype == 'token':
        return 'Auth', trust['token']
    if ttype == 'bearer':
        return 'Authorization', 'Bearer {}'.format(trust['token'])
    raise RuntimeError('unhandled trust type {}'.format(ttype))


class GkController(object):
    def __init__(self, contact_points, keyspace, authz):
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        self.log = LogWrapper('gk.GkController')
        self._allowed_dn = Cache(1800, 'gk.GkController.allowed_dn_cache')

    def allowed_dn(self, dn):
        return self._allowed_dn.get(dn, lambda: self.session.apigk_allowed_dn(dn))

    def options(self, backend_id):
        backend = self.session.get_apigk(backend_id)
        headers = dict()
        headers['endpoint'] = random.choice(backend['endpoints'])
        self.log.debug('Gatekeeping OPTIONS call',
                       gatekeeper=backend_id, endpoint=headers['endpoint'])
        return headers

    def info(self, backend_id, client, user, scopes, subtokens):
        backend = self.session.get_apigk(backend_id)
        if backend['requireuser'] and user is None:
            self.log.warn('user required but not in token', gatekeeper=backend_id,
                          client=client['id'])
            return None
        headers = dict()

        if backend_id in subtokens:
            subtoken = self.session.get_token(subtokens[backend_id])
            headers['token'] = str(subtoken['access_token'])

            if user:
                if 'userid' in subtoken['scope']:
                    headers['userid'] = str(user['userid'])
                allowed_prefixes = set()
                if 'userid-nin' in subtoken['scope']:
                    allowed_prefixes.add('nin')
                if 'userid-feide' in subtoken['scope']:
                    allowed_prefixes.add('feide')
                if allowed_prefixes:
                    exposed_sec_ids = []
                    for sec_id in user['userid_sec']:
                        sec_id_type, _ = sec_id.split(':', 1)
                        if sec_id_type in allowed_prefixes:
                            exposed_sec_ids.append(sec_id)
                    headers['userid-sec'] = ",".join(exposed_sec_ids)

        scope_prefix = 'gk_{}_'.format(backend_id)
        exposed_scopes = [scope[len(scope_prefix):]
                          for scope in scopes if scope.startswith(scope_prefix)]
        headers['scopes'] = ','.join(exposed_scopes)

        headers['clientid'] = str(client['id'])
        headers['endpoint'] = random.choice(backend['endpoints'])
        header, value = auth_header(backend['trust'])
        headers[header] = value
        self.log.debug('Allowing gatekeeping', gatekeeper=backend_id, endpoint=headers['endpoint'],
                       client=client['id'])
        return headers
