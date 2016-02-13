import re
import uuid

import valideer as V

from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.clientadm.controller import ClientAdmController
from coreapis.scopes.manager import ScopesManager
from coreapis.utils import LogWrapper, timestamp_adapter, log_token, valid_url, get_platform_admins


def valid_gk_url(url):
    if valid_url(url) and not url.endswith('/') and url.startswith('https://'):
        return True
    return False


class APIGKAdmController(CrudControllerBase):
    schema = {
        '+name': 'string',
        'owner': V.AdaptTo(uuid.UUID),
        'organization': V.Nullable('string'),
        '+id': re.compile(r'^[a-z][a-z0-9\-]{2,14}$'),
        '+scopes_requested':  V.HomogeneousSequence(item_schema='string', min_length=1),
        'created': V.AdaptBy(timestamp_adapter),
        'descr': V.Nullable('string'),
        'status': V.Nullable(['string']),
        'updated': V.AdaptBy(timestamp_adapter),
        '+endpoints': V.HomogeneousSequence(valid_gk_url, min_length=1),
        '+requireuser': 'boolean',
        'httpscertpinned': V.Nullable('string'),
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
        'scopes': V.Nullable(['string'], lambda: list()),
    }
    public_attrs = ['id', 'name', 'descr', 'scopedef', 'systemdescr', 'privacypolicyurl', 'docurl']

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        maxrows = int(settings.get('apigkadm_maxrows') or 300)
        super(APIGKAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)
        self.log = LogWrapper('apigkadm.APIGKAdmController')
        self.scopemgr = ScopesManager(settings, self.session, self.get_public_info, True)
        self.cadm_controller = ClientAdmController(settings)

    def has_permission(self, apigk, user):
        if user is None:
            return False
        if self.is_platform_admin(user):
            return True
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

    def list_all(self, scope=None):
        return self.session.get_apigks([], [], self.maxrows)

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, apigk):
        self.scopemgr.handle_update(apigk)
        self.session.insert_apigk(apigk)
        self.scopemgr.notify_moderators(apigk)
        return apigk

    def get_logo(self, gkid):
        return self.session.get_apigk_logo(gkid)

    def _save_logo(self, gkid, data, updated):
        self.session.save_logo('apigk', gkid, data, updated)

    @staticmethod
    def matches_query(apigk, query):
        if not query:
            return True
        query = query.lower()
        return query in apigk['id'].lower() or query in apigk['name'].lower()

    def public_list(self, query, max_replies):
        if max_replies is None or max_replies > self.maxrows:
            max_replies = self.maxrows
        maxrows = self.maxrows
        if query:
            maxrows = 9999
        res = [r for count, r in enumerate(self.session.get_apigks(['status contains ?'],
                                                                   ['public'], maxrows))
               if count < max_replies and self.matches_query(r, query)]
        users = {}
        orgs = {}
        return [self.get_public_info(r, users, orgs) for r in res]

    def get_gkowner_clients(self, ownerid):
        gkscopes = ['gk_{}'.format(r['id']) for r in self.list_by_owner(ownerid)]
        return self.cadm_controller.get_gkscope_clients(gkscopes)

    def get_gkorg_clients(self, orgid):
        gkscopes = ['gk_{}'.format(r['id']) for r in self.list_by_organization(orgid)]
        return self.cadm_controller.get_gkscope_clients(gkscopes)
