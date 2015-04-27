from coreapis.utils import LogWrapper, get_feideid, failsafe
from . import BaseBackend
from coreapis import cassandra_client
from eventlet.greenpool import GreenPile

orgadmin_type = 'fc:orgadmin'

role_nb = {
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
    displayname = ", ".join([role_nb.get(elem, elem) for elem in role]).title()
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


class OrgAdminBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(OrgAdminBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.orgadminbackend')
        self.timer = config.get_settings().get('timer')
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)

    def format_orgadmin_group(self, role):
        orgid = role['orgid']
        orgtag = get_orgtag(orgid)
        orgname = role['orgname']

        displayname = 'Administratorer for {}'.format(orgname)
        return {
            'id': '{}:{}'.format(orgadmin_type, orgtag),
            'type': orgadmin_type,
            'org': '{}'.format(orgid),
            'parent': '{}'.format(orgid),
            'displayName': displayname,
            'orgName': orgname,
            'membership': format_membership(role['role'])
        }

    def get_members(self, user, groupid, show_all):
        feideid = get_feideid(user)
        orgtag = get_orgtag(groupid)
        orgid = 'fc:org:{}'.format(orgtag)
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
        orgnames = {}
        feideid = get_feideid(user)
        pile = GreenPile()
        roles = self.session.get_roles(['feideid = ?'], [feideid],
                                       self.maxrows)
        if len(roles) == 0:
            return []
        for role in roles:
            orgid = role['orgid']
            orgnames[orgid] = {}
        for orgid in orgnames.keys():
            pile.spawn(failsafe(self.session.get_org), orgid)
        for org in pile:
            if org:
                orgnames[org['id']] = org.get('name', {})
        for role in roles:
            try:
                orgid = role['orgid']
                fallback = get_orgtag(orgid)
                # Hardcoding Norwegian displaynames for now
                role['orgname'] = orgnames[orgid].get('nb', fallback)
                result.append(self.format_orgadmin_group(role))
            except RuntimeError as ex:
                self.log.warn('Skipping role: {}'.format(ex.message))
                continue
        return result

    def grouptypes(self):
        return [
            {
                'id': orgadmin_type,
                "displayName": {
                    "en": "Organization Administrator Group",
                    "nb": "Organisasjonadministratorgruppe",
                }
            }
        ]
