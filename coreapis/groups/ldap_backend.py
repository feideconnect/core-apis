import functools
from coreapis.utils import LogWrapper, get_feideids, translatable, failsafe
from coreapis.cache import Cache
from . import BaseBackend, IDHandler
import eventlet
ldap3 = eventlet.import_patched('ldap3')
from coreapis.peoplesearch.controller import LDAPController
from eventlet.pools import Pool
from eventlet.greenpool import GreenPool
from coreapis import cassandra_client
from coreapis.groups.gogroups import affiliation_names as go_affiliation_names, GOGroup, groupid_entitlement
import urllib.parse as urlparse

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
PERSON_ATTRIBUTES = (
    'eduPersonOrgDN',
    'eduPersonOrgUnitDN',
    'eduPersonEntitlement',
    'eduPersonAffiliation',
    'eduPersonPrimaryAffiliation',
    'title',
)

PERSON_ATTRIBUTE_MAPPING = {
    'eduPersonAffiliation': 'affiliation',
    'eduPersonPrimaryAffiliation': 'primaryAffiliation',
    'title': 'title',
}
AFFILIATION_PRIORITY = (
    'faculty',
    'staff',
    'employee',
    'student',
    'alum',
    'affiliate',
    'library-walk-in',
    'member'
)

GREP_PREFIX = 'urn:mace:feide.no:go:grep:'
GREP_ID_PREFIX = 'fc:grep'
GOGROUP_ID_PREFIX = 'fc:gogroup'

lang_map = {
    'nno': 'nn',
    'nob': 'nb',
    'eng': 'en',
    'sme': 'se',
}

affiliation_names = {
    'go': go_affiliation_names,
    'he': {
        'faculty': translatable({
            'nb': 'Akademisk ansatt',
        }),
        'staff': translatable({
            'nb': 'Stab',
        }),
        'employee': translatable({
            'nb': 'Ansatt',
        }),
        'student': translatable({
            'nb': 'Student',
        }),
        'alum': translatable({
            'nb': 'Alumni',
        }),
        'affiliate': translatable({
            'nb': 'Tilknyttet',
        }),
#        'library-walk-in': translatable({
#        }),
        'member': translatable({
            'nb': 'Annet'
        })
    }
}
educational_org_types = {
    'higher_education',
    'primary_and_lower_secondary',
    'upper_secondary'
}


def grep_translatable(input):
    res = {}
    if len(input) == 1 and 'default' in input:
        return input['default']
    for lang, val in input.items():
        if lang in lang_map:
            res[lang_map[lang]] = val
    return translatable(res)


def quote(x, safe=''):
    return x.replace('/', '_')


def unquote(x):
    return x.replace('_', '/')


def groupid_escape(x):
    return ":".join((urlparse.quote(p) for p in x.split(':')))


def org_membership_name(affiliation, org_type):
    if 'higher_education' in org_type:
        names = affiliation_names['he']
    else:
        names = affiliation_names['go']
    for candidate in AFFILIATION_PRIORITY:
        if candidate in affiliation and candidate in names:
            return names[candidate]
    return affiliation[0]


def org_membership(person, org_type):
    membership = {
        'basic': 'member',
    }
    for key, value in person.items():
        if key in PERSON_ATTRIBUTE_MAPPING:
            membership[PERSON_ATTRIBUTE_MAPPING[key]] = value
    affiliation = membership.get('affiliation', [])
    if 'employee' in affiliation:
        membership['basic'] = 'admin'
        membership['displayName'] = org_membership_name(affiliation, org_type)
    return membership


class LDAPBackend(BaseBackend):
    def __init__(self, prefix, maxrows, settings):
        super(LDAPBackend, self).__init__(prefix, maxrows, settings)
        self.log = LogWrapper('groups.ldapbackend')
        self.timer = settings.get('timer')
        self.ldap = LDAPController(settings, pool=Pool)
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)
        self.org_types = Cache(3600)

    def _get_org_type_real(self, realm):
        org = self.session.get_org_by_realm(realm)
        return org['type']

    def _get_org_type(self, realm):
        return self.org_types.get(realm, functools.partial(self._get_org_type_real, realm))

    def get_id_handlers(self):
        return {
            self.prefix: IDHandler(self.get_group, self.get_membership,
                                   self.get_members, self.get_logo, self.permissions_ok),
            GREP_ID_PREFIX: IDHandler(self.get_grep_group, self.get_membership,
                                      self.get_members, self.get_logo, self.permissions_ok),
            GOGROUP_ID_PREFIX: IDHandler(self.get_group, self.get_membership,
                                         self.get_go_members, self.get_logo, self.permissions_ok),
        }

    def _get_org(self, realm, dn, person):
        org = self.ldap.search(realm, dn, '(objectClass=*)',
                               ldap3.SEARCH_SCOPE_BASE_OBJECT,
                               ldap3.ALL_ATTRIBUTES, 1)
        if len(org) == 0:
            raise KeyError('orgDN not found in catalog')
        org = org[0]
        orgAttributes = org['attributes']
        orgType = self._get_org_type(realm).intersection(educational_org_types)
        res = {
            'id': self._groupid(realm),
            'displayName': orgAttributes['eduOrgLegalName'][0],
            'type': 'fc:org',
            'public': True,
            'membership': org_membership(person, orgType),
            'orgType': orgType,
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
        orgType = self._get_org_type(realm).intersection(educational_org_types)
        data = {
            'id': self._groupid('{}:unit:{}'.format(realm,
                ouAttributes['norEduOrgUnitUniqueIdentifier'][0])),
            'parent': self._groupid(realm),
            'displayName': ouAttributes['ou'][0],
            'type': 'fc:orgunit',
            'public': True,
            'membership': {
                'basic': 'member',
            },
        }
        if 'higher_education' not in orgType:
            data['grouptype'] = 'fc:org'
            data['orgType'] = orgType
        return data

    def _handle_grepcode(self, grep_id, is_member):
        with self.timer.time('getting grep code'):
            grep_data = self.session.get_grep_code(grep_id)
        result = {
            'id': '{}:{}'.format(GREP_ID_PREFIX, quote(grep_id, safe='')),
            'displayName': grep_translatable(grep_data['title']),
            'type': 'fc:grep',
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

    def _handle_gogroup(self, realm, group_info, show_all):
        group = GOGroup(group_info)
        if not group.valid() and not show_all:
            raise KeyError('Group not valid now and show_all off')
        result = group.format_group(GOGROUP_ID_PREFIX, realm, self.prefix)
        if group.grep_code:
            grep_data = self.session.get_grep_code_by_code(group.grep_code, 'fagkoder')
            result['grep'] = {
                'displayName': grep_translatable(grep_data['title']),
                'code': group.grep_code,
            }
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

    def _handle_go_groups(self, realm, entitlements, show_all):
        res = []
        for val in entitlements:
            if GOGroup.candidate(val):
                try:
                    res.append(self._handle_gogroup(realm, val, show_all))
                except KeyError:
                    pass
        return res

    def _get_member_groups(self, show_all, feideid):
        self.log.debug('looking up groups', feideid=feideid)
        result = []
        realm = feideid.split('@', 1)[1]
        try:
            base_dn = self.ldap.get_base_dn(realm)
        except KeyError:
            self.log.debug('ldap not configured for realm', realm=realm)
            return []
        res = self.ldap.search(realm, base_dn, '(eduPersonPrincipalName={})'.format(feideid),
                               ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                               PERSON_ATTRIBUTES, 1)
        if len(res) == 0:
            raise KeyError('could not find user in catalog')
        res = res[0]
        attributes = res['attributes']
        if 'eduPersonOrgDN' in attributes:
            orgDN = attributes['eduPersonOrgDN'][0]
            result.append(self._get_org(realm, orgDN, attributes))
        if 'eduPersonOrgUnitDN' in attributes:
            for orgUnitDN in attributes['eduPersonOrgUnitDN']:
                result.append(self._get_orgunit(realm, orgUnitDN))
        if 'eduPersonEntitlement' in attributes:
            result.extend(self._handle_grepcodes(attributes['eduPersonEntitlement']))
            result.extend(self._handle_go_groups(realm, attributes['eduPersonEntitlement'],
                                                 show_all))
        return result

    def get_member_groups(self, user, show_all):
        result = []
        pool = GreenPool()
        get_member_groups = failsafe(functools.partial(self._get_member_groups, show_all))
        for res in pool.imap(get_member_groups, get_feideids(user)):
            if res:
                result.extend(res)
        return result

    def get_membership(self, user, groupid):
        groupid = groupid_escape(groupid)
        my_groups = self.get_member_groups(user, True)
        for group in my_groups:
            if group['id'] == groupid:
                return group['membership']
        raise KeyError('Not found')

    def get_group(self, user, groupid):
        groupid = groupid_escape(groupid)
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

    def get_members(self, user, groupid, show_all, include_member_ids):
        return []

    def _find_group_for_groupid(self, target, candidates):
        for group_data in candidates:
            if not GOGroup.candidate(group_data):
                continue
            try:
                group = GOGroup(group_data)
                if group.groupid_entitlement() == target:
                    return group
            except KeyError:
                continue
        raise KeyError("Did not find group for group id")

    def get_go_members(self, user, groupid, show_all, include_member_ids):
        intid = self._intid(groupid)
        intid = groupid_escape(intid)
        realm, groupid_base = intid.split(':', 1)
        entitlement_value = groupid_entitlement(groupid_base)
        print(entitlement_value)
        try:
            base_dn = self.ldap.get_base_dn(realm)
        except KeyError:
            self.log.debug('ldap not configured for realm', realm=realm)
            return []
        query_attributes = ('displayName', 'eduPersonEntitlement')
        if include_member_ids:
            query_attributes += ('eduPersonPrincipalName',)
        ldap_res = self.ldap.search(realm, base_dn,
                                    '(eduPersonEntitlement={})'.format(entitlement_value),
                                    ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                                    query_attributes, 1000)
        res = []
        for hit in ldap_res:
            attributes = hit['attributes']
            entry = {'name': attributes['displayName'][0]}
            try:
                if include_member_ids:
                    entry['userid_sec'] = ['feide:{}'.format(v) for v in attributes['eduPersonPrincipalName']]
                group = self._find_group_for_groupid(entitlement_value, attributes['eduPersonEntitlement'])
                entry['membership'] = group.membership()
            except KeyError:
                import logging
                logging.exception('hmm')
            res.append(entry)
        return res

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
                "displayName": translatable({
                    "en": "Organization",
                    "nb": "Organisasjon"
                })
            },
            {
                "id": "fc:orgunit",
                "displayName": translatable({
                    "en": "Organizational Unit",
                    "nb": "Organisasjonenhet"
                })
            },
        ]
