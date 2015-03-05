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

## View group information

    $ curl -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/adhocgroups/<group id>'

### Optional query parameters

- `invitation_token`: Required to view information about a group you are invited to (by token), but not yet member of

### Permissions

- Group owner
- Group members
- By invitation token

## View group details

    $ curl -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/adhocgroups/<group id>/details'

### Permissions

- Group owner
- Group admins

### Description

Returns all information about a group, including invitation_token

## Get group members

    $ curl -H "Authorization: Bearer $TOKEN" \
    'http://api.dev.feideconnect.no:6543/adhocgroups/<group id>/members'

### Permissions

- Group owner
- Group members

## Add/change group members

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN"  -H "Content-Type: application/json" -d '[
    {
    "token": <token from peoplesearch api>,
    "type": <membership type>
    },
    {
    "id": <id from membership list>,
    "type": <membership type>
    }]' \
    'http://api.dev.feideconnect.no:6543/adhocgroups/<group id>/members'

### Permissions

- Group owner
- Group admins

### Input

Input is a list of objects. Each object has a `type` field which can be either `member` or `admin`. Each object must also contain either a `token` field which you can get from the peoplesearch api, if you want ot add a member to the group. Or an `id` field if you want to change a members type.

## Remove group members

    $ curl -X DELETE -H "Authorization: Bearer $TOKEN"  -H "Content-Type: application/json" -d '[
    <id from membership list>,
    <id from membership list>,
    ...
    ]' \
    'http://api.dev.feideconnect.no:6543/adhocgroups/<group id>/members'

### Permissions

- Group owner
- Group admins
