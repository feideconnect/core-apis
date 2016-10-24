from copy import deepcopy
import itertools
import json
from urllib.parse import urlsplit
import uuid

from aniso8601 import parse_date
import cassandra.util
import datetime
import valideer as V

from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.scopes import is_gkscopename, has_gkscope_match
from coreapis.scopes.manager import ScopesManager
from coreapis.authproviders import authprovmgr, REGISTER_CLIENT
from coreapis.utils import (
    LogWrapper, timestamp_adapter, ValidationError, ForbiddenError,
    valid_url, get_feideids, userinfo_for_log, get_platform_admins,
    PRIV_PLATFORM_ADMIN)


USER_SETTABLE_STATUS_FLAGS = {'Public'}
INVALID_URISCHEMES = {'data', 'javascript', 'file', 'about'}
FEIDE_REALM_PREFIX = 'feide|realm|'
MAX_DAYS = 14


def is_valid_uri(uri):
    parsed = urlsplit(uri)
    scheme = parsed.scheme
    if len(scheme) == 0 or scheme in INVALID_URISCHEMES:
        return False
    elif scheme in ['http', 'https']:
        return len(parsed.netloc) > 0
    else:
        return True


def filter_client_status(attrs_new, attrs_old, privileges):
    try:
        status_old = set(attrs_old['status'])
    except (KeyError, TypeError):
        status_old = set()
    try:
        status_requested = set(attrs_new['status'])
    except (KeyError, TypeError):
        status_requested = set()
    if PRIV_PLATFORM_ADMIN in privileges:
        status_allowed = status_requested
    else:
        status_allowed = status_requested.intersection(USER_SETTABLE_STATUS_FLAGS)
    attrs_new['status'] = list(status_old.union(status_allowed))


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
        'admins': V.Nullable(['string'], lambda: list()),
    }
    public_attrs = ['id', 'name', 'descr', 'redirect_uri', 'owner', 'organization', 'authproviders',
                    'systemdescr', 'privacypolicyurl', 'homepageurl', 'loginurl', 'supporturl']
    scope_attrs = ['scopes', 'scopes_requested']
    platformadmin_attrs = ['owner', 'scopes', 'orgauthorization']
    platformadmin_attrs_update = ['organization']
    protected_attrs = ['created', 'updated']
    protected_attrs_update = ['id']

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        maxrows = settings.get('clientadm_maxrows')
        super(ClientAdmController, self).__init__(maxrows, 'client')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)
        self.scopemgr = ScopesManager(settings, self.session, self.get_public_info, False)
        self.log = LogWrapper('clientadm.ClientAdmController')
        self.groupengine_base_url = settings.get('groupengine_base_url')

    @staticmethod
    def adapt_client(client):
        adapted = deepcopy(client)
        for key, val in adapted.items():
            if key == 'orgauthorization':
                adapted[key] = {}
                if val:
                    adapted[key] = {k2: json.loads(v2) for k2, v2 in val.items()}
            elif key == 'authoptions':
                adapted[key] = {}
                if val:
                    adapted[key] = json.loads(val)
            elif isinstance(val, cassandra.util.SortedSet):
                adapted[key] = list(val)
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

    def list_by_admin(self, admin, scope=None):
        selectors = ['admins contains ?']
        values = [admin]
        clients = self._list(selectors, values, scope)
        return [c for c in clients if c['organization'] is None]

    def list_managed(self, owner, scope, token):
        managed = self.list_by_owner(owner, scope)
        managed_ids = {client['id'] for client in managed}
        groupids = set(self.get_my_groupids(token))
        for groupid in groupids:
            clients = self.list_by_admin(groupid, scope)
            for client in clients:
                clientid = client['id']
                if clientid not in managed_ids:
                    managed.append(clients)
                    managed_ids.add(clientid)
        return managed

    def list_by_organization(self, organization, scope=None):
        selectors = ['organization = ?']
        values = [organization]
        return self._list(selectors, values, scope)

    def list_all(self, scope=None):
        return self._list([], [], scope)

    def public_clients(self, orgauthorization):
        selectors = []
        values = []
        if orgauthorization:
            selectors = ['orgauthorization contains key ?']
            values = [orgauthorization]
        clients = self._list(selectors, values, None)
        return [self.get_public_info(c) for c in clients if c]

    def is_owner_equiv(self, client, user, token):
        if client['owner'] == user['userid']:
            return True
        admins = set(client.get('admins') or [])
        self.log.debug('is_owner_equiv', admins=admins)
        if not admins:
            return False
        groupids = set(self.get_my_groupids(token))
        self.log.debug('is_owner_equiv', groupids=groupids)
        return admins.intersection(groupids)

    def has_permission(self, client, user, token):
        if user is None:
            return False
        if self.is_platform_admin(user):
            return True
        org = client.get('organization', None)
        if org:
            return self.is_org_admin(user, org)
        else:
            return self.is_owner_equiv(client, user, token)

    def get(self, clientid):
        self.log.debug('Get client', clientid=clientid)
        return self.adapt_client(self.session.get_client_by_id(clientid))

    def insert_client(self, client):
        sessclient = deepcopy(client)
        orgauthz = sessclient.get('orgauthorization', None)
        if orgauthz:
            for key, val in orgauthz.items():
                orgauthz[key] = json.dumps(val)
        self.session.insert_client(sessclient)

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client, privileges):
        self.scopemgr.handle_update(client, privileges)
        authprovmgr.check_client_update(self.session, client)
        self.insert_client(client)
        self.scopemgr.notify_moderators(client)
        return client

    def add(self, item, user, privileges):
        filter_client_status(item, {}, privileges)
        res = super(ClientAdmController, self).add(item, user, privileges)
        self.log.info('adding client',
                      audit=True, clientid=res['id'], user=userinfo_for_log(user))
        return res

    def update(self, itemid, attrs, user, privileges):
        client = self.get(itemid)
        filter_client_status(attrs, client, privileges)
        client = self.validate_update(itemid, attrs)
        res = self._insert(client, privileges)
        self.log.info('updating client',
                      audit=True, clientid=res['id'], attrs=attrs, user=userinfo_for_log(user))
        return res

    def delete(self, clientid, user):
        self.log.info('delete client',
                      audit=True, clientid=clientid, user=userinfo_for_log(user))
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
        return [self.get_realmclient(realm, key, val)
                for key, val in self.get_realmclient_scopes(realm).items()]

    def get_gkscope_client(self, client, gkscopes, users=None, orgs=None):
        gkclient = self.get_public_info(client, users, orgs)
        orgauthz = client['orgauthorization']
        if orgauthz:
            orgauthz = {key: json.loads(val) for key, val in orgauthz.items()}
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
            for client in (itertools.chain(self.session.get_clients_by_scope(gkscope),
                                           self.session.get_clients_by_scope_requested(gkscope))):
                if client['id'] not in clientdict:
                    clientdict[client['id']] = self.get_gkscope_client(client, gkscopes,
                                                                       users, orgs)
        return list(clientdict.values())

    def list_scopes(self):
        self.log.debug('List scopes')
        return self.scopemgr.list_scopes()

    def validate_gkscope(self, user, scope, token):
        if not is_gkscopename(scope):
            raise ForbiddenError('{} is not an API Gatekeeper'.format(scope))
        gk = self.scopemgr.scope_to_gk(scope)
        if not gk or not self.has_permission(gk, user, token):
            raise ForbiddenError('User does not have access to manage API Gatekeeper')

    def add_gkscopes(self, client, user, scopes_add, token):
        for scope in [scope for scope in scopes_add if scope not in client['scopes']]:
            if scope not in client['scopes_requested']:
                raise ForbiddenError('Client owner has not requested scope {}'.format(scope))
            self.validate_gkscope(user, scope, token)
            client['scopes'].append(scope)
        return client

    def remove_gkscopes(self, client, user, scopes_remove, token):
        for scope in scopes_remove:
            self.validate_gkscope(user, scope, token)
            if scope in client['scopes']:
                client['scopes'].remove(scope)
            if scope in client['scopes_requested']:
                client['scopes_requested'].remove(scope)
        return client

    def update_gkscopes(self, clientid, user, scopes_add, scopes_remove, token):
        client = self.get(clientid)
        client = self.add_gkscopes(client, user, scopes_add, token)
        client = self.remove_gkscopes(client, user, scopes_remove, token)
        self.log.info('updating gkscopes for client',
                      audit=True, clientid=clientid,
                      scopes_add=scopes_add, scopes_remove=scopes_remove,
                      user=userinfo_for_log(user))
        self.insert_client(client)

    def has_realm_permission(self, realm, user):
        org = self.session.get_org_by_realm(realm)
        return self.is_admin(user, org['id'])

    @staticmethod
    def get_orgauthorization(client, realm):
        return client['orgauthorization'].get(realm, [])

    def update_orgauthorization(self, client, realm, scopes, user):
        clientid = client['id']
        self.log.info('updating orgauthorization for client',
                      audit=True, clientid=clientid, realm=realm, scopes=scopes,
                      user=userinfo_for_log(user))
        self.session.insert_orgauthorization(clientid, realm, json.dumps(scopes))

    def delete_orgauthorization(self, client, realm, user):
        clientid = client['id']
        self.log.info('deleting orgauthorization for client',
                      audit=True, clientid=clientid, realm=realm, user=userinfo_for_log(user))
        self.session.delete_orgauthorization(clientid, realm)

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

    def get_policy(self, user):
        approved = authprovmgr.has_user_permission(user, REGISTER_CLIENT)
        return dict(register=approved)

    def get_logins_stats(self, clientid, end_date, num_days, authsource):
        if end_date:
            try:
                end_date = parse_date(end_date)
            except Exception:
                raise ValidationError('end_date not a valid date: {}'.format(end_date))
        else:
            end_date = datetime.date.today()
        try:
            num_days = int(num_days)
        except ValueError:
            raise ValidationError('num_days not an integer: {}'.format(num_days))
        if num_days < 1 or num_days > MAX_DAYS:
            msg = 'num_days should be an integer: 1 <= num_days <= {}'.format(MAX_DAYS)
            raise ValidationError(msg)
        start_date = end_date - datetime.timedelta(num_days - 1)
        dates = [start_date + datetime.timedelta(i) for i in range(num_days)]
        return list(self.session.get_logins_stats(clientid, dates, authsource, None))
