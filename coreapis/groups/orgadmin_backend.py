import functools

from coreapis.utils import LogWrapper, failsafe, translatable
from coreapis import cassandra_client
from . import BaseBackend, Pool

ORGADMIN_TYPE = 'fc:orgadmin'
SCOPES_NEEDED = {'scope_groups-orgadmin'}

ROLE_NO = {
    'admin': 'admin',
    'technical': 'teknisk',
    'mercantile': 'merkantil'
}

ORGADMIN_DISPLAYNAMES = {
    'fallback': 'Administratorer for {}',
    'nb': 'Administratorer for {}',
    'nn': 'Administratorar for {}',
    'en': 'Administrators for {}',
}


class BadOrgidError(RuntimeError):
    def __init__(self, message):
        super(BadOrgidError, self).__init__(message)
        self.message = message


def basic(role):
    if 'admin' in role:
        return 'admin'
    return 'member'


def format_membership(role):
    displayname_en = ", ".join(role).title()
    displayname_no = ", ".join([ROLE_NO.get(elem, elem) for elem in role]).title()
    return {
        'basic': basic(role),
        'displayName': translatable(dict(en=displayname_en,
                                         nb=displayname_no,
                                         nn=displayname_no)),
        'adminRoles': role
    }


def get_orgtag(orgid):
    try:
        orgtag = orgid.split(':')[2]
    except IndexError:
        raise BadOrgidError("Bad orgid: {}".format(orgid))
    return orgtag


def get_canonical_id(identity):
    if identity.startswith('feide:'):
        return identity.lower()
    return identity


def get_canonical_ids(user):
    return set(get_canonical_id(ident) for ident in user['userid_sec'])


def format_orgadmin_group(role):
    orgid = role['orgid']
    orgtag = get_orgtag(orgid)
    orgname = role['orgname']
    displayname = translatable({lang: ORGADMIN_DISPLAYNAMES[lang].format(orgname[lang])
                                for lang in orgname
                                if lang in ORGADMIN_DISPLAYNAMES})
    return {
        'id': '{}:{}'.format(ORGADMIN_TYPE, orgtag),
        'type': ORGADMIN_TYPE,
        'org': '{}'.format(orgid),
        'parent': '{}'.format(orgid),
        'displayName': displayname,
        'orgName': orgname,
        'orgType': role['orgtype'],
        'membership': format_membership(role['role'])
    }


class OrgAdminBackend(BaseBackend):
    def __init__(self, prefix, maxrows, settings):
        super(OrgAdminBackend, self).__init__(prefix, maxrows, settings)
        self.log = LogWrapper('groups.orgadminbackend')
        self.timer = settings.get('timer')
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.session = cassandra_client.Client(contact_points, keyspace, True, authz=authz)
        self.scopes_needed = SCOPES_NEEDED

    def get_members(self, user, groupid, show_all, include_member_ids):
        orgtag = get_orgtag(groupid)
        if not groupid.startswith("{}:".format(ORGADMIN_TYPE)):
            raise KeyError("Not an orgadmin group")
        org_type = ORGADMIN_TYPE[:ORGADMIN_TYPE.rfind("admin")]
        orgid = '{}:{}'.format(org_type, orgtag)
        result = []
        found = False
        roles = self.session.get_roles(['orgid = ?'], [orgid],
                                       self.maxrows)
        for role in roles:
            if role['identity'] in get_canonical_ids(user):
                found = True
            result.append({
                'userid': role['identity'],
                'membership': format_membership(role['role'])
            })
        if not found:
            raise KeyError("Not member of group")
        return result

    def _get_member_groups(self, pool, identity):
        result = []
        roles = list(self.session.get_roles(['identity = ?'], [get_canonical_id(identity)],
                                            self.maxrows))
        if not roles:
            return []
        orgnames = {role['orgid']: {} for role in roles}
        orgtypes = {role['orgid']: [] for role in roles}
        for org in pool.imap(failsafe(self.session.get_org), orgnames.keys()):
            if org:
                if 'name' in org and org['name']:
                    orgnames[org['id']] = org['name']
                if 'type' in org and org['type']:
                    orgtypes[org['id']] = org['type']
        for role in roles:
            try:
                orgid = role['orgid']
                role['orgname'] = translatable(orgnames[orgid])
                fallback = get_orgtag(orgid)
                role['orgname']['fallback'] = fallback
                role['orgtype'] = orgtypes[orgid]
                result.append(format_orgadmin_group(role))
            except RuntimeError as ex:
                self.log.warn('Skipping role: {}'.format(ex))
                continue
        return result

    def get_member_groups(self, user, show_all):
        result = []
        pool = Pool()
        for res in pool.imap(functools.partial(self._get_member_groups, pool),
                             get_canonical_ids(user)):
            result.extend(res)
        return result

    def grouptypes(self):
        return [
            {
                'id': ORGADMIN_TYPE,
                "displayName": translatable({
                    "en": "Organization Administrator Group",
                    "nb": "Organisasjonadministratorgruppe",
                })
            }
        ]
