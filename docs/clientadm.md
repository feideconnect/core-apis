# Client Administration API for Feide Connect

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Creating a client

    $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{ "name" : "per", "scopes_requested" : ["clientadmin"],
          "redirect_uri" : ["http://example.org"] }' \
    'https://api.feideconnect.no/clientadm/clients/'

    {"type": "", "name": "per", "status": [], "redirect_uri": ["http://example.org"],
     "client_secret": "", "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-22T10:59:03.585600+00:00",
     "scopes": [], "scopes_requested": ["clientadmin"], "descr": "",
     "created": "2015-01-22T10:59:03.585600+00:00"}

Fills in `id` if not given. `name` must be given. `scopes_requested` and
`redirect_uri` must each have at least one member. `owner` is set to
user. `created`, `scopes` and `updated` may be given, but are silently
ignored - values are set by system.

Set `organization` to an organization id to register a client owned by
an orangization. You must be admin for that organization to do this.

Returns `201 Created` with url in `Location` header, and client as json in
body. Returns `409 Conflict` if `id` is given and is already in
use. Returns `400 Bad Request` if request body violates the schema or is
malformed in some way. Returns `403 Forbidden` if `organization` is set
but user is not admin of that organizatoin

## Updating a client

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"descr": "test"}' \
    'https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"type": "", "name": "per", "status": [], "client_secret": "",
     "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820",
     "updated": "2015-01-22T11:03:29.983120+00:00", "scopes": [],
     "scopes_requested": ["clientadmin"], "descr": "test",
     "created": "2015-01-22T10:59:03.585000"}

`id`, `organization`, `created`, `owner`, `scopes` and `updated` may be given, but are
silently ignored.

`scopes_requested` is treated as follows: `scopes` in the updated client will only contain scopes
listed in `scopes_requested` attribute. Scopes are included
in the client only if at least one of the following applies:

- The scope has policy `auto:true` in `scopedefs.json`
- The scope is owned by the client's owner.
- The scope is named `gk_<foo>`, where
  `<foo>` is the name of an API gatekeeper, whose scopedef
  has policy `auto:true`.
- The scope is named `gk_<foo>_<bar>`, where
  `<foo>` is the name of an API gatekeeper which has subscope
  `<bar>`. The  scopedef of `<bar>` should have policy `auto:true`.

Returns `200 OK`, and client as json in body. Returns `400 Bad
Request` if request body violates the schema or is malformed in some
way. Returns `403 Forbidden` if trying to update a client not
owned by user. Returns `404 Not Found` if client does not exist.

## Updating scopes for a client

The owner of an API Gatekeeper can add or remove scopes it controls
to/from a client's 'scopes', as long as the client owner has requested
the scope.

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"scopes_add": ["gk_foo_bar"], "scopes_remove": ["gk_foo_quux"]}' \
    'https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/scopes'

    "OK"

List scopes to be added in `scopes_add` and scopes to be removed in `scopes_remove`.

## Fetching a client

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"type": "", "name": "per", "status": null, "client_secret": "",
     "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-22T11:03:29.983000",
     "scopes": null, "scopes_requested": ["clientadmin"], "descr": "test",
     "created": "2015-01-22T10:59:03.585000"}

If user is unauthenticated, a restricted view of the client is
returned.

    $ curl -X GET
    'https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"name": "per", "redirect_uri": ["http://example.org"],
     "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": { "id": "p:ce5e8798-df69-4b87-a2e7-9678ab9a2820", "name": "Peder Aas"},
     "descr": "test"}

Returns `404 Not Found` if client does not exist.

## Listing all clients owned by user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/clientadm/clients/'

    [{"name": "per","redirect_uri": ["http://example.org"],
      "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
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

## Listing all clients owned by an organization

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/clientadm/clients/?organization=<org-id>'

    [{"name": "per","redirect_uri": ["http://example.org"],
      "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
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
even if resulting list is empty. Returns `403 Forbidden` if user is not admin
of the requested organization

## Filtering list of clients by scope

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/clientadm/clients/?scope=clientadmin'

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
    'https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

Returns `204 No Content`, or `403 Forbidden` if trying to delete a
client not owned by user. No body is returned.

## Getting client logo

    $ curl https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/logo|display

Returns `404 Not Found` if id does not map to an existing client in the database, `304 Not Modified` if request has the `If-Modified-Since` header set to a timestamp equal or higher than the updated column for that client and `200 OK` otherwise. If no logo has been uploaded for this client a default image will be returned

## Uploading a new client logo

    $ curl -v -H "Authorization: Bearer $TOKEN" -F 'logo=@new_logo.png' https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/logo

or:

    $ curl -v -H "Authorization: Bearer $TOKEN" -H 'Content-Type: image/png' --data-binary '@new_logo.png' https://api.feideconnect.no/clientadm/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/logo

Returns `403 Forbidden` if trying to change logo of a client not owned by user. `404 Not found` if no client with that id exists and `200 OK` otherwise, `400 Bad Request` if the uploaded file is not in a recognized image format.

## Listing public scope definitions

    $ curl https://api.feideconnect.no/clientadm/scopes/

    {"userinfo": {"policy": {"auto": true}, "title": "Grunnleggende informasjon om brukeren",
                  "descr": "bla blab la", "public": true},
     "userinfo-feide": {"policy": {"auto": true},
                        "title": "Tilgang til brukerens Feide-identifikator",
                         "descr": "bla blab la", "public": true},
     ..}

Returns `200 OK` with a json object body with entries for each public
scope.
