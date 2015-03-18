from coreapis.utils import LogWrapper
from . import BaseBackend
import eventlet
ldap3 = eventlet.import_patched('ldap3')
from coreapis.peoplesearch.controller import LDAPController
from eventlet.pools import Pool

org_attribute_names = {
    'eduOrgLegalName',
    'norEduOrgNIN',
    'mail',
    'telephoneNumber',
    'postalAddress',
    'eduOrgHomePageURI',
    'eduOrgIdentityAuthNPolicyURI',
    'eduOrgWhitePagesURI',
    'facsimileTelephoneNumber',
    'l',
    'labeledURI',
    'norEduOrgAcronym',
    'norEduOrgUniqueIdentifier',
    'postalCode',
    'postOfficeBox',
    'street',
}


class LDAPBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(LDAPBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.ldapbackend')
        self.timer = config.get_settings().get('timer')
        self.ldap = LDAPController(self.timer, pool=Pool)

    def _get_org(self, realm, dn):
        org = self.ldap.search(realm, dn, '(objectClass=*)',
                               ldap3.SEARCH_SCOPE_BASE_OBJECT,
                               ldap3.ALL_ATTRIBUTES, 1)
        if len(org) == 0:
            raise KeyError('orgDN not found in catalog')
        org = org[0]
        orgAttributes = org['attributes']
        res = {
            'id': self._groupid(realm),
            'displayName': orgAttributes['cn'][0],
            'type': 'fc:org',
            'active': True,
            'public': True,
            'membership': {
                'basic': 'member',
            },
        }
        for attribute in org_attribute_names:
            if attribute in orgAttributes:
                res[attribute] = orgAttributes[attribute][0]
        return res

    def _get_orgunit(self, realm, dn):
        ou = self.ldap.search(realm, dn, '(objectClass=*)',
                              ldap3.SEARCH_SCOPE_BASE_OBJECT,
                              ldap3.ALL_ATTRIBUTES, 1)
        if len(ou) == 0:
            raise KeyError('orgUnitDN not found in catalog')
        ou = ou[0]
        ouAttributes = ou['attributes']
        return {
            'id': self._groupid('{}:unit:{}'.format(realm,
                ouAttributes['norEduOrgUnitUniqueIdentifier'][0])),
            'parent': self._groupid(realm),
            'displayName': ouAttributes['ou'][0],
            'type': 'fc:org',
            'active': True,
            'public': True,
            'membership': {
                'basic': 'member',
            },
        }

    def get_member_groups(self, user, show_all):
        result = []
        feideid = None
        for sec in user['userid_sec']:
            if sec.startswith('feide:'):
                feideid = sec.split(':', 1)[1]
        if not feideid:
            raise RuntimeError('could not find feide id')
        if not '@' in feideid:
            raise RuntimeError('invalid feide id')
        realm = feideid.split('@', 1)[1]
        base_dn = self.ldap.get_base_dn(realm)
        res = self.ldap.search(realm, base_dn, '(eduPersonPrincipalName={})'.format(feideid),
                               ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                               ('eduPersonOrgDN', 'eduPersonOrgUnitDN'), 1)
        if len(res) == 0:
            raise KeyError('could not find user in catalog')
        res = res[0]
        attributes = res['attributes']
        if 'eduPersonOrgDN' in attributes:
            orgDN = attributes['eduPersonOrgDN'][0]
            result.append(self._get_org(realm, orgDN))
        if 'eduPersonOrgUnitDN' in attributes:
            for orgUnitDN in attributes['eduPersonOrgUnitDN']:
                result.append(self._get_orgunit(realm, orgUnitDN))
        return result

    def get_membership(self, user, groupid):
        my_groups = self.get_member_groups(user, True)
        for group in my_groups:
            if group['id'] == groupid:
                return group['membership']
        raise KeyError('Not found')

    def get_group(self, user, groupid):
        my_groups = self.get_member_groups(user, True)
        for group in my_groups:
            if group['id'] == groupid:
                return group
        raise KeyError('Not found')

    def get_members(self, user, groupid, show_all):
        return []

    def get_groups(self, user, query):
        my_groups = self.get_member_groups(user, True)
        if not query:
            return my_groups
        return [group for group in my_groups
                if query in group['displayName']]

    def grouptypes(self):
        return [
            {
                "id": "fc:org",
                "displayName": {
                    "en": "Uninett connect organization",
                    "nb": "Uninett connect organisasjon"
                }
            },
        ]
