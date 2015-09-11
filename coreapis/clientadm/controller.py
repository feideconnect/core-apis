from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts, public_userinfo, public_orginfo, ValidationError, ForbiddenError
from urllib.parse import urlsplit
import blist
import json
import uuid
import valideer as V


USER_SETTABLE_STATUS_FLAGS = {'Public'}
INVALID_URISCHEMES = {'data', 'javascript', 'file', 'about'}


def is_valid_uri(uri):
    parsed = urlsplit(uri)
    scheme = parsed.scheme
    if len(scheme) == 0 or scheme in INVALID_URISCHEMES:
        return False
    elif scheme in ['http', 'https']:
        return len(parsed.netloc) > 0
    else:
        return True


# Raises exception if filename is given, but open fails
def get_scopedefs(filename):
    if filename:
        with open(filename) as fh:
            return json.load(fh)
    else:
        return {}


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
        'created': V.AdaptBy(ts),
        'id': V.Nullable(V.AdaptTo(uuid.UUID)),
        'owner': V.AdaptTo(uuid.UUID),
        'organization': V.Nullable('string', None),
        'updated': V.AdaptBy(ts),
        # Other attributes
        'client_secret': V.Nullable('string', ''),
        'descr': V.Nullable('string', ''),
        'scopes': V.Nullable(['string'], lambda: list()),
        'orgauthorization': V.Nullable({}),
        'authproviders': V.Nullable(['string'], lambda: list()),
        'status': V.Nullable(['string'], lambda: list()),
        'type': V.Nullable('string', ''),
    }
    public_attrs = ['id', 'name', 'descr', 'redirect_uri', 'owner', 'organization', 'authproviders']
    scope_attrs = ['scopes', 'scopes_requested']

    def __init__(self, contact_points, keyspace, scopedef_file, maxrows):
        super(ClientAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('clientadm.ClientAdmController')
        self.scopedefs = get_scopedefs(scopedef_file)

    @staticmethod
    def adapt_client(client):
        for k, v in client.items():
            if k == 'orgauthorization':
                if v:
                    client[k] = {k2: json.loads(v2) for k2, v2 in v.items()}
                else:
                    client[k] = {}
            elif isinstance(v, blist.sortedset):
                client[k] = list(v)
        return client

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
        self.session.insert_client(client['id'], client['client_secret'], client['name'],
                                   client['descr'], client['redirect_uri'],
                                   client['scopes'], client['scopes_requested'],
                                   client['status'], client['type'], client['created'],
                                   client['updated'], client['owner'],
                                   client['organization'], client['authproviders'])

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client):
        client['scopes_requested'] = filter_missing_mainscope(client['scopes_requested'])
        client['scopes'] = list(set(client['scopes']).intersection(set(client['scopes_requested'])))
        for scope in set(client['scopes_requested']).difference(set(client['scopes'])):
            self.handle_scope_request(client, scope)
        self.insert_client(client)
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

    def get_gkscope_client(self, client, gkscopes, users=None, orgs=None):
        gkclient = self.get_public_client(client, users, orgs)
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
                    clientdict[client['id']] = self.get_gkscope_client(client, gkscopes, users, orgs)
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

    def validate_gkscope(self, client, user, scope):
        if not is_gkscopename(scope):
            raise ForbiddenError('{} is not an API Gatekeeper'.format(scope))
        gk = self.scope_to_gk(scope)
        if not gk or not self.has_permission(gk, user):
            raise ForbiddenError('User does not have access to manage API Gatekeeper')

    def add_gkscopes(self, client, user, scopes_add):
        for scope in [scope for scope in scopes_add if scope not in client['scopes']]:
            if not scope in client['scopes_requested']:
                raise ForbiddenError('Client owner has not requested scope {}'.format(scope))
            self.validate_gkscope(client, user, scope)
            client['scopes'].append(scope)
        return client

    def remove_gkscopes(self, client, user, scopes_remove):
        for scope in scopes_remove:
            self.validate_gkscope(client, user, scope)
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
