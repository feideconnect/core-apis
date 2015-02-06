from coreapis import cassandra_client
from coreapis.utils import LogWrapper


class AuthorizationController(object):

    def __init__(self, contact_points, keyspace):
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('authorizations.AuthorizationController')

    def delete(self, userid, clientid):
        self.log.debug('Delete authorization', userid=userid, clientid=clientid)
        self.session.delete_authorization(userid, clientid)

    def list(self, userid):
        res = []
        for authz in self.session.get_authorizations(userid):
            el = authz.copy()
            del el['clientid']
            client = self.session.get_client_by_id(authz['clientid'])
            el['client'] = dict(id=client['id'], name=client['name'])
            res.append(el)
        return res