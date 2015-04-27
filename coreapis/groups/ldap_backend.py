from coreapis.utils import LogWrapper, get_feideid
from . import BaseBackend, IDHandler
import eventlet
ldap3 = eventlet.import_patched('ldap3')
from coreapis.peoplesearch.controller import LDAPController
from eventlet.pools import Pool
from coreapis import cassandra_client

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
GREP_PREFIX = 'urn:mace:feide.no:go:grep:'
GREP_ID_PREFIX = 'fc:grep'


def quote(x, safe=''):
    return x.replace('/', '_')


def unquote(x):
    return x.replace('_', '/')


class LDAPBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(LDAPBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.ldapbackend')
        self.timer = config.get_settings().get('timer')
        ldap_config = config.get_settings().get('ldap_config_file', 'ldap-config.json')
        self.ldap = LDAPController(self.timer, ldap_config, pool=Pool)
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)

    def get_id_handlers(self):
        return {
            self.prefix: IDHandler(self.get_group, self.get_membership,
                                   self.get_members, self.get_logo),
            GREP_ID_PREFIX: IDHandler(self.get_grep_group, self.get_membership,
                                      self.get_members, self.get_logo),
        }

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
            'displayName': orgAttributes['eduOrgLegalName'][0],
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

    def _handle_grepcode(self, grep_id, is_member):
        with self.timer.time('getting grep code'):
            grep_data = self.session.get_grep_code(grep_id)
        result = {
            'id': '{}:{}'.format(GREP_ID_PREFIX, quote(grep_id, safe='')),
            'displayName': grep_data['title']['default'],
            'type': 'fc:grep',
            'active': True,
            'public': True,
            'grep_type': grep_data['type'],
        }
        if is_member:
            result['membership'] = {
                'basic': 'member',
            }

        code = grep_data.get('code', None)
        if code is not None:
            result['code'] = code
        return result

    def _handle_grepcodes(self, entitlements):
        res = []
        for val in entitlements:
            if val.startswith(GREP_PREFIX):
                try:
                    res.append(self._handle_grepcode(val[len(GREP_PREFIX):], True))
                except KeyError:
                    pass
        return res

    def get_member_groups(self, user, show_all):
        result = []
        feideid = get_feideid(user)
        realm = feideid.split('@', 1)[1]
        base_dn = self.ldap.get_base_dn(realm)
        res = self.ldap.search(realm, base_dn, '(eduPersonPrincipalName={})'.format(feideid),
                               ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                               ('eduPersonOrgDN', 'eduPersonOrgUnitDN', 'eduPersonEntitlement'), 1)
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
        if 'eduPersonEntitlement' in attributes:
            result.extend(self._handle_grepcodes(attributes['eduPersonEntitlement']))
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

    def get_grep_group(self, user, groupid):
        try:
            return self.get_group(user, groupid)
        except KeyError:
            pass
        grep_id = unquote(self._intid(groupid))

        return self._handle_grepcode(grep_id, False)

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
