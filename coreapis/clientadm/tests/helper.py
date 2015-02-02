import uuid
from copy import deepcopy
from aniso8601 import parse_datetime

userid_own   = '00000000-0000-0000-0000-000000000001'
userid_other = '00000000-0000-0000-0000-000000000002'
clientid     = '00000000-0000-0000-0000-000000000003'
date_created = '2015-01-12T13:05:16Z'
testscope    = 'gk_test1'
otherscope   = 'gk_test2'
testuri      = 'http://example.org'

post_body_minimal = {
    'name': 'per', 'scopes_requested': [testscope], 'redirect_uri': [testuri]
}

post_body_other_owner = {
    'name': 'per', 'scopes_requested': [testscope], 'redirect_uri': [testuri], 'owner': userid_other
}

post_body_maximal = {
    'name': 'per', 'scopes': [], 'redirect_uri': [testuri],
    'owner': userid_own, 'id': clientid,
    'client_secret': 'sekrit', 'descr': 'green',
    'scopes_requested': [testscope], 'status': ['lab'], 'type': 'client'
}

retrieved_client = {
    'name': 'per', 'scopes': [], 'redirect_uri': [testuri],
    'owner': uuid.UUID(userid_own),
    'id': uuid.UUID(clientid),
    'client_secret': 'sekrit', 'created': parse_datetime(date_created),
    'descr': 'green',
    'scopes_requested': [testscope], 'status': ['lab'], 'type': 'client',
    'updated': parse_datetime(date_created)
}

retrieved_user =  {
    'userid_sec': ['p:foo'],
    'selectedsource': 'us',
    'name': {'us': 'foo'},
}

retrieved_clients = [deepcopy(retrieved_client) for i in range(4)]

retrieved_clients[1].update({
    'id': '00000000-0000-0000-0000-000000000004',
    'scopes_requested': []
})

retrieved_clients[2].update({
    'id': '00000000-0000-0000-0000-000000000005',
    'scopes_requested': [otherscope]
})

retrieved_clients[3].update({
    'id': '00000000-0000-0000-0000-000000000006',
    'scopes': [testscope],
    'scopes_requested': [testscope,otherscope],
})

def httptime(timestamp):
    return timestamp.strftime("%a, %d %b %Y %H:%M:%S +0000")


def mock_get_clients_by_scope(scope):
    return [ client for client in retrieved_clients
      if scope in client['scopes']]

def mock_get_clients_by_scope_requested(scope):
    return [ client for client in retrieved_clients
             if scope in client['scopes_requested']]
