# Ad Hoc Group Administration API for Feide Connect

To test the API, obtain an authentication token and

    $ export TOKEN=...

## Creating a group

     $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
    "descr": "my very nice group",
    "name": "my group",
    "public": true,
    }' \
    'https://api.feideconnect.no/adhocgroups/'

### Required parameters

- `name`: The name of the new group
- `public`: (boolean)Whether this group should be public or not

### Optional parameters

- `descr`: A textual description of the group
- `invitation_token`: A token for use in invitation mails etc. Should be properly random

### Return values

- `201 Created`: The group was created. More info about the group can be obtained from the url included in the `Location` header in the response
- `400 Bad Request`: Some required parameter is missing or some passed parameter is invalid or malformed

## Updating a group

     $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
    "descr": "my very nice group",
    "name": "my group",
    "public": true,
    }' \
    'https://api.feideconnect.no/adhocgroups/<group id>'

### Optional parameters

- `descr`: A textual description of the group
- `invitation_token`: A token for use in invitation mails etc. Should be properly random
- `name`: The name of the new group
- `public`: (boolean)Whether this group should be public or not

### Return values

- `201 Created`: The group was created. More info about the group can be obtained from the url included in the `Location` header in the response
- `400 Bad Request`: Some required parameter is missing or some passed parameter is invalid or malformed

## Deleting a group

    $ curl -v -X DELETE -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/adhocgroups/<group id>'

### Return values

- `204 No Content`: The object was successfully deleted
- `403 Forbidden`: Current user does not own the object to be deleted
- `404 Not Found`: The provided group id does not exist in database

## View group information

    $ curl -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/adhocgroups/<group id>'

### Optional query parameters

- `invitation_token`: Required to view information about a group you are invited to (by token), but not yet member of

### Permissions

- Group owner
- Group members
- By invitation token

## View group details

    $ curl -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/adhocgroups/<group id>/details'

### Permissions

- Group owner
- Group admins

### Description

Returns all information about a group, including invitation_token

## Get group members

    $ curl -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/adhocgroups/<group id>/members'

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
    'https://api.feideconnect.no/adhocgroups/<group id>/members'

### Permissions

- Group owner
- Group admins

### Input

Input is a list of objects. Each object has a `type` field which can be either `member` or `admin`. Each object must also contain either a `token` field which you can get from the peoplesearch api, if you want ot add a member to the group. Or an `id` field if you want to change a members type.

## Remove group members

    $ curl -X DELETE -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '[
    <id from membership list>,
    <id from membership list>,
    ...
    ]' \
    'https://api.feideconnect.no/adhocgroups/<group id>/members'

### Permissions

- Group owner
- Group admins

## List memberships

    $ curl -H "Authorization: Bearer $TOKEN" \
    'https://api.feideconnect.no/adhocgroups/memberships'

### Description

Returns information about all groups current user is a member of, and information about the membership (status, and membership type)

## Leave groups

    $ curl -X DELETE -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '[
    <group id>,
    <group id>,
    ...
    ]' \
    'https://api.feideconnect.no/adhocgroups/memberships'

### Description

Remove current user from member lists if the groups indicated.

## Confirm group memberships

    $ curl -X PATCH -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '[
    <group id>,
    <group id>,
    ...
    ]' \
    'https://api.feideconnect.no/adhocgroups/memberships'

### Description

When a member is added to a group by a group owner or admin the status
of the membership is set to `unconfirmed`. The user can then use this
call to confirm his membeships, and get status to `normal`. Any number
of groups can be confirmed in one call.

## Join group using invitation token

    $ curl -X POST -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{
    "invitation_token": <invitation_token>
    }' \
    'https://api.feideconnect.no/adhocgroups/<group id>/invitaiton'

### Description

Use this call to join a group given a group id and invitation
token. Group owners and admins can access the groups invitation token
and distribute it with the group id to people they want to invite.

## Getting the group logo logo

    $ curl https://api.feideconnect.no/adhocgroups/<groupid>/logo|display

### Return values

- `200 OK`: On success. If no logo has been uploaded a default logo is provided
- `404 Not Found`: The provided group id does not exist in database
- `304 Not Modified`: if request has the `If-Modified-Since` header set to a timestamp equal or higher than the updated column for this group

## Uploading a new group logo

    $ curl -v -H "Authorization: Bearer $TOKEN" -F 'logo=@new_logo.png' \
    'https://api.feideconnect.no/adhocgroups/<group id>/logo'

or:

    $ curl -v -H "Authorization: Bearer $TOKEN" -H 'Content-Type: image/png' \
    --data-binary '@new_logo.png' \
    'https://api.feideconnect.no/adhocgroups/<group id>/logo'

- `200 OK`: On success
- `400 Bad Request`: The image data uploaded is not in a recognized format
- `403 Forbidden`: Current user does not own the group to update
- `404 Not Found`: The provided group id does not exist in database
