# Client Administration API for Feide Connect

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Creating a client

    $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{ "name" : "per", "scopes_requested" : ["clientadmin"],
          "redirect_uri" : ["http://example.org"] }' \
    'http://api.dev.feideconnect.no:6543/clientadm/clients/'

    {"type": "", "name": "per", "status": [], "redirect_uri": ["http://example.org"],
     "client_secret": "", "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-22T10:59:03.585600+00:00",
     "scopes": [], "scopes_requested": ["clientadmin"], "descr": "",
     "created": "2015-01-22T10:59:03.585600+00:00"}

Fills in `id` if not given. `name` must be given. `scopes_requested` and
`redirect_uri` must each have at least one member. `owner` is set to
user. `created`, `scopes` and `updated` may be given, but are silently
ignored - values are set by system.

Returns `201 Created` with url in `Location` header, and client as json in
body. Returns `409 Conflict` if `id` is given and is already in
use. Returns `400 Bad Request` if request body violates the schema or is
malformed in some way.

## Updating a client

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"descr": "test"}' \
    'http://api.dev.feideconnect.no:6543/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"type": "", "name": "per", "status": [], "client_secret": "",
     "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820",
     "updated": "2015-01-22T11:03:29.983120+00:00", "scopes": [],
     "scopes_requested": ["clientadmin"], "descr": "test",
     "created": "2015-01-22T10:59:03.585000"}

`id`, `created`, `owner`, `scopes` and `updated` may be given, but are
silently ignored.

Returns `200 OK`, and client as json in body. Returns `400 Bad
Request` if request body violates the schema or is malformed in some
way. Returns `401 Not Authorized` if trying to update a client not
owned by user.Returns `404 Not Found` if client does not exist.

## Fetching a client

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"type": "", "name": "per", "status": null, "client_secret": "",
     "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-22T11:03:29.983000",
     "scopes": null, "scopes_requested": ["clientadmin"], "descr": "test",
     "created": "2015-01-22T10:59:03.585000"}

Returns `401 Not Authorized` if trying to fetch a client not owned by
user, `404 Not Found` if client does not exist,

## Listing all clients owned by user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/clientadm/clients/'

    [{"type": "", "name": "per", "status": null, "client_secret": "",
      "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
      "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-22T11:03:29.983000",
      "scopes": null, "scopes_requested": ["clientadmin"], "descr": "test",
      "created": "2015-01-22T10:59:03.585000"},
     {"type": "client", "name": "test_clientadm", "status": ["production"],
      "client_secret": "88c7cdbf-d2bd-4d1b-825d-683770cd4bd3",
      "redirect_uri": ["http://example.org"], "id": "f3f043db-9fd6-4c5a-b0bc-61992bea9eca",
      "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-12T13:05:16.884000",
      "scopes": ["clientadmin"], "scopes_requested": ["clientadmin"],
      "descr": "Test client for client admin api", "created": "2015-01-12T13:05:16.884000"}]

Returns `200 OK`, and list of clients as json in body. Status is `200 OK`
even if resulting list is empty.

## Filtering list of clients by scope

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/clientadm/clients/?scope=clientadmin'

    [{"type": "client", "name": "test_clientadm", "status": ["production"],
      "client_secret": "88c7cdbf-d2bd-4d1b-825d-683770cd4bd3",
      "redirect_uri": ["http://example.org"], "id": "f3f043db-9fd6-4c5a-b0bc-61992bea9eca",
      "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-12T13:05:16.884000",
      "scopes": ["clientadmin"], "scopes_requested": ["clientadmin"],
      "descr": "Test client for client admin api", "created": "2015-01-12T13:05:16.884000"}]

Returns `200 OK`, and list of clients as json in body. Status is `200 OK`
even if resulting list is empty. Returns `400 Bad Request` if parameters
are not one of scope and owner, or if a parmeter value is missing or malformed.

## Deleting a client

    $ curl -v -X DELETE -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

Returns `204 No Content`, or `401 Not Authorized` if trying to delete a
client not owned by user. No body is returned.
