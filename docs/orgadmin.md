# Organization API for Dataporten

To test the API, obtain an authentication token and

    $ export TOKEN=...

## List mandatory clients for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.dataporten.no/orgs/<org-id>/mandatory_clients/'

    [{"id": "8aa931b4-f3da-4bdb-9675-fe02b899b6ed",
      "redirect_uri": ["http://localhost:8001"],
        "descr": "sa tester ting",
        "name": "sa-test",
        "owner": {
            "id": "p:6fc96878-fdc5-4fc3-abfc-6fcc018ff0fc",
            "name": "Sigmund Augdal"
        }
    }]

### Description

Returns a list of objects representing clients that are currently marked as mandatory for the given `org-id`


## Creating an organization

    curl -X POST -H "Authorization: Bearer $TOKEN" -d '{
        "id": "fc:org:ipadi.no",
        "name": {
            "nb": "Institutt for Partielle Differensialligninger",
            "nn": "Institutt for Partielle Differensiallikningar"
        },
        "fs_groups": false,
        "realm": "ipdadi.no",
        "type": ["higher_education", "home_organization"],
        "organization_number": "no123456789",
        "uiinfo": {"geo": [{"lat": 63.4, "lon": 10.4}]},
        "services": ["auth", "avtale"]
        }' \
    https://api.dataporten.no/orgs/

### Required parameters

- `id`: Feide organizations have "fc:org:<realm>". String.
- `name`: Object of key: language code and name: string.

### Optional parameters

- `fs_groups`: Boolean. True if organization has group in the Norwegian common student system.
- `realm`: Feide realm. String.
- `type`: Array of strings. Possible values:

  - `higher_education`
  - `upper_secondary`
  - `primary_and_lower_secondary`
  - `home_organization`
  - `service_provider`

- `organization_number`: For Norwegian organizations: Organization number from the Entity Register
    prefixed by 'no'.
- `uiinfo:` Json object.
- `services:` Array of strings. Possible values currently:

  - `avtale`
  - `auth`
  - `idporten`
  - `pilot`

### Return values

- `201 Created`: When the request is successful this code is returned and a json representation of the created object is returned in the response body
- `409 Conflict`: Returned if the selected `id` is already in use
- `400 Bad Request`: Returned if required parameters are missing or some parameter is malformed
- `403 Forbidden`: User is not a platform admin

Only for platform administrators


## Updating an organization

    $ curl -X PATCH  -H "Authorization: Bearer $TOKEN" \
    -H "Content-Type: application/json" -d '{
        "type": [
            "higher_education",
            "home_organization",
            "service_provider"
        ]}' \
    'https://api.dataporten.no/orgs/<org id>'

### Parameters

All parameters have the same meaning as when creating, but none are mandatory and `id` is read only (it's presence in a request will be ignored)

### Return values

- `200 OK`: When the request is successful this code is returned and the a json representation of the updated object is returned
- `400 Bad Request`: Some parameter passed was invalid
- `403 Forbidden`: User is not a platform admin

Only for platform administrators


## Deleting an organization

    $ curl -v -X DELETE -H "Authorization: Bearer $TOKEN" \
    'https://api.dataporten.no/orgs/<org id>'

### Return values

- `204 No Content`: The object was successfully deleted
- `400 Bad Request`: Organization has mandatory clients
- `403 Forbidden`: Current user does not own the object to be deleted
- `404 Not Found`: The provided organization id does not exist in database

Only for platform administrators


## Mark a client as mandatory for an organization

    curl -H "Authorization: Bearer $TOKEN" -X PUT 'https://api.dataporten.no/orgs/<org-id>/mandatory_clients/<client-id>'

### Parameters

- `org-id`: In the url. The id of the organization to work on
- `client-id`: A single json-encoded uuid in the url is the id of the client to mark as mandatory


## Make a client no longer mandatory for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.dataporten.no/orgs/<org-id>/mandatory_clients/<client-id>' -X DELETE

### Description

Removes a client from list of mandatory clients for an
organization. Both `org-id` and `client-id` are passed in the
url. Returns `204 No Content` on success.

## List services for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.dataporten.no/orgs/<org-id>/services/'

	[
		"auth",
		"avtale"
	]

### Description

Returns a list of strings representing services that are currently
enabled for the given `org-id`

## Enable a service for an organization

    curl -H "Authorization: Bearer $TOKEN" -X PUT 'https://api.dataporten.no/orgs/<org-id>/services/<service>'

### Parameters

- `org-id`: In the url. The id of the organization to work on
- `service`: A single json-encoded string in the url is the service to enable

### Description

Enables a service for an organization. At present, the supported
values are:

- auth
- avtale
- pilot

Only for platform administrators

## Disable a service for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.dataporten.no/orgs/<org-id>/services/<service>' -X DELETE

### Description

Disables a service for an organization. Both `org-id` and `service` are passed in the
url. Returns `204 No Content` on success.

Only for platform administrators
