import functools
import urllib.parse as urlparse
import time

import eventlet
import eventlet.greenthread

from coreapis.utils import LogWrapper, get_feideids, translatable, failsafe
from coreapis.cache import Cache
from coreapis import cassandra_client, feide
from coreapis.groups.gogroups import (
    affiliation_names as go_affiliation_names, GOGroup, groupid_entitlement)
from coreapis.ldap import ORG_ATTRIBUTE_NAMES, GROUP_PERSON_ATTRIBUTES, get_single
from . import BaseBackend, IDHandler, Pool
ldap3 = eventlet.import_patched('ldap3')
ldap3.core = eventlet.import_patched('ldap3.core')
ldap3.core.exceptions = eventlet.import_patched('ldap3.core.exceptions')

ldapcontroller = eventlet.import_patched('coreapis.ldap.controller')

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

GROUPID_CANONICALIZATION_MIGRATION_TIME = {
    'feide.osloskolen.no': 1518044400,  # Thu Feb  8 00:00:00 CET 2018
    'tromso.kommune.no': 1513292400,  # Fri Dec 15 00:00:00 CET 2017
}

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
            'nn': 'Akademisk tilsett',
        }),
        'staff': translatable({
            'nb': 'Stab',
        }),
        'employee': translatable({
            'nb': 'Ansatt',
            'nn': 'Tilsett',
        }),
        'student': translatable({
            'nb': 'Student',
        }),
        'alum': translatable({
            'nb': 'Alumni',
        }),
        'affiliate': translatable({
            'nb': 'Tilknyttet',
            'nn': 'Tilknytt',
        }),
        # 'library-walk-in': translatable({
        # }),
        'member': translatable({
            'nb': 'Annet',
            'nn': 'Anna',
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
            if key in feide.SINGLE_VALUED_ATTRIBUTES:
                value = get_single(value)
            membership[PERSON_ATTRIBUTE_MAPPING[key]] = value
    affiliation = membership.get('affiliation', [])
    if 'employee' in affiliation:
        membership['basic'] = 'admin'
        membership['displayName'] = org_membership_name(affiliation, org_type)
    return membership


def should_canonicalize_groupid(realm):
    migration_time = GROUPID_CANONICALIZATION_MIGRATION_TIME.get(realm, 0)
    return time.time() >= migration_time


class LDAPBackend(BaseBackend):
    def __init__(self, prefix, maxrows, settings):
        super(LDAPBackend, self).__init__(prefix, maxrows, settings)
        self.log = LogWrapper('groups.ldapbackend')
        self.timer = settings.get('timer')
        self.ldap = ldapcontroller.LDAPController(settings)
        eventlet.greenthread.spawn(self.ldap.health_check_thread)
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.session = cassandra_client.Client(contact_points, keyspace, True, authz=authz)
        self.org_types = Cache(3600, 'groups.ldap_backend.cache')

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
                               ldap3.BASE,
                               ldap3.ALL_ATTRIBUTES, 1)
        if not org:
            raise KeyError('orgDN not found in catalog')
        org = org[0]
        org_attributes = org['attributes']
        org_type = list(self._get_org_type(realm).intersection(educational_org_types))
        if 'higher_education' not in org_type:
            org_type = ['{}_owner'.format(o) for o in org_type]
        res = {
            'id': self._groupid(realm),
            'displayName': get_single(org_attributes['eduOrgLegalName']),
            'type': 'fc:org',
            'public': True,
            'membership': org_membership(person, org_type),
            'orgType': org_type,
        }
        for attribute in ORG_ATTRIBUTE_NAMES:
            if attribute in org_attributes:
                res[attribute] = get_single(org_attributes[attribute])
        return res

    def _get_orgunit(self, realm, dn, primary_dn):
        ou = self.ldap.search(realm, dn, '(objectClass=*)',
                              ldap3.BASE,
                              ldap3.ALL_ATTRIBUTES, 1)
        if not ou:
            raise KeyError('orgUnitDN not found in catalog')
        ou = ou[0]
        ou_attributes = ou['attributes']
        org_type = self._get_org_type(realm).intersection(educational_org_types)
        data = {
            'id': self._groupid('{}:unit:{}'.format(
                realm,
                get_single(ou_attributes['norEduOrgUnitUniqueIdentifier']))),
            'parent': self._groupid(realm),
            'displayName': get_single(ou_attributes['ou']),
            'type': 'fc:orgunit',
            'public': True,
            'membership': {
                'basic': 'member',
            },
        }
        if 'higher_education' not in org_type:
            data['type'] = 'fc:org'
            data['orgType'] = list(org_type)
            data['membership']['primarySchool'] = (dn == primary_dn)
        else:
            data['membership']['primaryOrgUnit'] = (dn == primary_dn)
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
        group = GOGroup(group_info, canonicalize=should_canonicalize_groupid(realm))
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
                except KeyError as ex:
                    self.log.debug("GO Group ignored: {}".format(ex))
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
                               ldap3.SUBTREE,
                               GROUP_PERSON_ATTRIBUTES, 1)
        if not res:
            raise KeyError('could not find user in catalog')
        res = res[0]
        attributes = res['attributes']
        if 'eduPersonOrgDN' in attributes:
            org_dn = get_single(attributes['eduPersonOrgDN'])
            result.append(self._get_org(realm, org_dn, attributes))
        if 'eduPersonOrgUnitDN' in attributes:
            primary_org_unit = attributes.get('eduPersonPrimaryOrgUnitDN', [])
            if primary_org_unit:
                primary_org_unit = get_single(primary_org_unit)
            else:
                primary_org_unit = None
            for org_unit_dn in attributes['eduPersonOrgUnitDN']:
                result.append(self._get_orgunit(realm, org_unit_dn, primary_org_unit))
        if 'eduPersonEntitlement' in attributes:
            result.extend(self._handle_grepcodes(attributes['eduPersonEntitlement']))
            result.extend(self._handle_go_groups(realm, attributes['eduPersonEntitlement'],
                                                 show_all))
        return result

    def get_member_groups(self, user, show_all):
        result = []
        pool = Pool()
        get_member_groups = failsafe(functools.partial(self._get_member_groups, show_all))
        for res in pool.imap(get_member_groups, get_feideids(user)):
            if res:
                result.extend(res)
        return result

    def get_grep_group(self, user, groupid):
        try:
            return self.get_group(user, groupid)
        except KeyError:
            pass
        grep_id = unquote(self._intid(groupid))

        return self._handle_grepcode(grep_id, False)

    def get_members(self, user, groupid, show_all, include_member_ids):
        return []

    def _find_group_for_groupid(self, target, candidates, realm):
        for group_data in candidates:
            if not GOGroup.candidate(group_data):
                continue
            try:
                group = GOGroup(group_data, canonicalize=should_canonicalize_groupid(realm))
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
                                    ldap3.SUBTREE,
                                    query_attributes, 1000)
        res = []
        for hit in ldap_res:
            try:
                attributes = hit['attributes']
                entry = {'name': get_single(attributes['displayName'])}
                if include_member_ids:
                    entry['userid_sec'] = ['feide:{}'.format(get_single(attributes['eduPersonPrincipalName']))]
                group = self._find_group_for_groupid(entitlement_value, attributes['eduPersonEntitlement'], realm)
                entry['membership'] = group.membership()
                res.append(entry)
            except KeyError:
                self.log.debug("Dropping member for member list due to missing attributes")
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
                    "nb": "Organisasjonsenhet",
                    "nn": "Organisasjonseining"
                })
            },
        ]
