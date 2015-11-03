import uuid
from coreapis.utils import (json_normalize, now)


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
