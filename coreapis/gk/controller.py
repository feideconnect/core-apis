from coreapis import cassandra_client
from coreapis.utils import LogWrapper
import random
import base64


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
    raise RuntimeError('unhandled trust type {}'.format(ttype))


class GkController(object):
    def __init__(self, contact_points, keyspace):
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('gk.GkController')

    def info(self, backend_id, client, user, scopes):
        backend = self.session.get_apigk(backend_id)
        if backend['requireuser'] and user is None:
            return None
        expose = backend['expose']
        headers = dict()

        if user:
            if expose.get('userid', False):
                headers['userid'] = str(user['userid'])
            expose_sec = expose.get('userid-sec', False)
            if expose_sec is True:
                headers['userid-sec'] = ",".join(user['userid_sec'])
            elif isinstance(expose_sec, list):
                exposed_sec_ids = []
                for sec in expose_sec:
                    for sec_id in user['userid_sec']:
                        sec_id_type, _ = sec_id.split(':', 1)
                        if sec_id_type == sec:
                            exposed_sec_ids.append(sec_id)
                headers['userid-sec'] = ",".join(exposed_sec_ids)

            if expose.get('groups', False):
                raise NotImplementedError()

        if expose.get('scopes', False):
            scope_prefix = 'gk_{}_'.format(backend_id)
            exposed_scopes = [scope[len(scope_prefix):] for scope in scopes if scope.startswith(scope_prefix)]
            headers['scopes'] = ','.join(exposed_scopes)

        if expose.get('clientid', False):
            headers['clientid'] = str(client['id'])
        headers['endpoint'] = random.choice(backend['endpoints'])
        header, value = auth_header(backend['trust'])
        headers[header] = value
        for k, v in headers.items():
            self.log.debug('returning header {}: {}'.format(k, v))
        return headers
