from coreapis import cassandra_client
from coreapis.clientadm.controller import ClientAdmController
from coreapis.utils import LogWrapper, get_feideids, ForbiddenError


class AuthorizationController(object):

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        self.log = LogWrapper('authorizations.AuthorizationController')
        self.cadm_controller = ClientAdmController(settings)

    def delete(self, userid, clientid):
        self.log.debug('Delete authorization', userid=userid, clientid=clientid)
        self.session.delete_authorization(userid, clientid)

    def delete_all(self, clientid, user, token):
        client = self.cadm_controller.get(clientid)
        if self.cadm_controller.has_permission(client, user, token):
            self.log.debug('Delete all authorizations', clientid=clientid)
            self.session.delete_all_authorizations(clientid)
        else:
            raise ForbiddenError('Must be owner or administrator of client')

    def list(self, userid):
        res = []
        for authz in self.session.get_authorizations(userid):
            elt = authz.copy()
            del elt['clientid']
            try:
                client = self.session.get_client_by_id(authz['clientid'])
            except KeyError:
                continue
            elt['client'] = dict(id=client['id'], name=client['name'])
            if 'apigk_scopes' in elt and elt['apigk_scopes']:
                elt['apigk_scopes'] = dict(elt['apigk_scopes'])
            res.append(elt)
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
        return False

    def get_mandatory_clients(self, user):
        selectors = ['status contains ?']
        values = ['Mandatory']

        by_id = {c['id']: c for c in self.session.get_clients(selectors, values, 9999)}
        for feideid in get_feideids(user):
            _, realm = feideid.split('@')
            for clientid in self.session.get_mandatory_clients(realm):
                try:
                    by_id[clientid] = self.session.get_client_by_id(clientid)
                except KeyError:
                    self.log.warn('Mandatory client does not exist', clientid=clientid)
        return [self.cadm_controller.get_public_info(c) for c in by_id.values()]
