# Organization API for Feide Connect

To test the API, obtain an authentication token and

    $ export TOKEN=...

## List mandatory clients for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.feideconnect.no/orgs/<org-id>/mandatory_clients/'

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

## Mark a client as mandatory for an organization

    curl -H "Authorization: Bearer $TOKEN" -X POST --data-binary '"<client-id>"' 'https://api.feideconnect.no/orgs/<org-id>/mandatory_clients/'

### Parameters

- `org-id`: In the url. The id of the organization to work on
- `client-id`: A single json-encoded uuid in the request body is the id of the client to mark as mandatory

## Make a client no longer mandatory for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.feideconnect.no/orgs/<org-id>/mandatory_clients/<client-id>' -X DELETE

### Description

Removes a client from list of mandatory clients for an
organization. Both `org-id` and `client-id` are passed in the
url. Returns `204 No Content` on success.

## List services for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.feideconnect.no/orgs/<org-id>/services/'

	[
		"auth",
		"avtale"
	]

### Description

Returns a list of strings representing services that are currently
enabled for the given `org-id`

## Enable a service for an organization

    curl -H "Authorization: Bearer $TOKEN" -X POST --data-binary '"<service>"' 'https://api.feideconnect.no/orgs/<org-id>/services/'

### Parameters

- `org-id`: In the url. The id of the organization to work on
- `service`: A single json-encoded string in the request body is the
  service to enable

### Description

Enables a service for an organization. At present, the supported
values are:

- auth
- avtale
- pilot

Only for platform administrators

## Disable a service for an organization

    curl -H "Authorization: Bearer $TOKEN" 'https://api.feideconnect.no/orgs/<org-id>/services/<service>' -X DELETE

### Description

Disables a service for an organization. Both `org-id` and `service` are passed in the
url. Returns `204 No Content` on success.

Only for platform administrators
