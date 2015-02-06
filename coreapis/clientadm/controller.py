from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.utils import LogWrapper, ts, public_userinfo, ValidationError
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

    def get(self, clientid):
        self.log.debug('Get client', clientid=clientid)
        client = self.session.get_client_by_id(clientid)
        return client

    def is_valid_gkscope(self, scope):
        scopeparts = scope.split('_')
        return (scopeparts[0] == 'gk' and len(scopeparts) > 1 and
                any([scopeparts[1] == apigk['id']
                     for apigk in self.session.get_apigks([], [], self.maxrows)]))

    def is_valid_scope(self, scope):
        return scope in self.scopedefs or self.is_valid_gkscope(scope)

    def is_auto_scope(self, scope):
        try:
            return self.scopedefs[scope]['policy']['auto']
        except KeyError:
            return False

    # Used both for add and update.
    # By default CQL does not distinguish between INSERT and UPDATE
    def _insert(self, client):
        for scope in client['scopes_requested']:
            if not self.is_valid_scope(scope):
                raise ValidationError('invalid scope: {}'.format(scope))
        for scope in client['scopes_requested']:
            if self.is_auto_scope(scope) and scope not in client['scopes']:
                client['scopes'].append(scope)
        self.session.insert_client(client['id'], client['client_secret'], client['name'],
                                   client['descr'], client['redirect_uri'],
                                   client['scopes'], client['scopes_requested'],
                                   client['status'], client['type'], client['created'],
                                   client['updated'], client['owner'])
        return client

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
