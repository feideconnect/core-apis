from coreapis import cassandra_client
from coreapis.utils import LogWrapper


class AuthorizationController(object):

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        self.log = LogWrapper('authorizations.AuthorizationController')

    def delete(self, userid, clientid):
        self.log.debug('Delete authorization', userid=userid, clientid=clientid)
        self.session.delete_authorization(userid, clientid)

    def list(self, userid):
        res = []
        for authz in self.session.get_authorizations(userid):
            el = authz.copy()
            del el['clientid']
            try:
                client = self.session.get_client_by_id(authz['clientid'])
            except KeyError:
                continue
            el['client'] = dict(id=client['id'], name=client['name'])
            if 'apigk_scopes' in el and el['apigk_scopes']:
                el['apigk_scopes'] = dict(el['apigk_scopes'])
            res.append(el)
        return res

    def resources_owned(self, userid):
        self.log.debug('Resources owned', userid=userid)
        maxrows = 99
        groupcount = sum(1 for i in self.session.get_groups(['owner = ?'], [userid], maxrows))
        apigkcount = sum(1 for i in self.session.get_apigks(['owner = ?'], [userid], maxrows))
        clientcount = sum(1 for i in self.session.get_clients(['owner = ?'], [userid], maxrows))
        ready = groupcount == 0 and apigkcount == 0 and clientcount == 0
        return {
            "ready": ready,
            "items": {
                "groups": groupcount,
                "apigks": apigkcount,
                "clients": clientcount,
            }
        }

    def reset_user(self, userid):
        self.log.debug('Reset user', userid=userid)
        # Remove from adhoc groups
        maxrows = 9999
        for membership in self.session.get_group_memberships(userid, None, None, maxrows):
            self.session.del_group_member(membership['groupid'], userid)
        # Remove oauth authorizations and tokens
        for auth in self.list(userid):
            self.delete(userid, auth['client']['id'])
        # Reset user in cassandra
        self.session.reset_user(userid)

    def consent_withdrawn(self, userid):
        self.log.debug('Consent withdrawn', userid=userid)
        if self.resources_owned(userid)["ready"]:
            self.reset_user(userid)
            return True
        else:
            return False
