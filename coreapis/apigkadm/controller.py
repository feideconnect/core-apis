from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.clientadm.controller import ClientAdmController
from coreapis.utils import LogWrapper, ts, public_userinfo, public_orginfo, log_token, valid_url
import uuid
import valideer as V
import re


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
        '+endpoints': V.HomogeneousSequence(valid_url, min_length=1),
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
        },
        'systemdescr': V.Nullable('string'),
        'privacypolicyurl': V.Nullable(valid_url),
        'docurl': V.Nullable(valid_url),
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

    def delete(self, gk, user):
        id = gk['id']
        mainscope = 'gk_' + id
        subscopes = ['{}_{}'.format(mainscope, s) for s in gk.get('scopedef', {}).get('subscopes', {}).keys()]
        gk_scopes = [mainscope] + subscopes
        self.log.debug('Delete apigk', id=id, scopes=gk_scopes)
        # Delete scopes from all clients
        clients = self.cadm_controller.get_gkscope_clients(['gk_' + id])
        for client in clients:
            scopes = set(client['scopes_requested']) | set(client['scopes'])
            self.log.debug('removing scopes from client', client=client['id'],
                           scopes_removed=list(scopes))
            self.cadm_controller.update_gkscopes(client['id'], user, [], scopes)
        # Delete scopes from all oauth_authorizations
        authorizations = {}
        for scope in gk_scopes:
            authorizations.update({(a['userid'], a['clientid']): a for a in self.session.get_oauth_authorizations_by_scope(scope)})
        for auth in authorizations.values():
            scopes = auth['scopes']
            auth['scopes'] = [scope for scope in scopes if scope not in gk_scopes]
            self.log.debug('removing scopes from oauth_authorization', userid=auth['userid'],
                           clientid=auth['clientid'],
                           scopes_removed=list(set(scopes).difference(auth['scopes'])))
            self.session.update_oauth_authorization_scopes(auth)
        # Delete scopes from all tokens
        tokens = {}
        for scope in gk_scopes:
            tokens.update({t['access_token']: t for t in self.session.get_tokens_by_scope(scope)})
        for tokenid, token in tokens.items():
            scopes = token['scope']
            token['scope'] = [scope for scope in scopes if scope not in gk_scopes]
            self.log.debug('removing scopes from oauth_token', accesstoken=log_token(tokenid),
                           scopes_removed=list(set(scopes).difference(token['scope'])))
            self.session.update_token_scopes(tokenid, token['scope'])
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
        organization_ids = set(r['organization'] for r in res if r['organization'])
        organizations = {orgid: self.session.get_org(orgid) for orgid in organization_ids}
        return [{
            'id': r['id'],
            'name': r['name'],
            'descr': r['descr'],
            'scopedef': r['scopedef'],
            'expose': r['expose'],
            'owner': public_userinfo(owners[r['owner']]),
            'organization': r['organization'] and public_orginfo(organizations[r['organization']]) or None,
        } for r in res]

    def get_gkowner_clients(self, ownerid):
        gkscopes = ['gk_{}'.format(r['id']) for r in self.list_by_owner(ownerid)]
        return self.cadm_controller.get_gkscope_clients(gkscopes)

    def get_gkorg_clients(self, orgid):
        gkscopes = ['gk_{}'.format(r['id']) for r in self.list_by_organization(orgid)]
        return self.cadm_controller.get_gkscope_clients(gkscopes)
