import uuid

from coreapis.utils import parse_datetime

post_body_minimal = {
    'name': 'per',
    'public': True,
}

post_body_maximal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'id': 'max-gk',
    'created': '2015-01-12T14:05:16+01:00', 'descr': 'green',
    'updated': '2015-01-12T14:05:16+01:00',
    'descr': 'new descr',
    'public': True,
}

user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
user2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
user3 = uuid.UUID("00000000-0000-0000-0000-000000000003")
groupid1 = uuid.UUID("00000000-0000-0000-0001-000000000001")
groupid2 = uuid.UUID("00000000-0000-0000-0001-000000000002")
group1_invitation = '62649b1d-353a-4588-8483-6f4a31863c78'
group2_invitation = '62649b1d-353a-4588-8483-6f4a31863c79'
group1 = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid1,
    "owner": user1,
    "name": "pre update",
    "descr": "some data",
    "public": False,
    'invitation_token': group1_invitation,
}
public_userinfo = {
    'userid_sec': ['p:foo'],
    'selectedsource': 'us',
    'name': {'us': 'foo'},
}
public_userinfo_view = {
    'id': 'p:foo',
    'name': 'foo',
}
group1_view = {
    "updated": "2015-01-26T16:05:59Z",
    "created": "2015-01-23T13:50:09Z",
    "id": str(groupid1),
    "owner": public_userinfo_view,
    "name": "pre update",
    "descr": "some data",
    "public": False,
}
group1_details = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid1,
    "owner": public_userinfo_view,
    "name": "pre update",
    "descr": "some data",
    "public": False,
    'invitation_token': group1_invitation,
}

group2 = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid2,
    "owner": user2,
    "name": "pre update",
    "descr": "some data",
    "public": True,
    'invitation_token': group2_invitation,
}
group2_view = {
    "updated": "2015-01-26T16:05:59Z",
    "created": "2015-01-23T13:50:09Z",
    "id": str(groupid2),
    "owner": public_userinfo_view,
    "name": "pre update",
    "descr": "some data",
    "public": True,
}


member_token = '9nFIGK7dEiuVfXdGhVcgvaQVOBZScQ_6y9Yd2BTdMizUtL8yB5b7Im5Zcr3W9hjd' # user1
