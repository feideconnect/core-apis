from coreapis.utils import parse_datetime
import uuid


post_body_minimal = {
    'id': 'testgk',
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'endpoints': ['https://foo.no'],
    'requireuser': False,
    'trust': {
        'type': 'basic',
        'username': 'username',
        'password': 'secrit',
    },
}

post_body_maximal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'id': 'max-gk',
    'created': '2015-01-12T14:05:16+01:00', 'descr': 'green',
    'status': ['lab'],
    'updated': '2015-01-12T14:05:16+01:00',
    'endpoints': ['https://foo.com', 'https://ugle.org:5000'],
    'requireuser': True,
    'httpscertpinned': '',
    'expose': {
        'userid': True,
        'clientid': True,
        'scopes': True,
        'groups': False,
        'userid-sec': ['feide'],
    },
    'scopedef': {},
    'trust': {
        'type': 'basic',
        'username': 'username',
        'password': 'secrit',
    },
}


pre_update = {
    "httpscertpinned": None,
    "scopedef": None,
    "descr": None,
    "status": None,
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": "updateable",
    "expose": {
    },
    "owner": uuid.UUID("00000000-0000-0000-0000-000000000001"),
    "trust": {
        "token": "abcderf",
        "type": "bearer"
    },
    "endpoints": [
        "https://example.com"
    ],
    "name": "pre update",
    "requireuser": False,
    "organization": None,
}
