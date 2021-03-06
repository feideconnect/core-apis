from copy import deepcopy
import itertools
import json
from urllib.parse import urlsplit
import uuid

import datetime
from aniso8601 import parse_date
import cassandra.util
import valideer as V

from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.scopes import is_gkscopename, has_gkscope_match
from coreapis.scopes.manager import ScopesManager
from coreapis.authproviders import AUTHPROVMGR, REGISTER_CLIENT
from coreapis.utils import (
    LogWrapper, timestamp_adapter, ValidationError, ForbiddenError,
    valid_url, valid_name, valid_description, userinfo_for_log,
    get_platform_admins, get_approved_creators, PRIV_PLATFORM_ADMIN, public_userinfo,
    public_orginfo)


USER_SETTABLE_STATUS_FLAGS = {'Public'}
INVALID_URISCHEMES = {'data', 'javascript', 'file', 'about'}
FEIDE_REALM_PREFIX = 'feide|realm|'
MAX_DAYS = 14


def is_valid_uri(uri):
    parsed = urlsplit(uri)
    scheme = parsed.scheme
    if not scheme or scheme in INVALID_URISCHEMES:
        return False
    if scheme in ['http', 'https']:
        return bool(parsed.netloc)
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


def client_sortkey(client):
    sortkey = (client.get('count_tokens') or 0) + (client.get('count_users') or 0)
    if client.get('organization'):
        sortkey += 10000000
    return sortkey


class ClientAdmController(CrudControllerBase):
    schema = {
        # Required
        '+name': V.AdaptBy(valid_name, traps=ValueError),
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
        'descr': V.Nullable(V.AdaptBy(valid_description, traps=ValueError), ''),
        'scopes': V.Nullable(['string'], ()),
        'authproviders': V.Nullable(['string'], ()),
        'status': V.Nullable(['string'], ()),
        'type': V.Nullable('string', ''),
        'systemdescr': V.Nullable(V.AdaptBy(valid_description, traps=ValueError), ''),
        'privacypolicyurl': V.Nullable(valid_url),
        'homepageurl': V.Nullable(valid_url),
        'loginurl': V.Nullable(valid_url),
        'supporturl': V.Nullable(valid_url),
        'authoptions': V.Nullable({}),
        'admins': V.Nullable(['string'], ()),
        'admin_contact': V.Nullable('string', None),
    }
    public_attrs = ['id', 'name', 'descr', 'redirect_uri', 'owner', 'organization', 'authproviders',
                    'systemdescr', 'privacypolicyurl', 'homepageurl', 'loginurl', 'supporturl',
                    'scopes', 'status']
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
        approved_creators_file = settings.get('approved_creators_file')
        self.approved_creators = set(get_approved_creators(approved_creators_file))
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
        return self._list(selectors, values, scope)

    def list_personal(self, owner, scope=None):
        return [c for c in self.list_by_owner(owner, scope) if c['organization'] is None]

    def list_by_admin(self, admin, scope=None):
        selectors = ['admins contains ?']
        values = [admin]
        clients = self._list(selectors, values, scope)
        return [c for c in clients]

    def list_delegated(self, userid, scope, token):
        delegated = []
        delegated_ids = set()
        groupids = set(self.get_my_groupids(token))
        for groupid in groupids:
            clients = self.list_by_admin(groupid, scope)
            for client in clients:
                clientid = client['id']
                if clientid not in delegated_ids:
                    delegated.append(client)
                    delegated_ids.add(clientid)
        return delegated

    def list_by_organization(self, organization, scope=None):
        selectors = ['organization = ?']
        values = [organization]
        return self._list(selectors, values, scope)

    def list_all(self, scope=None):
        clients = self._list([], [], scope)
        self.session.add_client_counters(clients)
        return sorted(clients,
                      key=client_sortkey, reverse=True)

    def get_public_client_list(self, clients):
        owner_ids = list({c['owner'] for c in clients})
        users = {uid: public_userinfo(user)
                 for uid, user in self.session.get_users(owner_ids).items()}
        org_ids = list({c['organization'] for c in clients if c.get('organization')})
        orgs = {oid: public_orginfo(org) for oid, org in self.session.get_orgs(org_ids).items()}
        return [self.get_public_info(c, users, orgs) for c in clients if c]

    def public_clients(self, orgauthorization, status):
        selectors = []
        values = []
        if orgauthorization:
            selectors = ['orgauthorization contains key ?']
            values = [orgauthorization]
        if status:
            selectors.append('status contains ?')
            values.append(status)
        clients = self._list(selectors, values, None)
        self.session.add_client_counters(clients)

        clients = sorted(clients,
                         key=client_sortkey, reverse=True)
        return self.get_public_client_list(clients)

    def is_owner(self, user, client):
        if client['owner'] == user['userid']:
            return True
        return False

    def is_delegated_admin(self, client, token):
        admins = set(client.get('admins') or [])
        if not admins:
            return False
        groupids = set(self.get_my_groupids(token))
        return bool(admins.intersection(groupids))

    def has_permission(self, client, user, token):
        if user is None:
            return False
        if self.is_platform_admin(user):
            return True
        org = client.get('organization', None)
        if ((org and self.is_org_admin(user, org)) or
                (not org and self.is_owner(user, client))):
            return True
        return self.is_delegated_admin(client, token)

    def has_add_permission(self, user, token):
        groupids = set(self.get_my_groupids(token))
        allowed_for_id_provider = AUTHPROVMGR.has_user_permission(user, REGISTER_CLIENT)
        approved_creator = bool(set(self.approved_creators).intersection(groupids))
        return allowed_for_id_provider or approved_creator

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
        AUTHPROVMGR.check_client_update(self.session, client)
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
                for subname, subscopedef in subscopes.items():
                    res.update(self.get_scope_targets('{}_{}'.format(name, subname), subscopedef))
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
        gkclient.update({'admin_contact': self.get_admin_contact(client)})
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

    def add_scopes(self, client, scopes_add, privileges):
        for scope in [scope for scope in scopes_add if scope not in client['scopes']]:
            if scope not in client['scopes_requested']:
                raise ForbiddenError('Client owner has not requested scope {}'.format(scope))
            self.scopemgr.handle_scope_request(client, scope, privileges)
        return client

    def remove_scopes(self, client, scopes_remove):
        for scope in scopes_remove:
            if scope in client['scopes']:
                client['scopes'].remove(scope)
            if scope in client['scopes_requested']:
                client['scopes_requested'].remove(scope)
        return client

    def update_scopes(self, client, user, scopes_add, scopes_remove):
        client = self.add_scopes(client, scopes_add, self.get_privileges(user))
        client = self.remove_scopes(client, scopes_remove)
        self.log.info('updating scopes for client',
                      audit=True, clientid=client['id'],
                      scopes_add=scopes_add, scopes_remove=scopes_remove,
                      user=userinfo_for_log(user))
        self.insert_client(client)
        self.scopemgr.notify_moderators(client)
        return client

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

    def get_policy(self, user, token):
        approved = self.has_add_permission(user, token)
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
