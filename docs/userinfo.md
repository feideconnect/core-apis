# Userinfo API for Feide Connect

API to retrieve information about current user. To test the API, obtain an authentication token and

    $ export TOKEN=...

## Retrieving information about current user

    $ curl -H "Authorization: Bearer $token" https://api.feideconnect.no/userinfo/userinfo/

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

- scope `userinfo`

  - `displayName`, single value
  - `sn`
  - `givenName`

- scope `userinfo-feide`

  - `eduPersonPrincipalName`, single value
  - `uid`

- scope `userinfo-nin`

  - `norEduPersonNIN`, single value

- scope `userinfo-mail`

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

- scope `userinfo-contact`

  - `postOfficeBox`
  - `postalAddress`
  - `postalCode`
  - `facsimileTelephoneNumber`
  - `homePhone`
  - `homePostalAddress`
  - `l`
  - `mobile`
  - `street`
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

