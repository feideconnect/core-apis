import functools
from coreapis.utils import LogWrapper, get_feideids, failsafe, translatable
from . import BaseBackend
from coreapis import cassandra_client
from eventlet.greenpool import GreenPool

ORGADMIN_TYPE = 'fc:orgadmin'
SCOPES_NEEDED = {'scope_groups-orgadmin'}

ROLE_NB = {
    'admin': 'admin',
    'technical': 'teknisk',
    'mercantile': 'merkantil'
}

ORGADMIN_DISPLAYNAMES = {
    'fallback': 'Administratorer for {}',
    'nb': 'Administratorer for {}',
    'nn': 'Administratorer for {}',
    'en': 'Administrators for {}',
}


class BadOrgidError(RuntimeError):
    def __init__(self, message):
        super(BadOrgidError, self).__init__(message)
        self.message = message


def basic(role):
    if 'admin' in role:
        return 'admin'
    else:
        return 'member'


def format_membership(role):
    displayname = ", ".join([ROLE_NB.get(elem, elem) for elem in role]).title()
    return {
        'basic': basic(role),
        'displayName': displayname,
        'adminRoles': role
    }


def get_orgtag(orgid):
    try:
        orgtag = orgid.split(':')[2]
    except IndexError:
        raise BadOrgidError("Bad orgid: {}".format(orgid))
    return orgtag


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
        self.session = cassandra_client.Client(contact_points, keyspace, True)
        self.scopes_needed = SCOPES_NEEDED

    def get_members(self, user, groupid, show_all, include_member_ids):
        feideids = get_feideids(user)
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
            if role['feideid'] in feideids:
                found = True
            result.append({
                'userid': 'feide:{}'.format(role['feideid']),
                'membership': format_membership(role['role'])
            })
        if not found:
            raise KeyError("Not member of group")
        return result

    def _get_member_groups(self, pool,  feideid):
        result = []
        roles = self.session.get_roles(['feideid = ?'], [feideid],
                                       self.maxrows)
        if len(roles) == 0:
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
        pool = GreenPool()
        for res in pool.imap(functools.partial(self._get_member_groups, pool), get_feideids(user)):
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
