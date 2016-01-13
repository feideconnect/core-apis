from copy import deepcopy
import json
from urllib.parse import urlsplit
import uuid

import blist
import valideer as V

from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import (
    LogWrapper, timestamp_adapter, public_userinfo, public_orginfo, ValidationError, ForbiddenError, valid_url,
    EmailNotifier, json_load)
from .scope_request_notification import ScopeRequestNotification


USER_SETTABLE_STATUS_FLAGS = {'Public'}
INVALID_URISCHEMES = {'data', 'javascript', 'file', 'about'}
FEIDE_REALM_PREFIX = 'feide|realm|'
EMAIL_NOTIFICATIONS_CONFIG_KEY = 'notifications.email.'


def is_valid_uri(uri):
    parsed = urlsplit(uri)
    scheme = parsed.scheme
    if len(scheme) == 0 or scheme in INVALID_URISCHEMES:
        return False
    elif scheme in ['http', 'https']:
        return len(parsed.netloc) > 0
    else:
        return True


def get_scopedefs(filename):
    return json_load(filename, fallback={})


def is_gkscopename(name):
    return name.startswith('gk_')


def filter_missing_mainscope(scopes):
    return [scope for scope in scopes if gk_mainscope(scope) in scopes]


def gk_mainscope(name):
    if not is_gkscopename(name):
        return name
    nameparts = name.split('_')
    if len(nameparts) == 2:
        return name
    else:
        return "_".join(nameparts[:2])


def has_gkscope_match(scope, gkscopes):
    return any(scope == gkscope or scope.startswith(gkscope + '_')
               for gkscope in gkscopes)


def cache(data, key, fetch):
    if key in data:
        return data[key]
    value = fetch(key)
    data[key] = value
    return value


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
        scopedefs_file = settings.get('clientadm_scopedefs_file')
        maxrows = settings.get('clientadm_maxrows')
        system_moderator = settings.get('clientadm_system_moderator', '')
        super(ClientAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('clientadm.ClientAdmController')
        self.scopedefs = get_scopedefs(scopedefs_file)
        self.system_moderator = system_moderator
        self.email_notification_settings = {'enabled': False}
        self.email_notification_settings.update({
            '.'.join(k.split('.')[2:]): v
            for k, v in settings.items()
            if k.startswith(EMAIL_NOTIFICATIONS_CONFIG_KEY)
        })

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
        return [self.get_public_client(c) for c in clients if c]

    def has_permission(self, client, user):
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

    def add_scope_if_approved(self, client, scopedef, scope):
        try:
            if scopedef['policy']['auto']:
                self.log.debug('Accept scope', scope=scope)
                client['scopes'].append(scope)
        except KeyError:
            pass

    def handle_gksubscope_request(self, client, scope, subname, subscopes):
        try:
            scopedef = subscopes[subname]
        except:
            raise ValidationError('invalid scope: {}'.format(scope))
        self.add_scope_if_approved(client, scopedef, scope)

    def handle_gkscope_request(self, client, scope):
        nameparts = scope.split('_')
        gkname = nameparts[1]
        try:
            apigk = self.session.get_apigk(gkname)
            scopedef = apigk.get('scopedef', {})
            if not scopedef:
                scopedef = {}
        except:
            raise ValidationError('invalid scope: {}'.format(scope))
        if str(apigk['owner']) == str(client['owner']):
            client['scopes'].append(scope)
        elif len(nameparts) > 2:
            if 'subscopes' in scopedef:
                subname = nameparts[2]
                self.handle_gksubscope_request(client, scope, subname, scopedef['subscopes'])
            else:
                raise ValidationError('invalid scope: {}'.format(scope))
        else:
            self.add_scope_if_approved(client, scopedef, scope)

    def handle_scope_request(self, client, scope):
        if is_gkscopename(scope):
            self.handle_gkscope_request(client, scope)
        elif not scope in self.scopedefs:
            raise ValidationError('invalid scope: {}'.format(scope))
        else:
            self.add_scope_if_approved(client, self.scopedefs[scope], scope)

    def insert_client(self, client):
        sessclient = deepcopy(client)
        orgauthz = sessclient.get('orgauthorization', None)
        if orgauthz:
            for k, v in orgauthz.items():
                orgauthz[k] = json.dumps(v)
        self.session.insert_client(sessclient)

    def get_gk_moderator(self, scope):
        apigk = self.scope_to_gk(scope)
        owner = self.session.get_user_by_id(apigk['owner'])
        try:
            return list(owner['email'].values())[0]
        except (AttributeError, IndexError):
            return None

    def get_moderator(self, scope):
        if is_gkscopename(scope):
            return self.get_gk_moderator(scope)
        else:
            return self.system_moderator

    # Group scopes by apigk, with a separate bucket for built-in scopes
    # Example:
    # {'system': {systemscopes},
    #  'gk_foo': {'gk_foo', gk_foo_bar'},
    #  'gk_baz': {'gk_baz1}}
    def get_scopes_by_base(self, modscopes):
        ret = {}
        for scope in modscopes:
            if is_gkscopename(scope):
                base = gk_mainscope(scope)
            else:
                base = 'system'
            ret[base] = ret.get(base, set())
            ret[base].add(scope)
        return ret

    def notify_moderator(self, moderator, client, scopes):
        apigk = None
        first_scope = list(scopes)[0]
        if is_gkscopename(first_scope):
            apigk = self.scope_to_gk(first_scope)
        notification = ScopeRequestNotification(self.get_public_client(client), scopes, apigk)
        subject = notification.get_subject()
        body = notification.get_body()
        self.log.debug('notify_moderator', moderator=moderator, subject=subject)
        EmailNotifier(self.email_notification_settings).notify(moderator, subject, body)

    def notify_moderators(self, client):
        modscopes = set(client['scopes_requested']).difference(set(client['scopes']))
        for base, scopes in self.get_scopes_by_base(modscopes).items():
            mod = self.get_moderator(base)
            if mod and len(mod) > 0:
                self.notify_moderator(mod, client, scopes)
            else:
                self.log.debug('No moderator address', base=base, mod=mod)

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client):
        client['scopes_requested'] = filter_missing_mainscope(client['scopes_requested'])
        client['scopes'] = list(set(client['scopes']).intersection(set(client['scopes_requested'])))
        for scope in set(client['scopes_requested']).difference(set(client['scopes'])):
            self.handle_scope_request(client, scope)
        self.insert_client(client)
        self.notify_moderators(client)
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
        for scope in client['scopes_requested']:
            if not scope in client['scopes']:
                self.handle_scope_request(client, scope)
        return self._insert(client)

    def delete(self, clientid):
        self.log.debug('Delete client', clientid=clientid)
        self.session.delete_client(clientid)

    def get_logo(self, clientid):
        return self.session.get_client_logo(clientid)

    def _save_logo(self, clientid, data, updated):
        self.session.save_logo('clients', clientid, data, updated)

    def get_public_client(self, client, users=None, orgs=None):
        if users is None:
            users = {}
        if orgs is None:
            orgs = {}
        pubclient = {attr: client[attr] for attr in self.public_attrs}
        try:
            def get_user(userid):
                return public_userinfo(self.session.get_user_by_id(userid))

            def get_org(orgid):
                return public_orginfo(self.session.get_org(orgid))
            pubclient['owner'] = cache(users, client['owner'], get_user)
            org = client.get('organization', None)
            if org:
                pubclient['organization'] = cache(orgs, org, get_org)
        except KeyError:
            self.log.warn('Client owner does not exist in users table',
                          clientid=client['id'], userid=client['owner'])
            return None
        return pubclient

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
        pubclient = self.get_public_client(client)
        pubclient['scopeauthorizations'] = scopeauthz
        return pubclient

    def get_realmclients(self, realm):
        return [self.get_realmclient(realm, k, v)
                for k, v in self.get_realmclient_scopes(realm).items()]

    def get_gkscope_client(self, client, gkscopes, users=None, orgs=None):
        gkclient = self.get_public_client(client, users, orgs)
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
            for client in (self.session.get_clients_by_scope(gkscope) +
                           self.session.get_clients_by_scope_requested(gkscope)):
                if not client['id'] in clientdict:
                    clientdict[client['id']] = self.get_gkscope_client(client, gkscopes,
                                                                       users, orgs)
        return list(clientdict.values())

    def list_public_scopes(self):
        self.log.debug('List public scopes')
        return {k: v for k, v in self.scopedefs.items() if v.get('public', False)}

    def scope_to_gk(self, scopename):
        try:
            nameparts = scopename.split('_')
            gkname = nameparts[1]
            return self.session.get_apigk(gkname)
        except KeyError:
            return None

    def validate_gkscope(self, user, scope):
        if not is_gkscopename(scope):
            raise ForbiddenError('{} is not an API Gatekeeper'.format(scope))
        gk = self.scope_to_gk(scope)
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
        return self.is_org_admin(user, org['id'])

    @staticmethod
    def get_orgauthorization(client, realm):
        return client['orgauthorization'].get(realm, [])

    def update_orgauthorization(self, client, realm, scopes):
        self.session.insert_orgauthorization(client['id'], realm, json.dumps(scopes))

    def delete_orgauthorization(self, client, realm):
        self.session.delete_orgauthorization(client['id'], realm)
