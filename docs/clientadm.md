# Client Administration API for Dataporten

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Creating a client

    $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{ "name" : "per", "scopes_requested" : ["clientadmin"],
          "redirect_uri" : ["http://example.org"] }' \
    'https://clientadmin.dataporten-api.no/clients/'

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
an organization. You must be admin for that organization to do this.

Returns `201 Created` with url in `Location` header, and client as json in
body. Returns `409 Conflict` if `id` is given and is already in
use. Returns `400 Bad Request` if request body violates the schema or is
malformed in some way. Returns `403 Forbidden` if `organization` is set
but user is not admin of that organization

## Updating a client

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"descr": "test"}' \
    'https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"type": "", "name": "per", "status": [], "client_secret": "",
     "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820",
     "updated": "2015-01-22T11:03:29.983120+00:00", "scopes": [],
     "scopes_requested": ["clientadmin"], "descr": "test",
     "created": "2015-01-22T10:59:03.585000"}

`id`, `organization`, `orgauthorization`, `created`, `owner`, `scopes` and `updated` may be given, but are
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

`status` is treated as follows:

- User may add or remove the 'Public' flag.
- Attempts to add or remove other flags are silently ignored.

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
    'https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/gkscopes'
 
    "OK"

If successful, returns `200 OK`, and "OK" as body.

List scopes to be added in `scopes_add` and scopes to be removed in `scopes_remove`.

A platform administrator can add or remove any scope
to/from a client's 'scopes', as long as the client owner has requested
the scope. The same call works for client owners, and scope requests
are moderated as for the client update call.

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" \
    -d '{"scopes_add": ["gk_foo_bar"], "scopes_remove": ["gk_foo_quux"]}' \
    'https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/scopes'

If successful, returns `200 OK`, and client as json in body.

List scopes to be added in `scopes_add` and scopes to be removed in `scopes_remove`.

## Fetching a client

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"type": "", "name": "per", "status": null, "client_secret": "",
     "redirect_uri": ["http://example.org"], "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-22T11:03:29.983000",
     "scopes": null, "scopes_requested": ["clientadmin"], "descr": "test",
     "created": "2015-01-22T10:59:03.585000"}

If user is unauthenticated, a restricted view of the client is
returned.

    $ curl -X GET
    'https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

    {"name": "per", "redirect_uri": ["http://example.org"],
     "id": "9dd084a3-c497-4d4c-9832-a5096371a4c9",
     "owner": { "id": "p:ce5e8798-df69-4b87-a2e7-9678ab9a2820", "name": "Peder Aas"},
     "descr": "test"}

Returns `404 Not Found` if client does not exist.

## Listing all clients owned by authorized user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/'

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
even if resulting list is empty. Does not include clients where `organization` is set.

## Listing all clients delegated to a user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/?delegated=true'

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
    'https://clientadmin.dataporten-api.no/clients/?organization=<org-id>'

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

## Listing clients for all owners

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/?showAll=true'

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
even if resulting list is empty. Returns `403 Forbidden` if user is not a platform
administrator.

## Listing all clients owned by given user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/?owner=ce5e8798-df69-4b87-a2e7-9678ab9a2820'

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
even if resulting list is empty. Returns `400 Bad Request` if owner is
not a well formed UUID. A client is visible to its owner and relevant
administrators. Includes clients where `organization` is set.


## Filtering list of clients by scope

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/?scope=clientadmin'

    [{"type": "client", "name": "test_clientadm", "status": ["production"],
      "client_secret": "88c7cdbf-d2bd-4d1b-825d-683770cd4bd3",
      "redirect_uri": ["http://example.org"], "id": "f3f043db-9fd6-4c5a-b0bc-61992bea9eca",
      "owner": "ce5e8798-df69-4b87-a2e7-9678ab9a2820", "updated": "2015-01-12T13:05:16.884000",
      "scopes": ["clientadmin"], "scopes_requested": ["clientadmin"],
      "descr": "Test client for client admin api", "created": "2015-01-12T13:05:16.884000"}]

Returns `200 OK`, and list of clients as json in body. Status is `200 OK`
even if resulting list is empty. Returns `400 Bad Request` if parameters
are not one of scope and owner, or if a parameter value is missing or malformed.

## Listing public information about all clients

    $ curl -X GET 'https://clientadmin.dataporten-api.no/public/'

    [{"name": "Test client", "owner": {
    "name": "Test Developer", "id": "p:00000000-0000-0000-0000-000000000001"},
    "id": "fb787073-d862-4f5a-8f5c-6b3ec439d817",
    "redirect_uri": ["http://people.dev.dataporten.no/"], "descr": ""},...]

Lists the publicly available information about all registered clients

## Listing all clients authorized by an organization

    $ curl -X GET \
    'https://clientadmin.dataporten-api.no/public/?orgauthorization=<realm>'

    [{"name": "Test client", "owner": {
    "name": "Test Developer", "id": "p:00000000-0000-0000-0000-000000000001"},
    "id": "fb787073-d862-4f5a-8f5c-6b3ec439d817",
    "redirect_uri": ["http://people.dev.dataporten.no/"], "descr": ""},...]

Lists the publicly available information about all clients authorized
to an organization. Returns `200 OK`, and list of clients as json in body. Status is `200 OK`
even if resulting list is empty.

## Deleting a client

    $ curl -v -X DELETE -H "Authorization: Bearer $TOKEN" \
    'https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9'

Returns `204 No Content`, or `403 Forbidden` if trying to delete a
client not owned by user. No body is returned.

## Getting client logo

    $ curl https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/logo|display

Returns `404 Not Found` if id does not map to an existing client in the database, `304 Not Modified` if request has the `If-Modified-Since` header set to a timestamp equal or higher than the updated column for that client and `200 OK` otherwise. If no logo has been uploaded for this client a default image will be returned

## Uploading a new client logo

    $ curl -v -H "Authorization: Bearer $TOKEN" -F 'logo=@new_logo.png' https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/logo

or:

    $ curl -v -H "Authorization: Bearer $TOKEN" -H 'Content-Type: image/png' --data-binary '@new_logo.png' https://clientadmin.dataporten-api.no/clients/9dd084a3-c497-4d4c-9832-a5096371a4c9/logo

Returns `403 Forbidden` if trying to change logo of a client not owned by user. `404 Not found` if no client with that id exists and `200 OK` otherwise, `400 Bad Request` if the uploaded file is not in a recognized image format.

## Listing public scope definitions

    $ curl https://clientadmin.dataporten-api.no/scopes/

    {"userinfo": {"policy": {"auto": true}, "title": "Grunnleggende informasjon om brukeren",
                  "descr": "bla blab la", "public": true},
     "userinfo-feide": {"policy": {"auto": true},
                        "title": "Tilgang til brukerens Feide-identifikator",
                         "descr": "bla blab la", "public": true},
     ..}

Returns `200 OK` with a json object body with entries for each public
scope.

## Listing orgauthorizations

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/clients/<id>/orgauthorization/<realm>'

    [
        "gk_foo",
        "gk_jktest"
    ]

Returns a list of scopes available to the client and authorized for
the realm.

The caller has to be one of

- the owner of the client
- an administrator of the owner organization of the realm

## Adding or updating an orgauthorization

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" \
	-d '["gk_jktest_rw"]'
	'https://clientadmin.dataporten-api.no/clients/<id>/orgauthorization/<realm>'

    [
        "gk_jktest_rw"
    ]

Input is the new list of scopes available to the client and authorized
for the realm. The same list is returned. It does not matter if there
already was a list, but note that the old list is overwritten.

The caller has to be an administrator of the owner organization of the realm.

## Deleting an orgauthorization

    $ curl -X DELETE -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/clients/<id>/orgauthorization/<realm>'

The list of scopes available to the client and authorized for the
realm is deleted.

The caller has to be one of

- the owner of the client
- an administrator of the owner organization of the realm

## Listing clients targeting a realm

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/realmclients/targetrealm/<realm>/'

    [
        {
            "name": "jktest1",
            "id": "1c90410e-2ce1-42c4-8236-6e44977a4d40"
			..
            "scopeauthorizations": {
                "gk_jktest_rw": true
            },
        },
        {
            "name": "test_clientadm",
            "authproviders": null,
            "id": "f3f043db-9fd6-4c5a-b0bc-61992bea9eca"
			..
            "scopeauthorizations": {
                "gk_jktest_rw": true
            },
        }
    ]

The call returns a list of clients which have been assigned a scope
which targets this realm.  The information is the public view of the
client, with the additional property
`scopeauthorizations`. `scopeauthorizations` lists scopes available to
the client, with a boolean telling whether the client has authorized
the scope.

The caller has to be an administrator of the owner organization of the realm.


## Listing mandatory clients for a user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/v1/mandatory/'

    [{"name": "Test client", "owner": {
    "name": "Test Developer", "id": "p:00000000-0000-0000-0000-000000000001"},
    "id": "fb787073-d862-4f5a-8f5c-6b3ec439d817",
    "redirect_uri": ["http://people.dev.dataporten.no/"], "descr": ""},...]

The call returns a list of clients which are mandatory for the authenticated user.
The information is the public view of the
clients.

The caller needs the `authzinfo` scope.


## Listing policy for a user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/policy'

	{
		"register": true
	}

The call returns a json object body with various policies for the
authenticated user. So far, only one policy has been defined:

`register`: `true` if user is allowed to register clients.


## Getting statistics records for a client

    curl -H "Authorization: Bearer $TOKEN" 'https://clientadmin.dataporten-api.no/clients/<id>/logins_stats/'

    [{"login_count": 5,
      "date": "2016-03-02",
      "timeslot": "2016-03-02T14:06:00Z",
      "authsource": "feide:uninett.no"
    },
	...
	]

    curl -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/clients/<id>/logins_stats/?end_date=2016-03-15'

    curl -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/clients/<id>/logins_stats/?num_days=2'

    curl -H "Authorization: Bearer $TOKEN" \
	'https://clientadmin.dataporten-api.no/clients/<id>/logins_stats/?authsource=feide:uninett.no'

### Description

Returns a list of statistics records

### Parameters

- `id`: The client id. Part of url.
- `end_date`: Final date to be included. Optional parameter. ISO 8601
  date string. Defaults to current date.
- `num_days`: Number of days to report. Optional parameter. Integer
  string. Defaults to 1. Must not be above upper limit. Limit is given in 400 body
  if it is exceeded.
- `authsource`: Authentication source to include in report. Optional
  parameter. String. Default is no filtering.

### Return values

- `200 OK`: When the request is successful this code is returned and
  the statistics are returned as json in the response body.
- `400 Bad Request`: Returned if some parameter has a  malformed or
  illegal value.
- `403 Forbidden`: User is not owner or administrator of the client.
