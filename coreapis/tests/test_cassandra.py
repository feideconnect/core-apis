r'''
Unit tests for cassandra-client.py in Dataporten

The database node is selected with the env var 'DP_CASSANDRA_TEST_NODE',
default 'cassandra-test-coreapis'. It must be an IP address or a DNS
name, not a URL.

The keyspace is selected with the env var 'DP_CASSANDRA_TEST_KEYSPACE',
default 'test_coreapis'.

The tests are skipped if no database is available.

Here's how to set up a test environment:

    $ docker run -d -p 9042:9042 cassandra:2.1
    wait for cassandra to initialize
    $ python <coreapis/bin> init_keyspace.py
    $ git clone git@github.com:feideconnect/cassandra-schema.git
    $ cd cassandra-schema
    $ CASSANDRA_NODE=<external_ip_or_dns> CASSANDRA_KEYSPACE=test_coreapis \
        ./migrate up

This will be automated later.

'migrate' needs the external IP of the host, as it runs in its own docker container.
'''

import unittest
import uuid
import random
import string
import os
from cassandra.cluster import NoHostAvailable
from coreapis.cassandra_client import Client
from coreapis.utils import now

TABLES = [
    'oauth_tokens',
    'oauth_authorizations',
    'clients',
    'users',
    'apigk',
    'groups',
    'group_members',
    'grep_codes',
    'organizations',
    'roles',
    'mandatory_clients',
    'remote_apigatekeepers',
]

db_node = os.environ.get('DP_CASSANDRA_TEST_NODE', 'cassandra-test-coreapis')
db_keyspace = os.environ.get('DP_CASSANDRA_TEST_KEYSPACE', 'test_coreapis')

cclient = None


def setUpModule():
    global cclient
    try:
        cclient = Client([db_node], db_keyspace)
    except NoHostAvailable:
        raise unittest.SkipTest('No database available')
    truncate_tables(cclient, TABLES)


def truncate_tables(cclient, tables):
    for table in tables:
        cclient.session.execute('TRUNCATE {}'.format(table))


def random_string(length):
    return ''.join(random.choice(string.ascii_letters + string.digits) for n in range(length))


def random_bytes(length):
    return random_string(length).encode('UTF-8')


def random_int():
    return random.randint(0, 2**30)


def id_and_owner_match(a, b):
    return a['id'] == b['id'] and a['owner'] == b['owner']


def tokens_match(a, b):
    return all([a['access_token'] == b['access_token'],
                a['clientid'] == b['clientid'],
                a['userid'] == b['userid']])


def users_match(a, b):
    return a['userid'] == b['userid'] and a['userid_sec'] == b['userid_sec']


def authz_match(a, b):
    return a['userid'] == b['userid'] and a['clientid'] == b['clientid']


def group_members_match(a, b):
    return all([a['groupid'] == b['groupid'],
                a['userid'] == b['userid'],
                a['status'] == b['status'],
                a['type'] == b['type']])


def grep_codes_match(a, b):
    return a['id'] == b['id'] and a['code'] == b['code']


def orgs_match(a, b):
    return a['id'] == b['id'] and a['organization_number'] == b['organization_number']


def roles_match(a, b):
    return all([a['feideid'] == b['feideid'],
                a['orgid'] == b['orgid'],
                a['role'] == b['role']])


def make_testscopes():
    return [random_string(10) for i in range(2)]


def make_client():
    ts_now = now()
    testscopes = make_testscopes()
    return dict(
        id=uuid.uuid4(),
        client_secret='',
        name='foo',
        descr='',
        systemdescr='',
        type='',
        redirect_uri=[],
        scopes=[testscopes[1]],
        scopes_requested=testscopes,
        orgauthorization={},
        status=[],
        privacypolicyurl='',
        homepageurl='',
        loginurl='',
        supporturl='',
        authproviders=[],
        authoptions='',
        owner=uuid.uuid4(),
        organization='',
        created=ts_now,
        updated=ts_now,
    )


def make_token():
    ts_now = now()
    testscopes = make_testscopes()
    return dict(
        access_token=uuid.uuid4(),
        clientid=uuid.uuid4(),
        userid=uuid.uuid4(),
        issued=ts_now,
        scope=testscopes,
        token_type='Bearer',
        validuntil=ts_now,
        lastuse=ts_now
    )


def make_user():
    photo = random_bytes(1025)
    source = 'foo'
    return dict(
        userid=uuid.uuid4(),
        email={},
        name={},
        profilephoto={source: photo},
        profilephotohash={},
        selectedsource=source,
        userid_sec={random_string(16), random_string(16)}
    )


def make_apigk():
    ts_now = now()
    return dict(
        id=random_string(16),
        name='',
        descr='',
        systemdescr='',
        scopes=[],
        scopes_requested=[random_string(10)],
        endpoints=[],
        trust=None,
        scopedef='{}',
        requireuser=False,
        httpscertpinned='',
        status=set(),
        privacypolicyurl='',
        docurl='',
        owner=uuid.uuid4(),
        organization='',
        created=ts_now,
        updated=ts_now
    )


def make_authorization():
    return dict(
        userid=uuid.uuid4(),
        clientid=uuid.uuid4(),
        issued=now(),
        scopes=make_testscopes(),
    )


def make_group():
    ts_now = now()
    return dict(
        id=uuid.uuid4(),
        name=random_string(16),
        descr='',
        public=False,
        owner=uuid.uuid4(),
        created=ts_now,
        updated=ts_now,
        invitation_token=random_string(32)
    )


def make_group_member():
    return dict(
        userid=uuid.uuid4(),
        groupid=uuid.uuid4(),
        type=random_string(16),
        status=random_string(16),
        added_by=uuid.uuid4(),
    )


def make_grep_code():
    return dict(
        id=random_string(16),
        title={},
        code=random_string(16),
        type=random_string(16),
        last_changed=now()
    )


def make_org():
    return dict(
        id=random_string(16),
        fs_groups=False,
        realm=random_string(16),
        type=set(),
        organization_number=random_string(16),
        name={'nb': random_string(16)},
        uiinfo=random_string(16),
        services=set()
    )


def make_role():
    return dict(
        feideid=random_string(16),
        orgid=random_string(16),
        role=set([random_string(16)]),
    )


def make_mandatory_client():
    return dict(
        realm=random_string(16),
        clientid=uuid.uuid4()
    )


def make_remgk():
    return dict(
        dn=random_string(16)
    )


class CassandraClientTests(unittest.TestCase):
    def setUp(self):
        self.cclient = cclient
        self.nrecs = 3
        self.maxrows = 100

    def tearDown(self):
        pass

    def insert_clients(self, nrecs):
        recs = [make_client() for i in range(nrecs)]
        for rec in recs:
            self.cclient.insert_client(rec)
        return recs

    def insert_token(self, token):
        self.cclient.default_columns['oauth_tokens'] = [
            'access_token',
            'clientid',
            'userid',
            'issued',
            'scope',
            'token_type',
            'validuntil',
            'lastuse',
        ]
        self.cclient.json_columns['oauth_tokens'] = []
        self.cclient.insert_generic(token, 'oauth_tokens')

    def insert_tokens(self, nrecs):
        tokens = [make_token() for i in range(nrecs)]
        for token in tokens:
            self.insert_token(token)
        return tokens

    def insert_user(self, user):
        self.cclient.insert_user(
            user['userid'],
            user['email'],
            user['name'],
            user['profilephoto'],
            user['profilephotohash'],
            user['selectedsource'],
            user['userid_sec']
        )

    def insert_users(self, nrecs):
        users = [make_user() for i in range(nrecs)]
        for user in users:
            self.insert_user(user)
        return users

    def insert_apigks(self, nrecs):
        apigks = [make_apigk() for i in range(nrecs)]
        for apigk in apigks:
            self.cclient.insert_apigk(apigk)
        return apigks

    def insert_authz(self, nrecs):
        authz = [make_authorization() for i in range(nrecs)]
        for auth in authz:
            self.cclient.update_oauth_authorization_scopes(auth)
        return authz

    def insert_groups(self, nrecs):
        groups = [make_group() for i in range(nrecs)]
        for group in groups:
            self.cclient.insert_group(group)
        return groups

    def insert_group_member(self, member):
        self.cclient.add_group_member(member['groupid'], member['userid'], member['type'],
                                      member['status'], member['added_by'])

    def insert_group_members(self, nrecs):
        members = [make_group_member() for i in range(nrecs)]
        for member in members:
            self.insert_group_member(member)
        return members

    def insert_grep_codes(self, nrecs):
        codes = [make_grep_code() for i in range(nrecs)]
        for code in codes:
            self.cclient.insert_grep_code(code)
        return codes

    def insert_org(self, org):
        self.cclient.default_columns['organizations'] = [
            'id',
            'fs_groups',
            'realm',
            'type',
            'organization_number',
            'name',
            'uiinfo',
            'services',
        ]
        self.cclient.json_columns['organizations'] = []
        self.cclient.insert_generic(org, 'organizations')

    def insert_orgs(self, nrecs):
        orgs = [make_org() for i in range(nrecs)]
        for org in orgs:
            self.insert_org(org)
        return orgs

    def insert_role(self, role):
        self.cclient.json_columns['roles'] = []
        self.cclient.insert_generic(role, 'roles')

    def insert_roles(self, nrecs):
        roles = [make_role() for i in range(nrecs)]
        for role in roles:
            self.insert_role(role)
        return roles

    def insert_mandatory_clients(self, nrecs):
        mcs = [make_mandatory_client() for i in range(nrecs)]
        for mc in mcs:
            self.cclient.add_mandatory_client(mc['realm'], mc['clientid'])
        return mcs

    def insert_remgk(self, remgk):
        self.cclient.default_columns['remote_apigatekeepers'] = ['dn']
        self.cclient.json_columns['remote_apigatekeepers'] = []
        self.cclient.insert_generic(remgk, 'remote_apigatekeepers')

    def insert_remgks(self, nrecs):
        remgks = [make_remgk() for i in range(nrecs)]
        for remgk in remgks:
            self.insert_remgk(remgk)
        return remgks

    def authorize(self, userid, clientid, scopes):
        authz = [make_authorization() for i in range(self.nrecs)]
        savedauth = authz[self.nrecs - 2]
        savedauth['userid'] = userid
        savedauth['clientid'] = clientid
        savedauth['scopes'] = scopes
        for auth in authz:
            self.cclient.update_oauth_authorization_scopes(auth)
        res = self.cclient.get_authorizations(userid)
        assert authz_match(res[0], savedauth)
        tokens = [make_token() for i in range(self.nrecs)]
        savedtoken = tokens[self.nrecs - 2]
        access_token = uuid.uuid4()
        savedtoken['access_token'] = access_token
        savedtoken['userid'] = userid
        savedtoken['clientid'] = clientid
        for token in tokens:
            self.insert_token(token)
        res = self.cclient.get_token(access_token)
        assert tokens_match(res, savedtoken)

    def setup_group_member(self):
        members = self.insert_group_members(self.nrecs)
        member = members[self.nrecs - 2]
        groupid = member['groupid']
        userid = member['userid']
        status = 'datt'
        mtype = 'ditt'
        member['status'] = status
        member['type'] = mtype
        self.cclient.set_group_member_status(groupid, userid, status)
        self.cclient.set_group_member_type(groupid, userid, mtype)
        return member

    def _test_get_rec(self, seeder, getter, key, matcher):
        recs = seeder(self.nrecs)
        rec = recs[self.nrecs - 2]
        recid = rec[key]
        res = getter(recid)
        assert matcher(res, rec)

    def test_get_client_by_id(self):
        self._test_get_rec(self.insert_clients, self.cclient.get_client_by_id, 'id',
                           id_and_owner_match)

    def _test_get_recs(self, seeder, getter, key):
        recs = seeder(self.nrecs)
        savedids = [rec[key] for rec in recs]
        res = getter()
        fetchedids = [r[key] for r in res]
        assert len(savedids) == len(fetchedids)
        savedids.sort()
        fetchedids.sort()
        assert all(a == b for a, b in zip(savedids, fetchedids))
        return res

    def test_get_clients(self):
        def get_clients():
            return self.cclient.get_clients([], [], self.maxrows)
        self.cclient.session.execute('TRUNCATE clients')
        self._test_get_recs(self.insert_clients, get_clients, 'id')

    def test_get_clients_by_owner(self):
        clients = self.insert_clients(self.nrecs)
        client = clients[self.nrecs - 2]
        owner = client['owner']
        res = self.cclient.get_clients_by_owner(owner)
        assert id_and_owner_match(res[0], client)

    def test_get_clients_by_scope(self):
        clients = self.insert_clients(self.nrecs)
        client = clients[self.nrecs - 2]
        scopes = client['scopes']
        res = self.cclient.get_clients_by_scope(scopes[0])
        assert id_and_owner_match(res[0], client)

    def test_get_clients_by_scope_requested(self):
        clients = self.insert_clients(self.nrecs)
        client = clients[self.nrecs - 2]
        scopes = client['scopes_requested']
        res = self.cclient.get_clients_by_scope_requested(scopes[0])
        assert id_and_owner_match(res[0], client)

    def test_delete_client(self):
        clients = self.insert_clients(self.nrecs)
        client = clients[self.nrecs - 2]
        clientid = client['id']
        self.authorize(uuid.uuid4(), clientid, None)
        self.cclient.delete_client(clientid)
        with self.assertRaises(KeyError):
            self.cclient.get_client_by_id(clientid)

    def test_get_generic_bad_call(self):
        with self.assertRaises(KeyError):
            self.cclient.get_generic('clients', ['feideid = ?'], [], self.maxrows)

    def _test_orgauthorization(self, realm, scopes):
        clients = self.insert_clients(self.nrecs)
        client = clients[self.nrecs - 2]
        clientid = client['id']
        self.cclient.insert_orgauthorization(clientid, realm, scopes)
        return self.cclient.get_client_by_id(clientid)

    def test_insert_orgauthorization(self):
        realm = 'uninett.no'
        scopes = '[{}]'.format(random_string(10))
        res = self._test_orgauthorization(realm, scopes)
        assert res['orgauthorization'] == {realm: scopes}

    def test_delete_orgauthorization(self):
        realm = 'uninett.no'
        scopes = '[{}]'.format(random_string(10))
        client = self._test_orgauthorization(realm, scopes)
        clientid = client['id']
        self.cclient.delete_orgauthorization(clientid, realm)
        res = self.cclient.get_client_by_id(clientid)
        assert res['orgauthorization'] is None

    def test_get_token(self):
        self._test_get_rec(self.insert_tokens, self.cclient.get_token, 'access_token',
                           tokens_match)

    def test_get_tokens_by_scope(self):
        tokens = self.insert_tokens(self.nrecs)
        token = tokens[self.nrecs - 2]
        scopes = token['scope']
        res = self.cclient.get_tokens_by_scope(scopes[0])
        assert tokens_match(res[0], token)

    def test_update_token_scopes(self):
        tokens = self.insert_tokens(self.nrecs)
        token = tokens[self.nrecs - 2]
        scopes = make_testscopes()
        self.cclient.update_token_scopes(token['access_token'], scopes)
        res = self.cclient.get_tokens_by_scope(scopes[0])
        assert tokens_match(res[0], token)

    def test_get_user_by_id(self):
        self._test_get_rec(self.insert_users, self.cclient.get_user_by_id, 'userid', users_match)

    def test_get_user_profilephoto(self):
        users = self.insert_users(self.nrecs)
        user = users[self.nrecs - 2]
        savedphotos = user['profilephoto'].values()
        userid = user['userid']
        resphoto, _ = self.cclient.get_user_profilephoto(userid)
        assert resphoto in savedphotos

    def test_get_user_no_profilephoto(self):
        user = make_user()
        self.insert_user(user)
        userid = user['userid']
        self.cclient.reset_user(userid)
        resphoto, _ = self.cclient.get_user_profilephoto(userid)
        assert resphoto is None

    def test_get_userid_by_userid_sec(self):
        users = self.insert_users(self.nrecs)
        user = users[self.nrecs - 2]
        userid = user['userid']
        sec = user['userid_sec'].copy().pop()
        self.cclient.reset_user(userid)
        res = self.cclient.get_userid_by_userid_sec(sec)
        assert res == userid

    def test_get_apigk(self):
        self._test_get_rec(self.insert_apigks, self.cclient.get_apigk, 'id', id_and_owner_match)

    def test_get_apigks(self):
        def get_apigks():
            return self.cclient.get_apigks([], [], self.maxrows)
        self.cclient.session.execute('TRUNCATE apigk')
        res = self._test_get_recs(self.insert_apigks, get_apigks, 'id')
        res.append(42)  # Checks that res behaves like a list

    def _test_delete_rec(self, seeder, deleter, getter, key):
        recs = seeder(self.nrecs)
        rec = recs[self.nrecs - 2]
        recid = rec[key]
        deleter(recid)
        with self.assertRaises(KeyError):
            getter(recid)

    def test_delete_apigk(self):
        self._test_delete_rec(self.insert_apigks, self.cclient.delete_apigk,
                              self.cclient.get_apigk, 'id')

    def _test_get_logo(self, table, seeder, getter):
        recs = seeder(self.nrecs)
        rec = recs[self.nrecs - 2]
        recid = rec['id']
        data = random_bytes(1025)
        self.cclient.save_logo(table, recid, data, now())
        logo, _ = getter(recid)
        assert data == logo

    def test_get_client_logo(self):
        self._test_get_logo('clients', self.insert_clients, self.cclient.get_client_logo)

    def test_get_apigk_logo(self):
        self._test_get_logo('apigk', self.insert_apigks, self.cclient.get_apigk_logo)

    def test_get_authorizations(self):
        authz = self.insert_authz(self.nrecs)
        auth = authz[self.nrecs - 2]
        userid = auth['userid']
        res = self.cclient.get_authorizations(userid)
        assert authz_match(res[0], auth)

    def test_delete_token(self):
        self._test_delete_rec(self.insert_tokens, self.cclient.delete_token,
                              self.cclient.get_token, 'access_token')

    def test_delete_authorization(self):
        userid = uuid.uuid4()
        clientid = uuid.uuid4()
        self.authorize(userid, clientid, None)
        self.cclient.delete_authorization(userid, clientid)
        res = self.cclient.get_authorizations(userid)
        assert list(res) == []

    def test_get_oauth_authorizations_by_scope(self):
        userid = uuid.uuid4()
        clientid = uuid.uuid4()
        testscopes = make_testscopes()
        self.authorize(userid, clientid, testscopes)
        res = self.cclient.get_oauth_authorizations_by_scope(testscopes[0])
        assert all([res[0]['userid'] == userid,
                    res[0]['clientid'] == clientid,
                    res[0]['scopes'] == testscopes])

    def test_get_group(self):
        self._test_get_rec(self.insert_groups, self.cclient.get_group, 'id', id_and_owner_match)

    def test_delete_group(self):
        self._test_delete_rec(self.insert_groups, self.cclient.delete_group,
                              self.cclient.get_group, 'id')

    def test_get_group_logo(self):
        self._test_get_logo('groups', self.insert_groups, self.cclient.get_group_logo)

    def test_get_groups(self):
        def get_groups():
            return self.cclient.get_groups([], [], self.maxrows)
        self.cclient.session.execute('TRUNCATE groups')
        self._test_get_recs(self.insert_groups, get_groups, 'id')

    def test_get_group_members(self):
        member = self.setup_group_member()
        res = self.cclient.get_group_members(member['groupid'])
        assert group_members_match(res[0], member)

    def test_set_group_member_attrs(self):
        member = self.setup_group_member()
        res = self.cclient.get_group_members(member['groupid'])
        assert group_members_match(res[0], member)

    def test_del_group_member(self):
        member = self.setup_group_member()
        groupid = member['groupid']
        userid = member['userid']
        self.cclient.del_group_member(groupid, userid)
        res = self.cclient.get_group_members(userid)
        assert len(list(res)) == 0

    def test_get_membership_data(self):
        member = self.setup_group_member()
        groupid = member['groupid']
        userid = member['userid']
        res = self.cclient.get_membership_data(groupid, userid)
        assert group_members_match(res, member)

    def test_get_group_memberships(self):
        member = self.setup_group_member()
        userid = member['userid']
        mtype = member['type']
        status = member['status']
        res = self.cclient.get_group_memberships(userid, mtype, status, self.maxrows)
        assert group_members_match(res[0], member)

    def test_get_grep_code(self):
        self._test_get_rec(self.insert_grep_codes, self.cclient.get_grep_code, 'id',
                           grep_codes_match)

    def test_get_grep_code_by_code(self):
        recs = self.insert_grep_codes(self.nrecs)
        rec = recs[self.nrecs - 2]
        code = rec['code']
        greptype = rec['type']
        res = self.cclient.get_grep_code_by_code(code, greptype)
        assert grep_codes_match(res, rec)

    def test_get_grep_code_by_code_no_match(self):
        recs = self.insert_grep_codes(self.nrecs)
        rec = recs[self.nrecs - 2]
        code = random_string(16)
        greptype = rec['type']
        with self.assertRaises(KeyError):
            self.cclient.get_grep_code_by_code(code, greptype)

    def test_get_org(self):
        self._test_get_rec(self.insert_orgs, self.cclient.get_org, 'id',
                           orgs_match)

    def test_get_org_by_realm(self):
        self._test_get_rec(self.insert_orgs, self.cclient.get_org_by_realm, 'realm',
                           orgs_match)

    def test_list_orgs(self):
        self.cclient.session.execute('TRUNCATE organizations')
        self._test_get_recs(self.insert_orgs, self.cclient.list_orgs, 'id')

    def test_get_org_logo(self):
        orgs = self.insert_orgs(self.nrecs)
        org = orgs[self.nrecs - 2]
        orgid = org['id']
        data = random_bytes(1025)
        self.cclient.save_org_logo('organizations', orgid, data, now())
        logo, _ = self.cclient.get_org_logo(orgid)
        assert data == logo

    def test_org_use_fs_groups(self):
        orgs = [make_org() for i in range(self.nrecs)]
        savedorg = orgs[self.nrecs - 2]
        savedorg['fs_groups'] = True
        for org in orgs:
            self.insert_org(org)
        res = self.cclient.org_use_fs_groups(savedorg['realm'])
        assert res
        savedorg = orgs[0]
        res = self.cclient.org_use_fs_groups(savedorg['realm'])
        assert not res
        res = self.cclient.org_use_fs_groups(random_string(16))
        assert not res

    def test_is_org_admin(self):
        roles = [make_role() for i in range(self.nrecs)]
        savedrole = roles[self.nrecs - 2]
        savedrole['role'] = set(['admin'])
        for role in roles:
            self.insert_role(role)
        feideid = savedrole['feideid']
        orgid = savedrole['orgid']
        res = self.cclient.is_org_admin(feideid, orgid)
        assert res
        res = self.cclient.is_org_admin(feideid, random_string(16))
        assert not res

    def test_get_roles(self):
        roles = self.insert_roles(self.nrecs)
        role = roles[self.nrecs - 2]
        res = self.cclient.get_roles(['feideid = ?'], [role['feideid']], self.maxrows)
        assert roles_match(res[0], role)

    def test_get_mandatory_clients(self):
        mcs = self.insert_mandatory_clients(self.nrecs)
        mc = mcs[self.nrecs - 2]
        res = self.cclient.get_mandatory_clients(mc['realm'])
        assert res[0] == mc['clientid']

    def test_del_mandatory_client(self):
        mcs = self.insert_mandatory_clients(self.nrecs)
        mc = mcs[self.nrecs - 2]
        realm = mc['realm']
        clientid = mc['clientid']
        self.cclient.del_mandatory_client(realm, clientid)
        res = self.cclient.get_mandatory_clients(realm)
        assert len(res) == 0

    def test_services(self):
        orgs = self.insert_orgs(self.nrecs)
        org = orgs[self.nrecs - 2]
        orgid = org['id']
        service = random_string(16)
        self.cclient.add_services(orgid, set([service]))
        res = self.cclient.get_org(orgid)
        assert service in res['services']
        self.cclient.del_services(orgid, set([service]))
        res = self.cclient.get_org(orgid)
        assert res['services'] is None or service not in res['services']

    def test_apigk_allowed_dn(self):
        remgks = self.insert_remgks(self.nrecs)
        remgk = remgks[self.nrecs - 2]
        res = self.cclient.apigk_allowed_dn(remgk['dn'])
        assert res
        res = self.cclient.apigk_allowed_dn(random_string(16))
        assert not res
