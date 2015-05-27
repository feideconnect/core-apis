from urllib.parse import unquote as urlunquote, quote as urlquote
import functools
import datetime
import pytz
from coreapis.utils import LogWrapper, get_feideids, translatable, failsafe, now
from coreapis.cache import Cache
from . import BaseBackend, IDHandler
import eventlet
ldap3 = eventlet.import_patched('ldap3')
from coreapis.peoplesearch.controller import LDAPController
from eventlet.pools import Pool
from eventlet.greenpool import GreenPool
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
GOGROUP_PREFIX = 'urn:mace:feide.no:go:group:'
GOGROUPID_PREFIX = 'urn:mace:feide.no:go:groupid:'
GREP_ID_PREFIX = 'fc:grep'
GOGROUP_ID_PREFIX = 'fc:gogroup'

go_types = {
    'u': translatable({
        'nb': 'undervisningsgruppe',
    }),
    'b': translatable({
        'nb': 'basisgruppe',
    }),
    'a': translatable({
        'nb': 'andre grupper',
        'en': 'other groups',
    }),
}

lang_map = {
    'nno': 'nn',
    'nob': 'nb',
    'eng': 'en',
    'sme': 'se',
}

affiliation_names = {
    'go': {
        'faculty': translatable({
            'nb': 'Lærer',
        }),
        'staff': translatable({
            'nb': 'Stab',
        }),
        'employee': translatable({
            'nb': 'Ansatt',
        }),
        'student': translatable({
            'nb': 'Elev',
        }),
#        'alum': translatable({
#        }),
        'affiliate': translatable({
            'nb': 'Ekstern',
        }),
#        'library-walk-in': translatable({
#        }),
        'member': translatable({
            'nb': 'Annet',
        })
    },
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


def go_split(string):
    return [urlunquote(part) for part in string.split(':')]


def go_join(parts):
    return ":".join((urlquote(part) for part in parts))


def parse_go_date(date):
    res = datetime.datetime.strptime(date, '%Y-%m-%d')
    return res.replace(tzinfo=pytz.UTC)


def go_membership(role):
    membership = {
        'basic': 'admin' if role == 'faculty' else 'member',
        'affiliation': role,
    }
    if role in affiliation_names['go']:
        membership['displayName'] = affiliation_names['go'][role]
    else:
        membership['displayName'] = role
    return membership


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
    def __init__(self, prefix, maxrows, config):
        super(LDAPBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.ldapbackend')
        self.timer = config.get_settings().get('timer')
        ldap_config = config.get_settings().get('ldap_config_file', 'ldap-config.json')
        self.ldap = LDAPController(self.timer, ldap_config, pool=Pool)
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
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
        orgType = self._get_org_type(realm)
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
        return {
            'id': self._groupid('{}:unit:{}'.format(realm,
                ouAttributes['norEduOrgUnitUniqueIdentifier'][0])),
            'parent': self._groupid(realm),
            'displayName': ouAttributes['ou'][0],
            'type': 'fc:org',
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

    def _parse_gogroup(self, group_info):
        if not group_info.startswith(GOGROUP_PREFIX):
            self.log.warn("Found malformed group info: {}".format(group_info))
            raise KeyError('invalid group info')
        parts = go_split(group_info)
        if len(parts) != 13:
            self.log.warn("Found malformed group info: {}".format(group_info))
            raise KeyError('invalid group info')
        return parts[5:]

    def _handle_gogroup(self, realm, group_info, show_all):
        group_type, grep_code, organization, _group_id, valid_from, valid_to, role, name = self._parse_gogroup(group_info)
        group_id = go_join((realm, group_type, organization, _group_id, valid_from, valid_to))
        valid_from = parse_go_date(valid_from)
        valid_to = parse_go_date(valid_to)
        ts = now()
        if not show_all and (ts < valid_from or ts > valid_to):
            raise KeyError('Group not valid now and show_all off')
        result = {
            'id': '{}:{}'.format(GOGROUP_ID_PREFIX, group_id),
            'displayName': name,
            'type': 'fc:gogroup',
            'notBefore': valid_from,
            'notAfter': valid_to,
            'go_type': group_type,
            'parent': self._groupid('{}:unit:{}'.format(realm, organization)),
            'membership': go_membership(role),
        }
        if grep_code:
            grep_data = self.session.get_grep_code_by_code(grep_code, 'fagkoder')
            result['grep'] = {
                'displayName': grep_translatable(grep_data['title']),
                'code': grep_code,
            }
        if group_type in go_types:
            result['go_type_displayName'] = go_types[group_type]
        else:
            self.log.warn('Found invalid go group type', go_type=group_type)
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
            if val.startswith(GOGROUP_PREFIX):
                try:
                    res.append(self._handle_gogroup(realm, val, True))
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

    def _find_group_for_groupid(self, gogroupid, entitlements):
        groupid_data = go_split(gogroupid)
        group_type, organization, group_id, valid_from, valid_to = groupid_data
        for a in entitlements:
            if not a.startswith(GOGROUP_PREFIX):
                continue
            try:
                group_data = self._parse_gogroup(a)
                _group_type, _grep_code, _organization, _group_id, _valid_from, _valid_to, _role, _name = group_data
                print(groupid_data)
                print(group_data)
                if _group_type == group_type and \
                   organization == _organization and \
                   group_id == _group_id and \
                   valid_to == _valid_to and \
                   valid_from == _valid_from:
                    return group_data
            except KeyError:
                continue
        raise KeyError("Did not find group for group id")

    def get_go_members(self, user, groupid, show_all):
        intid = self._intid(groupid)
        realm, gogroupid = intid.split(':', 1)
        entitlement_value = "{}{}".format(GOGROUPID_PREFIX, gogroupid)
        try:
            base_dn = self.ldap.get_base_dn(realm)
        except KeyError:
            self.log.debug('ldap not configured for realm', realm=realm)
            return []
        ldap_res = self.ldap.search(realm, base_dn,
                                    '(eduPersonEntitlement={})'.format(entitlement_value),
                                    ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                                    ('displayName', 'eduPersonEntitlement'), 1000)
        res = []
        for hit in ldap_res:
            entry = {'name': hit['attributes']['displayName'][0]}
            try:
                data = self._find_group_for_groupid(gogroupid, hit['attributes']['eduPersonEntitlement'])
                entry['membership'] = go_membership(data[6])
            except KeyError:
                import logging
                logging.execption('hmm')
                pass
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
                    "en": "Uninett connect organization",
                    "nb": "Uninett connect organisasjon"
                })
            },
        ]
