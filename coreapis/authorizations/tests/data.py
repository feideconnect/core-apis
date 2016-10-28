import uuid

from aniso8601 import parse_datetime
from cassandra.util import SortedSet

from coreapis.utils import (json_normalize, now)


date_created = '2015-01-12T13:05:16Z'
user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
client1 = "00000000-0000-0000-0001-000000000001"
group1 = uuid.UUID("00000000-0000-0000-0002-000000000001")
testgk = 'gk_test1'
testgk_foo = testgk + '_foo'

authz1 = {
    'userid': user1,
    'clientid': client1,
    'issued': now(),
    'scopes': [testgk, testgk_foo]
}

ret_authz1 = json_normalize(authz1.copy())
ret_authz1['client'] = {'id': client1, 'name': 'foo'}
del ret_authz1['clientid']

users = {
    user1: {
        'userid_sec': ['p:foo'],
        'selectedsource': 'us',
        'name': {'us': 'foo'},
        'userid': user1,
        'email': {'us': 'test@example.org'},
    }
}


clients = {
    client1: {
        'name': 'per',
        'scopes': SortedSet(),
        'redirect_uri': ['https://test.example.com'],
        'owner': user1,
        'organization': None,
        'id': uuid.UUID(client1),
        'client_secret': 'sekrit',
        'created': parse_datetime(date_created),
        'descr': 'green',
        'scopes_requested': SortedSet(['ugle']),
        'status': ['lab'],
        'type': 'client',
        'authproviders': [],
        'orgauthorization': {},
        'systemdescr': None,
        'privacypolicyurl': None,
        'homepageurl': None,
        'loginurl': None,
        'supporturl': None,
        'authoptions': None,
        'updated': parse_datetime(date_created),
        'admins': [],
        'admin_contact': None,
    }
}
