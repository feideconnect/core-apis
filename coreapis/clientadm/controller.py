from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts, public_userinfo, ValidationError, ForbiddenError
import blist
import json
import uuid
import valideer as V


# Raises exception if filename is given, but open fails
def get_scopedefs(filename):
    if filename:
        with open(filename) as fh:
            return json.load(fh)
    else:
        return {}


def is_gkscopename(name):
    return name.startswith('gk_')


def has_gkscope_match(scope, gkscopes):
    return any(scope == gkscope or scope.startswith(gkscope + '_')
               for gkscope in gkscopes)


class ClientAdmController(CrudControllerBase):
    FILTER_KEYS = {
        'owner': {'sel':  'owner = ?',
                  'cast': uuid.UUID},
        'scope': {'sel':  'scopes contains ?',
                  'cast': lambda u: u}
    }
    schema = {
        # Required
        '+name': 'string',
        '+redirect_uri': V.HomogeneousSequence(item_schema='string', min_length=1),
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
        'status': V.Nullable(['string'], lambda: list()),
        'type': V.Nullable('string', ''),
    }
    public_attrs = ['id', 'name', 'descr', 'redirect_uri', 'owner']
    scope_attrs = ['scopes', 'scopes_requested']

    def __init__(self, contact_points, keyspace, scopedef_file, maxrows):
        super(ClientAdmController, self).__init__(maxrows)
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('clientadm.ClientAdmController')
        self.scopedefs = get_scopedefs(scopedef_file)

    def _list(self, selectors, values, maxrows):
        return self.session.get_clients(selectors, values, maxrows)

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
        client = self.session.get_client_by_id(clientid)
        for k, v in client.items():
            if isinstance(v, blist.sortedset):
                client[k] = list(v)
        return client

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
                                   client['organization'])

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client):
        client['scopes'] = list(set(client['scopes']).intersection(set(client['scopes_requested'])))
        for scope in set(client['scopes_requested']).difference(set(client['scopes'])):
            self.handle_scope_request(client, scope)
        self.insert_client(client)
        return client

    def update(self, itemid, attrs):
        client = self.get(itemid)
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

    def get_public_client(self, client):
        pubclient = {attr: client[attr] for attr in self.public_attrs}
        pubclient['owner'] = public_userinfo(
            self.session.get_user_by_id(client['owner']))
        return pubclient

    def get_gkscope_client(self, client, gkscopes):
        gkclient = self.get_public_client(client)
        gkclient.update({attr: [] for attr in self.scope_attrs})
        for attr in self.scope_attrs:
            clientscopes = client[attr]
            if clientscopes:
                gkclient[attr] = [scope for scope in clientscopes
                                  if has_gkscope_match(scope, gkscopes)]
        return gkclient

    def get_gkscope_clients(self, gkscopes):
        clientdict = {}
        for gkscope in gkscopes:
            for client in (self.session.get_clients_by_scope(gkscope) +
                           self.session.get_clients_by_scope_requested(gkscope)):
                if not client['id'] in clientdict:
                    clientdict[client['id']] = self.get_gkscope_client(client, gkscopes)
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
