from coreapis import cassandra_client
from coreapis.utils import LogWrapper, get_feideid

USER_INFO_ATTRIBUTES_FEIDE = {
    "userinfo": [
        'displayName',
        'sn',
        'givenName',
    ],
    "userinfo-feide": [
        'eduPersonPrincipalName',
        'uid',
    ],
    "userinfo-nin": [
        'norEduPersonNIN',
    ],
    "userinfo-mail": [
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
    "userinfo-contact": [
        'postOfficeBox',
        'postalAddress',
        'postalCode',
        'facsimileTelephoneNumber',
        'homePhone',
        'homePostalAddress',
        'l',
        'mobile',
        'street',
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
SINGLE_VALUED_ATTRIBUTES_FEIDE = [
    'displayName',
    'eduPersonPrincipalName',
    'eduPersonPrimaryAffiliation',
    'norEduPersonBirthDate',
    'norEduPersonLegalName',
    'norEduPersonNIN',
    'o',
    'preferredLanguage',
    'schacHomeOrganization',
]


def flatten(user, single_val_attrs):
    for attr in single_val_attrs:
        if attr in user:
            user[attr] = user[attr][0]


def normalize(user, single_val_attrs):
    for k, v in user.items():
        # Choose just one for attributes with options, e.g. 'title;lang-no-no'
        parts = k.split(';')
        if len(parts) > 1:
            user[parts[0]] = v
            del user[k]
    flatten(user, single_val_attrs)


def allowed_attributes(attributes, perm_checker):
    res = []
    for k, v in attributes.items():
        if perm_checker('scope_{}'.format(k)):
            res += v
    return res


class UserInfoController(object):

    def __init__(self, contact_points, keyspace, ldap_controller):
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log = LogWrapper('userinfo.UserInfoController')
        self.ldap = ldap_controller

    def get_userinfo(self, user, perm_checker):
        feideid = get_feideid(user)
        attributes = allowed_attributes(USER_INFO_ATTRIBUTES_FEIDE, perm_checker)
        person = self.ldap.lookup_feideid(feideid, attributes)
        normalize(person, SINGLE_VALUED_ATTRIBUTES_FEIDE)
        return dict(person)
