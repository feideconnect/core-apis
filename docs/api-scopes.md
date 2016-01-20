APIs and scopes
===============

In external APIs, the version is optional, The unversioned route will
point to the latest version.

Public scopes
-------------

- userinfo
- userinfo-mail
- userinfo-feide
- userinfo-photo
- openid
- longterm
- peoplesearch
- groups


[Ad Hoc Groups](adhocgroupadm.md)
---------------------------------

Prefix: /adhocgroups

### Public

- (/v1)/{id}/logo GET

### Private, scope adhocgroupadmin

- (/v1)/{id}/logo POST

- / GET, POST
- /{id} GET, PATCH. DELETE
- /{id}/details GET
- /{id}/invitation POST
- /{id}/members GET, PATCH, DELETE
- /memberships GET, PATCH, DELETE
  

[API Gatekeeper](apigkadm.md)
-----------------------------

Prefix: /apigkadm

### Public

- (/v1)/public GET
- (/v1)/apigks/{id}/logo GET

### Private, scope apigkadmin

- (/v1)/apigks/{id}/logo POST

- /apigks/ GET, POST
- /apigks/{id} GET, PATCH, DELETE
- /apigks/{id}/exists GET
- /apigks/orgs/{orgid}/clients/ GET
- /apigks/owners/{ownerid}/clients/ GET


[Authorizations](authorizations.md)
-----------------------------------

Prefix: /authorizations

### Private, scope authzinfo

- / GET
- /{id} DELETE
- /resources_owned GET
- /consent_withdrawn POST

[Clients](clientadm.md)
-----------------------

Prefix: /clientadm

###  Public

- (/v1)/public/ GET
- (/v1)/clients/{id}/logo GET
- (/v1)/scopes/ GET

### Private, scope clientadmin

- (/v1)/clients/{id}/logo POST

- /clients/ GET
- /clients/ POST
- /clients/{id} GET
- /clients/{id} DELETE
- /clients/{id} PATCH
- /clients/{id}/gkscopes PATCH
- /clients/{id}/orgauthorization/{realm} GET, PATCH, DELETE
- /realmclients/targetrealm/{realm}/ GET


GK
--

Prefix: /gk

- /info/{backend} GET
  - Needs client certificate
  - Unless method=OPTIONS, scope gk_{backend} is needed
  - If method=OPTIONS, who is authorized?


Groups
------

Prefix: /groups

### External, scope groups

- (/v1)/groups/{groupid} GET
- (/v1)/groups/{groupid}/logo GET
- (/v1)/groups/{groupid}/members GET
- (/v1)/groups GET
- (/v1)/grouptypes GET
- (/v1)/me/groups GET
- (/v1)/me/groups/{groupid} GET


Organizations
-------------

Prefix: /orgs

### [Public](org.md)

- (/v1)/ GET
- (/v1)/{id} GET
- (/v1)/{id}/logo GET

### [Private, scope orgadmin](orgadmin.md)

- (/v1)/{id}/logo POST

- /{id}/ldap_status GET
- /{id}/mandatory_clients/ GET
- /{id}/mandatory_clients/{clientid} PUT, DELETE
- /{id}/services/ GET
- /{id}/services/{service} PUT, DELETE


Peoplesearch
------------

Prefix: /peoplesearch


### External, scope peoplesearch

- (/v1)/orgs GET
- (/v1)/people/profilephoto/{token} GET
- (/v1)/search/{org}/{name} GET


[Userinfo](userinfo.md)
-----------------------

Prefix: /userinfo

### Public

- /v1/user/media/{userid_sec} GET

### External, scope userinfo

- /v1/userinfo GET
