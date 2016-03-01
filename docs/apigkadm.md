# API Gatekeeper Administration API for Dataporten

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Creating a gatekeeper

    $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
    "httpscertpinned": null,
    "descr": "The feide api",
    "expose": {
      "clientid": false,
      "userid": false,
      "scopes": false
    },
    "requireuser": false,
    "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
    "updated": "2015-01-26T16:05:59Z",
    "endpoints": [
      "https://api.feide.no"
    ],
    "name": "feide api",
    "created": "2015-01-23T13:50:09Z",
    "trust": {
      "token": "DiYpd5FbEPx5eFMG",
      "type": "bearer"
    },
    "id": "feideapi",
    "status": null,
    "scopedef": null
    }' \
    'https://api.dataporten.no/apigkadm/apigks/'

### Required attributes

- `id`: Only lower case characters, numbers and -. Must begin with a character. 3 to 15 characters long. This is the first part of the domain the gatekeeper will be accessible as. E.g a gatekeeper with id `testkeeper` will be accessible as `https://testkeeper.gk.dataporten.no`.
- `name`: Descriptive name of the gatekeeper
- `requireuser`: Boolean, whether clients can access this api without acting on behalf of a user
- `endpoints`: Array of urls that this gatekeeper will forward the requests to. Must be http or https and may not contain a file path. E.g. `https://api.example.com` or `http://data.example.org:5001`

### Optional attributes

- `descr`: Textual description of this gatekeeper
- `expose`: Object describing what data is exposed to the api
  - `clientid`: The id of the client is exposed if set to true
  - `userid`: The id of the user is exposed if set to true
  - `scopes`: Active sub scopes of this gatekeeper is exposed, that is scopes starting with `gk_<id>_`
  - `groups`: Not implemented yet
  - `userid_sec`: If true, all secondary user ids are exposed to the api. If a list only secondary user ids of the types listed are exposed
- `trust`: Information about credentials passed to the backend. Must contain a `type` attribute, other attributes depend on the value of `type`:
  - `bearer`: The value of `token` in `trust` is passed using Bearer authentication in the Authorization header
  - `basic`: The attributes `username` and `passwords` are used to do HTTP Basic authentication
  - `token`: The `token` attribute is passed in the `X-Dataporten-Auth`-header
- `status`: To be defined
- `scopedef`: To be defined
- `organization`: When set the gatekeeper will be owned by the organization with this id. Token must be associated with a user that is org admin for the organization. When not set the gatekeeper will be personal.

### Read only attributes

These attributes are returned from queries, and will be ignored in updates and when creating.
- `owner`: User id of the owner. Will be set based on the current authorization token
- `created`: Timestamp of the first creating of this object
- `updated`: Timestamp of the last update of this object

### Return values

- `201 Created`: When the request is successful this code is returned and a json representation of the created object is returned in the response body
- `409 Conflict`: Returned if the selected `id` is already in use
- `400 Bad Request`: Returned if required attributes are missing or some attribute is malformed
- `403 Forbidden`: User is not admin of the organization mentioned in `organization`

## Updating an apigk

    $ curl -X PATCH  -H "Authorization: Bearer $TOKEN" \
     -H "Content-Type: application/json" -d '{"name": "New gatekeeper name"}' \
    'https://api.dataporten.no/apigkadm/apigks/<gatekeeper id>'

### Attributes

All attributes have the same meaning as when creating, but none are mandatory and `id` and `organization` is read only (it's presence in a request will be ignored)

### Return values

- `200 OK`: When the request is successful this code is returned and the a json representation of the updated object is returned
- `400 Bad Request`: Some attribute passed was invalid
- `403 Forbidden`: Current user does not own the object to be updated

## Fetching a gatekeeper

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/<api gatekeeper id>'

    {"scopedef": null, "expose": {"clientid": false, "userid": false,
    "scopes": true}, "trust": {"type": "bearer", "token": "absd"},
    "status": null, "endpoints": ["https://testgk.uninett.no"],
    "httpscertpinned": null, "name": "testgk", "descr": "sigmund
    tester", "id": "testgk", "owner":
    "52a55f50-3b1f-4d25-8b14-d34ca715c30e", "updated":
    "2015-01-26T12:43:31Z", "requireuser": true, "created":
    "2015-01-26T12:43:31Z"}

### Return values

- `200 OK`: When successful this is returned with the json representation of the object in the response body
- `403 Forbidden`: Current user does not own the object requested
- `404 Not Found`: The provided gatekeeper id does not exist in database

## Listing all gatekeepers owned by user

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/'

    [{"scopedef": null, "expose": {"userid": false, "scopes": false, "clientid": false},
      "trust": {"type": "bearer", "token": "adsfSFDsdfasdfa"},"status": null,
      "endpoints": ["https://api.feide.no"], "httpscertpinned": null, "name": "feide api",
      "descr": "The feide api", "id": "feideapi", "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
      "updated": "2015-01-26T16:05:59Z", "requireuser": false, "created": "2015-01-23T13:50:09Z"},
     {"scopedef": null, "expose": {"clientid": false, "userid": false, "scopes": true},
      "trust": {"type": "bearer", "token": "absd"}, "status": null,
       "endpoints": ["https://testgk.uninett.no"], "httpscertpinned": null, "name": "testgk",
       "descr": "sigmund tester", "id": "testgk", "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
       "updated": "2015-01-26T12:43:31Z", "requireuser": true, "created": "2015-01-26T12:43:31Z"}]
    
### Return values

Returns `200 OK`, and list of api gatekeepers as json in body. Status is `200 OK`
even if resulting list is empty.

## Listing all gatekeepers for all owners

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/?showAll=true'

    [{"scopedef": null, "expose": {"userid": false, "scopes": false, "clientid": false},
      "trust": {"type": "bearer", "token": "adsfSFDsdfasdfa"},"status": null,
      "endpoints": ["https://api.feide.no"], "httpscertpinned": null, "name": "feide api",
      "descr": "The feide api", "id": "feideapi", "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
      "updated": "2015-01-26T16:05:59Z", "requireuser": false, "created": "2015-01-23T13:50:09Z"},
     {"scopedef": null, "expose": {"clientid": false, "userid": false, "scopes": true},
      "trust": {"type": "bearer", "token": "absd"}, "status": null,
       "endpoints": ["https://testgk.uninett.no"], "httpscertpinned": null, "name": "testgk",
       "descr": "sigmund tester", "id": "testgk", "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
       "updated": "2015-01-26T12:43:31Z", "requireuser": true, "created": "2015-01-26T12:43:31Z"}]

### Return values

Returns `200 OK`, and list of api gatekeepers as json in body. Status is `200 OK`
even if resulting list is empty. Returns `403 Forbidden` if user is not a platform
administrator

## Listing all gatekeepers owned by an organization

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/?organization=<org-id>'

    [{"scopedef": null, "expose": {"userid": false, "scopes": false, "clientid": false},
      "trust": {"type": "bearer", "token": "adsfSFDsdfasdfa"},"status": null,
      "endpoints": ["https://api.feide.no"], "httpscertpinned": null, "name": "feide api",
      "descr": "The feide api", "id": "feideapi", "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
      "updated": "2015-01-26T16:05:59Z", "requireuser": false, "created": "2015-01-23T13:50:09Z"},
     {"scopedef": null, "expose": {"clientid": false, "userid": false, "scopes": true},
      "trust": {"type": "bearer", "token": "absd"}, "status": null,
       "endpoints": ["https://testgk.uninett.no"], "httpscertpinned": null, "name": "testgk",
       "descr": "sigmund tester", "id": "testgk", "owner": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
       "updated": "2015-01-26T12:43:31Z", "requireuser": true, "created": "2015-01-26T12:43:31Z"}]

### Return values

Returns `200 OK`, and list of api gatekeepers as json in body. Status is `200 OK`
even if resulting list is empty. Returns `403 Forbidden` if user is not admin for the specified organization

## Deleting a gatekeeper

    $ curl -v -X DELETE -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/<api gatekeeper id>'

### Return values

- `204 No Content`: The object was successfully deleted
- `403 Forbidden`: Current user does not own the object to be deleted
- `404 Not Found`: The provided gatekeeper id does not exist in database

## Getting api gatekeeper logo

    $ curl https://api.dataporten.no/apigkadm/apigks/<api gatekeeper id>/logo|display

### Return values

- `200 OK`: On success. If no logo has been uploaded a default logo is provided
- `404 Not Found`: The provided gatekeeper id does not exist in database
- `304 Not Modified`: if request has the `If-Modified-Since` header set to a timestamp equal or higher than the updated column for this gatekeeper

## Uploading a new api gatekeeper logo

    $ curl -v -H "Authorization: Bearer $TOKEN" -F 'logo=@new_logo.png' \
    'https://api.dataporten.no/apigkadm/apigks/<api gatekeeper id>/logo'

or:

    $ curl -v -H "Authorization: Bearer $TOKEN" -H 'Content-Type: image/png' \
    --data-binary '@new_logo.png' \
    'https://api.dataporten.no/apigkadm/apigks/<api gatekeeper id>/logo'

- `200 OK`: On success
- `400 Bad Request`: The image data uploaded is not in a recognized format
- `403 Forbidden`: Current user does not own the gatekeeper to update
- `404 Not Found`: The provided gatekeeper id does not exist in database

## Getting public information about api gatekeepers

    $ curl https://api.dataporten.no/apigkadm/public

    [{"id": "feideapi", "expose": {"userid": false, "clientid": false, "scopes": false},
      "name": "feide api", "owner": {"id": "p:6fc96878-fdc5-4fc3-abfc-6fcc018ff0fc",
      "name": "Sigmund Augdal"}, "scopedef": null, "descr": "The feide api"},
     {"id": "testgk", "expose": {"userid": false, "clientid": false, "scopes": true},
      "name": "testgk", "owner": {"id": "p:6fc96878-fdc5-4fc3-abfc-6fcc018ff0fc",
      "name": "Sigmund Augdal"}, "scopedef": null, "descr": "sigmund tester"}]

Lists some public information about registered api gatekeepers for
clients to use when requesting permission. Only gatekeepers whose status
contains 'public' are included.

### Optional parameters

- `max_replies`: Maximum number of api gatekeepers to return. This
  number is also limited by a system configured value.
- `query`: A string to search for in the id and name fields of the
  public gatekeepers. The search is a case insensitive substring search.

## Checking whether a gatekeeper id is already in use

    $ curl -v -H "Authorization: Bearer $TOKEN" -F 'logo=@new_logo.png' \
    'https://api.dataporten.no/apigkadm/apigks/<api gatekeeper id>/exists'

### Return value

Returns `200 OK` on success with a single boolean in the json body indicating whether the gatekeeper exists or not

## Listing clients interested in a user's api gatekeepers

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/owners/<owner id>/clients/'

### Return value

- `200 OK`: On success
- `403 Forbidden`: Current user is not allowed to see the owner's clients

'me' can be used as owner id and means the userid of the calling user.

On success, the json body consists of a list of clients matching the
request. If the owner owns an apigk with id `foo`, clients having
`gk_foo` in scopes or scopes_requested are considered
matching. Example:

    [{"descr": "Example", "id": "a7f407fd-ace2-4fbe-a07a-db123821ff59",
      "name": "example",
      "owner": {"id": "p:497ff70b-4b73-47a9-b9f4-8a87d844a410", "name": "Pelle"},
      "redirect_uri": ["http://example.org"],"scopes": [],
      "scopes_requested": ["gk_foo", "gk_bar"]}]

## Listing clients interested in an organization's api gatekeepers

    $ curl -X GET -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/apigkadm/apigks/orgs/<organization id>/clients/'

### Return value

- `200 OK`: On success
- `403 Forbidden`: Current user is not allowed to see the owner's clients

On success, the json body consists of a list of clients matching the
request. If the owner owns an apigk with id `foo`, clients having
`gk_foo` in scopes or scopes_requested are considered
matching. Example:

    [{"descr": "Example", "id": "a7f407fd-ace2-4fbe-a07a-db123821ff59",
      "name": "example",
      "owner": {"id": "p:497ff70b-4b73-47a9-b9f4-8a87d844a410", "name": "Pelle"},
      "redirect_uri": ["http://example.org"],"scopes": [],
      "scopes_requested": ["gk_foo", "gk_bar"]}]
