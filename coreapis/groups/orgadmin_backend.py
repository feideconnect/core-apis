from coreapis.utils import LogWrapper, get_feideid, failsafe
from . import BaseBackend
from coreapis import cassandra_client
from eventlet.greenpool import GreenPile

ORGADMIN_TYPE = 'fc:orgadmin'

ROLE_NB = {
    'admin': 'admin',
    'technical': 'teknisk',
    'mercantile': 'merkantil'
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
    displayname = 'Administratorer for {}'.format(orgname)
    return {
        'id': '{}:{}'.format(ORGADMIN_TYPE, orgtag),
        'type': ORGADMIN_TYPE,
        'org': '{}'.format(orgid),
        'parent': '{}'.format(orgid),
        'displayName': displayname,
        'orgName': orgname,
        'membership': format_membership(role['role'])
    }


class OrgAdminBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(OrgAdminBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.orgadminbackend')
        self.timer = config.get_settings().get('timer')
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)

    def get_members(self, user, groupid, show_all):
        feideid = get_feideid(user)
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
            if role['feideid'] == feideid:
                found = True
            result.append({
                'userid': 'feide:{}'.format(role['feideid']),
                'membership': format_membership(role['role'])
            })
        if not found:
            raise KeyError("Not member of group")
        return result

    def get_member_groups(self, user, show_all):
        result = []
        feideid = get_feideid(user)
        pile = GreenPile()
        roles = self.session.get_roles(['feideid = ?'], [feideid],
                                       self.maxrows)
        if len(roles) == 0:
            return []
        orgnames = {role['orgid']: {} for role in roles}
        for orgid in orgnames.keys():
            pile.spawn(failsafe(self.session.get_org), orgid)
        for org in pile:
            if org and 'name' in org and org['name']:
                orgnames[org['id']] = org['name']
        for role in roles:
            try:
                orgid = role['orgid']
                fallback = get_orgtag(orgid)
                # Hardcoding Norwegian displaynames for now
                role['orgname'] = orgnames[orgid].get('nb', fallback)
                result.append(format_orgadmin_group(role))
            except RuntimeError as ex:
                self.log.warn('Skipping role: {}'.format(ex))
                continue
        return result

    def grouptypes(self):
        return [
            {
                'id': ORGADMIN_TYPE,
                "displayName": {
                    "en": "Organization Administrator Group",
                    "nb": "Organisasjonadministratorgruppe",
                }
            }
        ]
