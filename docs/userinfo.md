# Userinfo API for Dataporten

API to retrieve information about current user. To test the API, obtain an authentication token and

    $ export TOKEN=...

## Retrieving information about current user

    $ curl -H "Authorization: Bearer $TOKEN" https://api.dataporten.no/userinfo/v1/userinfo

    {
       "displayName": "Per Spellmann",
       "givenName": [
          "Per"
       ],
       "sn": [
           "Spellmann"
       ]
    }


Attributes are defined in
https://www.feide.no/sites/feide.no/files/documents/norEdu_spec.pdf. They
are multiple valued unless stated otherwise below.

The returned information depends on the scopes held by the caller:

- scope `profile`

  - `displayName`, single value
  - `sn`
  - `givenName`

- scope `userid-feide`

  - `eduPersonPrincipalName`, single value
  - `uid`

- scope `userid-nin`

  - `norEduPersonNIN`, single value

- scope `email`

  - `mail`

- scope `groups`

  - `schacHomeOrganization`, single value
  - `title`
  - `o`, single value
  - `ou`
  - `manager`
  - `eduPersonAffiliation`
  - `eduPersonPrimaryAffiliation`, single value
  - `eduPersonScopedAffiliation`

- scope `userinfo-entitlement`

  - `eduPersonEntitlement`

- scope `address`

  - `postOfficeBox`
  - `postalAddress`
  - `postalCode`
  - `homePostalAddress`
  - `l`
  - `street`

- scope `phone`

  - `mobile`
  - `facsimileTelephoneNumber`
  - `homePhone`
  - `telephoneNumber`

- scope `userinfo-extra`

  - `eduPersonAssurance`
  - `eduPersonNickname`
  - `labeledURI`
  - `cn`
  - `norEduPersonBirthDate`, single value
  - `norEduPersonLIN`
  - `norEduPersonLegalName`, single value
  - `preferredLanguage`, single value


## Retrieving profile photo of a user

    $ curl https://api.dataporten.no/userinfo/v1/user/media/<userid_sec>

e.g

    $ curl https://api.dataporten.no/userinfo/v1/user/media/p:497ff70b-4b73-47a9-b9f4-8a87d844a410

userid_sec must be of the form `p:<uuid>`. Authentication is not required.

### Optional paramters

- `usedefault`: Return a default image if no photo has been
  uploaded. Defaults to `true`.

### Return values

- `200 OK`: On success. The image is returned as the response body.
- `404 Not Found`: The requested userid_sec was not found, or no photo
  has been uploaded and `usedefault` is `false`.
- `304 Not Modified`: If request has the `If-Modified-Since` header set to a timestamp equal or higher than the updated column for this group.
