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


Attributes are defined in https://www.feide.no/sites/feide.no/files/documents/norEdu_spec.pdf

The returned information depends on the scopes held by the caller:

- scope `userinfo`

  - `displayName`
  - `sn`
  - `givenName`

- scope `userinfo-feide`

  - `eduPersonPrincipalName`
  - `uid`

- scope `userinfo-nin`

  - `norEduPersonNIN`

- scope `userinfo-mail`

  - `mail`

- scope `groups`

  - `schacHomeOrganization`
  - `title`
  - `o`
  - `ou`
  - `manager`
  - `eduPersonAffiliation`
  - `eduPersonPrimaryAffiliation`
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
  - `norEduPersonBirthDate`
  - `norEduPersonLIN`
  - `norEduPersonLegalName`
  - `preferredLanguage`

