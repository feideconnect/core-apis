from copy import deepcopy
import json
from urllib.parse import urlsplit
import uuid

import blist
import valideer as V

from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.scopes import is_gkscopename, has_gkscope_match
from coreapis.scopes.manager import ScopesManager
from coreapis.utils import (
    LogWrapper, timestamp_adapter, ForbiddenError, valid_url,
    get_feideids, get_platform_admins)


USER_SETTABLE_STATUS_FLAGS = {'Public'}
INVALID_URISCHEMES = {'data', 'javascript', 'file', 'about'}
FEIDE_REALM_PREFIX = 'feide|realm|'


def is_valid_uri(uri):
    parsed = urlsplit(uri)
    scheme = parsed.scheme
    if len(scheme) == 0 or scheme in INVALID_URISCHEMES:
        return False
    elif scheme in ['http', 'https']:
        return len(parsed.netloc) > 0
    else:
        return True


class ClientAdmController(CrudControllerBase):
    schema = {
        # Required
        '+name': 'string',
        '+redirect_uri': V.HomogeneousSequence(item_schema=V.Condition(is_valid_uri), min_length=1),
        '+scopes_requested':  V.HomogeneousSequence(item_schema='string', min_length=1),
        # Maintained by clientadm API
        'created': V.AdaptBy(timestamp_adapter),
        'id': V.Nullable(V.AdaptTo(uuid.UUID)),
        'owner': V.AdaptTo(uuid.UUID),
        'organization': V.Nullable('string', None),
        'updated': V.AdaptBy(timestamp_adapter),
        'orgauthorization': V.Nullable({}),
        # Other attributes
        'client_secret': V.Nullable('string', ''),
        'descr': V.Nullable('string', ''),
        'scopes': V.Nullable(['string'], lambda: list()),
        'authproviders': V.Nullable(['string'], lambda: list()),
        'status': V.Nullable(['string'], lambda: list()),
        'type': V.Nullable('string', ''),
        'systemdescr': V.Nullable('string', ''),
        'privacypolicyurl': V.Nullable(valid_url),
        'homepageurl': V.Nullable(valid_url),
        'loginurl': V.Nullable(valid_url),
        'supporturl': V.Nullable(valid_url),
        'authoptions': V.Nullable({}),
    }
    public_attrs = ['id', 'name', 'descr', 'redirect_uri', 'owner', 'organization', 'authproviders',
                    'systemdescr', 'privacypolicyurl', 'homepageurl', 'loginurl', 'supporturl']
    scope_attrs = ['scopes', 'scopes_requested']

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        maxrows = settings.get('clientadm_maxrows')
        super(ClientAdmController, self).__init__(maxrows, 'client')
        self.session = cassandra_client.Client(contact_points, keyspace)
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)
        self.scopemgr = ScopesManager(settings, self.session, self.get_public_info, False)
        self.log = LogWrapper('clientadm.ClientAdmController')

    @staticmethod
    def adapt_client(client):
        adapted = deepcopy(client)
        for k, v in adapted.items():
            if k == 'orgauthorization':
                adapted[k] = {}
                if v:
                    adapted[k] = {k2: json.loads(v2) for k2, v2 in v.items()}
            elif k == 'authoptions':
                adapted[k] = {}
                if v:
                    adapted[k] = json.loads(v)
            elif isinstance(v, blist.sortedset):
                adapted[k] = list(v)
        return adapted

    def _list(self, selectors, values, scope):
        if scope:
            selectors.append('scopes contains ?')
            values.append(scope)
        res = self.session.get_clients(selectors, values, self.maxrows)
        return [self.adapt_client(client) for client in res]

    def list_by_owner(self, owner, scope=None):
        selectors = ['owner = ?']
        values = [owner]
        clients = self._list(selectors, values, scope)
        return [c for c in clients if c['organization'] is None]

    def list_by_organization(self, organization, scope=None):
        selectors = ['organization = ?']
        values = [organization]
        return self._list(selectors, values, scope)

    def public_clients(self, orgauthorization):
        selectors = []
        values = []
        if orgauthorization:
            selectors = ['orgauthorization contains key ?']
            values = [orgauthorization]
        clients = self._list(selectors, values, None)
        return [self.get_public_info(c) for c in clients if c]

    def has_permission(self, client, user):
        if self.is_platform_admin(user):
            return True
        if user is None:
            return False
        org = client.get('organization', None)
        if org:
            return self.is_org_admin(user, org)
        else:
            if client['owner'] == user['userid']:
                return True
            return False

    def get(self, clientid):
        self.log.debug('Get client', clientid=clientid)
        return self.adapt_client(self.session.get_client_by_id(clientid))

    def insert_client(self, client):
        sessclient = deepcopy(client)
        orgauthz = sessclient.get('orgauthorization', None)
        if orgauthz:
            for k, v in orgauthz.items():
                orgauthz[k] = json.dumps(v)
        self.session.insert_client(sessclient)

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client):
        self.scopemgr.handle_update(client)
        self.insert_client(client)
        self.scopemgr.notify_moderators(client)
        return client

    @staticmethod
    def filter_client_status(attrs_new, attrs_old):
        try:
            status_old = set(attrs_old['status'])
        except (KeyError, TypeError):
            status_old = set()
        try:
            status_requested = set(attrs_new['status'])
        except (KeyError, TypeError):
            status_requested = set()
        status_allowed = {flag for flag in status_requested if flag in USER_SETTABLE_STATUS_FLAGS}
        attrs_new['status'] = list(status_old.union(status_allowed))

    def add(self, item, userid):
        self.filter_client_status(item, {})
        return super(ClientAdmController, self).add(item, userid)

    def update(self, itemid, attrs):
        client = self.get(itemid)
        self.filter_client_status(attrs, client)
        client = self.validate_update(itemid, attrs)
        return self._insert(client)

    def delete(self, clientid):
        self.log.debug('Delete client', clientid=clientid)
        self.session.delete_client(clientid)

    def get_logo(self, clientid):
        return self.session.get_client_logo(clientid)

    def _save_logo(self, clientid, data, updated):
        self.session.save_logo('clients', clientid, data, updated)

    # Return clients for each scope as dict { <scope>: set(clientids)}
    def get_scope_clients(self):
        res = {}
        for client in self._list([], [], None):
            clientscopes = client.get('scopes', None)
            if clientscopes:
                for scope in [scope for scope in clientscopes if is_gkscopename(scope)]:
                    clientids = set(res.get(scope, []))
                    clientids.add(str(client['id']))
                    res[scope] = clientids
        return res

    # Return targets for a scope with subscopes as dict { <scope>: set(realms)}
    def get_scope_targets(self, name, scopedef):
        res = {}
        if scopedef:
            try:
                res[name] = set(scopedef['policy']['orgadmin']['target'])
            except KeyError:
                pass  # scopedef does not have orgadmin targets
            subscopes = scopedef.get('subscopes', None)
            if subscopes:
                for subname, scopedef in subscopes.items():
                    res.update(self.get_scope_targets('{}_{}'.format(name, subname), scopedef))
        return res

    # Return dict { <scope>: set(realms)} including all scopes, subscopes and their realms
    def get_scope_targets_all(self):
        res = {}
        for apigk in self.session.get_apigks([], [], 999999):
            res.update(self.get_scope_targets('gk_' + apigk['id'], apigk['scopedef']))
        return res

    # Return all clients which have been assigned a scope targeting this realm
    # as dict { <client id>: [<scope>, ..]}
    def get_realmclient_scopes(self, realm):
        # Get dict { <scope>: set(clientids)} including all scopes, subscopes and their clients
        clientids = self.get_scope_clients()
        # Get dict { <scope>: set(realms)} including all scopes, subscopes and their realms
        scope_targets = self.get_scope_targets_all()
        # For scopes which target the realm, add list of clients to result dict
        res = {}
        for scopename, realms in scope_targets.items():
            if FEIDE_REALM_PREFIX + realm in realms and scopename in clientids.keys():
                for clientid in clientids[scopename]:
                    scopenames = set(res.get(clientid, []))
                    scopenames.add(scopename)
                    res[clientid] = list(scopenames)
        return res

    def get_realmclient(self, realm, clientid, scopes):
        client = self.get(uuid.UUID(clientid))
        orgauthz = client.get('orgauthorization', {})
        scopeauthz = {scope: scope in orgauthz.get(realm, '[]') for scope in list(scopes)}
        pubclient = self.get_public_info(client)
        pubclient['scopeauthorizations'] = scopeauthz
        return pubclient

    def get_realmclients(self, realm):
        return [self.get_realmclient(realm, k, v)
                for k, v in self.get_realmclient_scopes(realm).items()]

    def get_gkscope_client(self, client, gkscopes, users=None, orgs=None):
        gkclient = self.get_public_info(client, users, orgs)
        orgauthz = client['orgauthorization']
        if orgauthz:
            orgauthz = {k: json.loads(v) for k, v in orgauthz.items()}
        gkclient.update({'orgauthorization': orgauthz})
        gkclient.update({attr: [] for attr in self.scope_attrs})
        for attr in self.scope_attrs:
            clientscopes = client[attr]
            if clientscopes:
                gkclient[attr] = [scope for scope in clientscopes
                                  if has_gkscope_match(scope, gkscopes)]
        return gkclient

    def get_gkscope_clients(self, gkscopes):
        users = {}
        orgs = {}
        clientdict = {}
        for gkscope in gkscopes:
            for client in (list(self.session.get_clients_by_scope(gkscope)) +
                           list(self.session.get_clients_by_scope_requested(gkscope))):
                if not client['id'] in clientdict:
                    clientdict[client['id']] = self.get_gkscope_client(client, gkscopes,
                                                                       users, orgs)
        return list(clientdict.values())

    def list_public_scopes(self):
        self.log.debug('List public scopes')
        return self.scopemgr.list_public_scopes()

    def validate_gkscope(self, user, scope):
        if not is_gkscopename(scope):
            raise ForbiddenError('{} is not an API Gatekeeper'.format(scope))
        gk = self.scopemgr.scope_to_gk(scope)
        if not gk or not self.has_permission(gk, user):
            raise ForbiddenError('User does not have access to manage API Gatekeeper')

    def add_gkscopes(self, client, user, scopes_add):
        for scope in [scope for scope in scopes_add if scope not in client['scopes']]:
            if not scope in client['scopes_requested']:
                raise ForbiddenError('Client owner has not requested scope {}'.format(scope))
            self.validate_gkscope(user, scope)
            client['scopes'].append(scope)
        return client

    def remove_gkscopes(self, client, user, scopes_remove):
        for scope in scopes_remove:
            self.validate_gkscope(user, scope)
            if scope in client['scopes']:
                client['scopes'].remove(scope)
            if scope in client['scopes_requested']:
                client['scopes_requested'].remove(scope)
        return client

    def update_gkscopes(self, clientid, user, scopes_add, scopes_remove):
        client = self.get(clientid)
        client = self.add_gkscopes(client, user, scopes_add)
        client = self.remove_gkscopes(client, user, scopes_remove)
        self.insert_client(client)

    def has_realm_permission(self, realm, user):
        org = self.session.get_org_by_realm(realm)
        return self.is_admin(user, org['id'])

    @staticmethod
    def get_orgauthorization(client, realm):
        return client['orgauthorization'].get(realm, [])

    def update_orgauthorization(self, client, realm, scopes):
        self.session.insert_orgauthorization(client['id'], realm, json.dumps(scopes))

    def delete_orgauthorization(self, client, realm):
        self.session.delete_orgauthorization(client['id'], realm)

    def get_mandatory_clients(self, user):
        selectors = ['status contains ?']
        values = ['Mandatory']
        by_id = {c['id']: c for c in self._list(selectors, values, None)}
        for feideid in get_feideids(user):
            print(feideid)
            _, realm = feideid.split('@')
            for clientid in self.session.get_mandatory_clients(realm):
                by_id[clientid] = self.session.get_client_by_id(clientid)
        return [self.get_public_info(c) for c in by_id.values()]
