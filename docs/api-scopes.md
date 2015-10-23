APIs and scopes
===============

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

- /{id}/logo GET

### Private, scope adhocgroupadmin

- /{id}/logo POST

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

- /public GET
- /apigks/{id}/logo GET

### Private, scope apigkadmin

- /apigks/{id}/logo POST

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


[Clients](clientadm.md)
-----------------------

Prefix: /clientadm

###  Public

/public/ GET
/clients/{id}/logo GET
/scopes/ GET

### Private, scope clientadmin

- /clients/{id}/logo POST

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

### Public, scope groups

- /groups/{groupid} GET
- /groups/{groupid}/logo GET
- /groups/{groupid}/members GET
- /groups GET 
- /grouptypes GET
- /me/groups GET
- /me/groups/{groupid} GET


Organizations
-------------

Prefix: /orgs

### [Public](org.md)

- / GET
- /{id} GET
- /{id}/logo GET

### [Private, scope orgadmin](orgadmin.md)

- /{id}/ldap_status GET
- /{id}/mandatory_clients/ GET, POST
- /{id}/mandatory_clients/{clientid} DELETE


Peoplesearch
------------

Prefix: /peoplesearch


### Public, scope peoplesearch

- /orgs GET
- /people/profilephoto/{token} GET
- /search/{org}/{name} GET


[Userinfo](userinfo.md)
-----------------------

Prefix: /userinfo

### Public

- /user/media/{userid_sec} GET

### Private, scope userinfo

- /userinfo GET
