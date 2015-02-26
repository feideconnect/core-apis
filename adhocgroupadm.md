# Ad Hoc Group Administration API for Feide Connect

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Creating a group

     $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
    "descr": "my very nice group",
    "name": "my group",
    "public": true,
    }' \
    'http://api.dev.feideconnect.no:6543/adhocgroups/'

### Required parameters

- `name`: The name of the new group
- `public`: (boolean)Whether this group should be public or not

### Optional parameters

- `descr`: A textual description of the group
- `invitation_token`: A token for use in invitation mails etc. Should be properly random

### Return values

- `201 Created`: The group was created. More info about the group can be obtained from the url included in the `Location` header in the response
- `400 Bad Request`: Some required parameter is missing or some passed parameter is invalid or malformed

## Deleting a group

    $ curl -v -X DELETE -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/adhocgroups/<group id>'

### Return values

- `204 No Content`: The object was successfully deleted
- `403 Forbidden`: Current user does not own the object to be deleted
- `404 Not Found`: The provided group id does not exist in database

