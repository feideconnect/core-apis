import blist
import uuid
import json
from copy import deepcopy
from aniso8601 import parse_datetime

userid_own = '00000000-0000-0000-0000-000000000001'
userid_other = '00000000-0000-0000-0000-000000000002'
userid_third = '00000000-0000-0000-0000-000000000003'
clientid = '00000000-0000-0000-0000-000000000004'
date_created = '2015-01-12T13:05:16Z'
# testscope has policy auto=false, otherscope has auto=true
testscope = 'clientadmin'
otherscope = 'userinfo-feide'
testgk = 'gk_test1'
othergk = 'gk_test2'
owngk = 'gk_test3'
nullscopedefgk = 'gk_nullscopedef'
testuris = [
    'http://example.org',
    'https://example.org',
    'custom:whatever',
]
baduris = [
    'nocolon',
    'http:noslash',
    'http:/oneslash',
    'file://etc/motd',
    'data:whatever',
    'javascript:whoknows',
    'about:connect',
]
testrealm = 'example.org'
prefixed_realm = 'feide|realm|' + testrealm

userstatus = 'Public'
reservedstatus = 'Mandatory'

post_body_minimal = {
    'name': 'per', 'scopes_requested': [testscope], 'redirect_uri': testuris
}

post_body_other_owner = {
    'name': 'per', 'scopes_requested': [testscope], 'redirect_uri': testuris, 'owner': userid_other
}

post_body_maximal = {
    'name': 'per', 'scopes': [], 'redirect_uri': testuris,
    'owner': userid_own, 'id': clientid,
    'client_secret': 'sekrit', 'descr': 'green',
    'scopes_requested': [testscope], 'status': ['lab'], 'type': 'client',
    'systemdescr': 'Awesome!',
    'privacypolicyurl': 'http://www.seoghor.no',
    'homepageurl': 'http://www.altavista.com',
    'loginurl': 'http://altinn.no',
    'supporturl': 'http://www.google.com',
    'authoptions': {'this': 'that'},
}

retrieved_client = {
    'name': 'per', 'scopes': blist.sortedset(), 'redirect_uri': testuris,
    'owner': uuid.UUID(userid_own),
    'organization': None,
    'id': uuid.UUID(clientid),
    'client_secret': 'sekrit', 'created': parse_datetime(date_created),
    'descr': 'green',
    'scopes_requested': blist.sortedset([testscope]), 'status': ['lab'], 'type': 'client',
    'authproviders': [],
    'orgauthorization': {},
    'systemdescr': None,
    'privacypolicyurl': None,
    'homepageurl': None,
    'loginurl': None,
    'supporturl': None,
    'authoptions': None,
    'updated': parse_datetime(date_created)
}

retrieved_user = {
    'userid_sec': ['p:foo'],
    'selectedsource': 'us',
    'name': {'us': 'foo'},
    'userid': uuid.UUID(userid_own),
}

orgadmin_policy = {
    'target': [prefixed_realm],
    'moderate': True
}

subscope_policy = {
    'auto': True,
    'orgadmin': orgadmin_policy
}

retrieved_gk_clients = [deepcopy(retrieved_client) for i in range(4)]

retrieved_gk_clients[0].update({
    'id': '00000000-0000-0000-0000-000000000004',
    'scopes_requested': [testgk]
})

retrieved_gk_clients[1].update({
    'id': '00000000-0000-0000-0000-000000000004',
    'scopes_requested': []
})

retrieved_gk_clients[2].update({
    'id': '00000000-0000-0000-0000-000000000005',
    'scopes_requested': [othergk]
})

testgk_foo = testgk + '_foo'
retrieved_gk_clients[3].update({
    'id': '00000000-0000-0000-0000-000000000006',
    'owner': uuid.UUID(userid_own),
    'scopes': [testgk, testgk_foo],
    'scopes_requested': [testgk, testgk_foo, othergk],
    'orgauthorization': {testrealm: json.dumps([testgk, testgk_foo])}
})

retrieved_gk_client = retrieved_gk_clients[0]

apigks = {testgk.split('_')[1]: {'owner': uuid.UUID(userid_other),
                                 'scopedef': {'subscopes': {'foo': {'policy': subscope_policy}}}},
          othergk.split('_')[1]: {'owner': uuid.UUID(userid_third),
                                  'scopedef': {}},
          owngk.split('_')[1]: {'owner': uuid.UUID(userid_own),
                                'scopedef': {}},
          nullscopedefgk.split('_')[1]: {'owner': uuid.UUID(userid_other), 'scopedef': None}}


def httptime(timestamp):
    return timestamp.strftime("%a, %d %b %Y %H:%M:%S +0000")


def mock_get_apigk(gkid):
    ret = deepcopy(apigks[gkid])
    ret.update({'id': gkid})
    return ret


retrieved_apigks = [mock_get_apigk(id) for id in apigks]


def mock_get_clients_by_scope(scope):
    return [client for client in retrieved_gk_clients
            if scope in client['scopes']]


def mock_get_clients_by_scope_requested(scope):
    return [client for client in retrieved_gk_clients
            if scope in client['scopes_requested']]
