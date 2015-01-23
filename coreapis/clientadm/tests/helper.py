import uuid
from aniso8601 import parse_datetime

userid_own   = '00000000-0000-0000-0000-000000000001'
userid_other = '00000000-0000-0000-0000-000000000002'
clientid     = '00000000-0000-0000-0000-000000000003'
date_created = '2015-01-12T14:05:16+01:00'
testscope    = 'clientadmin'
otherscope   = 'userlist'
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
    'name': 'per', 'scopes': [testscope], 'redirect_uri': [testuri],
    'owner': uuid.UUID(userid_own),
    'id': uuid.UUID(clientid),
    'client_secret': 'sekrit', 'created': parse_datetime(date_created),
    'descr': 'green',
    'scopes_requested': [testscope], 'status': ['lab'], 'type': 'client',
    'updated': parse_datetime(date_created)
}


