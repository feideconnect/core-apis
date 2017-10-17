from coreapis import cassandra_client, feide
from coreapis.utils import LogWrapper, get_feideid
from coreapis.ldap import get_single

USER_INFO_ATTRIBUTES_FEIDE = {
    "profile": [
        'displayName',
        'sn',
        'givenName',
    ],
    "userid-feide": [
        'eduPersonPrincipalName',
        'uid',
    ],
    "userid-nin": [
        'norEduPersonNIN',
    ],
    "email": [
        'mail',
    ],
    "groups": [
        'schacHomeOrganization',
        'title',
        'o',
        'ou',
        'manager',
        'eduPersonAffiliation',
        'eduPersonPrimaryAffiliation',
        'eduPersonScopedAffiliation',
    ],
    "userinfo-entitlement": [
        'eduPersonEntitlement',
    ],
    "address": [
        'postOfficeBox',
        'postalAddress',
        'postalCode',
        'homePostalAddress',
        'l',
        'street',
    ],
    "phone": [
        'facsimileTelephoneNumber',
        'homePhone',
        'mobile',
        'telephoneNumber',
    ],
    "userinfo-extra": [
        'eduPersonAssurance',
        'eduPersonNickname',
        'labeledURI',
        'cn',
        'norEduPersonBirthDate',
        'norEduPersonLIN',
        'norEduPersonLegalName',
        'preferredLanguage',
    ]
}


def flatten(user, single_val_attrs):
    for attr in single_val_attrs:
        if attr in user:
            user[attr] = get_single(user[attr])


def normalize(user, single_val_attrs):
    for key, val in user.items():
        # Choose just one for attributes with options, e.g. 'title;lang-no-no'
        parts = key.split(';')
        if len(parts) > 1:
            user[parts[0]] = val
            del user[key]
    flatten(user, single_val_attrs)


def allowed_attributes(attributes, perm_checker):
    res = []
    for key, val in attributes.items():
        if perm_checker('scope_{}'.format(key)):
            res += val
    return list(set(res))


class UserInfoController(object):

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        ldap_controller = settings.get('ldap_controller')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        self.log = LogWrapper('userinfo.UserInfoController')
        self.ldap = ldap_controller

    def get_userinfo(self, user, perm_checker):
        feideid = get_feideid(user)
        attributes = allowed_attributes(USER_INFO_ATTRIBUTES_FEIDE, perm_checker)
        person = self.ldap.lookup_feideid(feideid, attributes)
        normalize(person, feide.SINGLE_VALUED_ATTRIBUTES)
        return dict(person)

    def get_profilephoto(self, userid_sec):
        if not userid_sec.startswith('p:'):
            self.log.warn("Attempt to get profilephoto by id that isn't p:", userid_sec=userid_sec)
            raise KeyError('incorrect ID used')
        userid = self.session.get_userid_by_userid_sec(userid_sec)
        profilephoto, updated = self.session.get_user_profilephoto(userid)
        return profilephoto, updated
