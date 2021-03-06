# Authorizations API for Dataporten

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Listing all authorizations for current user

    $ curl -H "Authorization: Bearer $token" https://api.dataporten.no/authorizations/

    [
      {
        "userid": "52a55f50-3b1f-4d25-8b14-d34ca715c30e",
        "scopes": [
          "apigkadmin",
          "clientadmin",
          "peoplesearch",
          "userinfo"
        ],
        "client": {
          "name": "sa-test",
          "id": "8aa931b4-f3da-4bdb-9675-fe02b899b6ed"
        },
        "issued": "2015-01-27T15:24:37Z"
      }
    ]

## Delete an authorization for a client for the current user

    $ curl -X DELETE -H "Authorization: Bearer $token" \
        https://api.dataporten.no/authorizations/<client id>

### Parameters

- `client id`: The id of the client whose authorization should be removed found in `x.client.id` in the output of the list call

### Return codes

- `204 No Content`: Request was successful. Note that this does not guarantee that the authorization did exist beforehand, only that it does not exist anymore
- `404 Not Found`: Client id does not exist or was malformed.

## Delete an authorization for a client for all users

    $ curl -X DELETE -H "Authorization: Bearer $token" \
        https://api.dataporten.no/authorizations/all_users/<client id>

### Parameters

- `client id`: The id of the client whose authorization should be removed

### Return codes

- `204 No Content`: Request was successful
- `403 Forbidden`: User is not an owner or administrator of the client
- `404 Not Found`: Client id does not exist or was malformed
