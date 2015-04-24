from coreapis.utils import LogWrapper, get_feideid
from . import BaseBackend
from coreapis import cassandra_client

orgadmin_type = 'fc:orgadmin'


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
    return {
        'basic': basic(role),
        'displayName': ", ".join(role).title(),
        'adminRoles': role
    }


def get_orgname(orgid):
    try:
        orgname = orgid.split(':')[2]
    except IndexError:
        raise BadOrgidError("Bad orgid: {}".format(orgid))
    return orgname


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
        orgname = get_orgname(orgid)

        displayname = 'Administratorer for {}'.format(orgname)
        return {
            'id': '{}:{}'.format(orgadmin_type, orgname),
            'type': orgadmin_type,
            'org': '{}'.format(orgid),
            'parent': '{}'.format(orgid),
            'displayName': displayname,
            'orgName': orgname,
            'membership': format_membership(role['role'])
        }

    def get_member_groups(self, user, show_all):
        result = []
        feideid = get_feideid(user)
        for role in self.session.get_roles(feideid, None, self.maxrows):
            try:
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
