from coreapis.utils import LogWrapper, get_feideid
from . import BaseBackend
from coreapis import cassandra_client


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


class OrgAdminBackend(BaseBackend):
    def __init__(self, prefix, maxrows, config):
        super(OrgAdminBackend, self).__init__(prefix, maxrows, config)
        self.log = LogWrapper('groups.orgadminbackend')
        self.timer = config.get_settings().get('timer')
        contact_points = config.get_settings().get('cassandra_contact_points')
        keyspace = config.get_settings().get('cassandra_keyspace')
        self.session = cassandra_client.Client(contact_points, keyspace, True)

    def format_orgadmin_group(self, role):
        grouptype = 'fc:orgadmin'
        orgid = role['orgid']
        orgname = orgid.split(':')[2]

        displayname = '{} Administratorer'.format(orgname)
        return {
            'id': '{}:{}'.format(grouptype, orgname),
            'type': grouptype,
            'org': '{}'.format(orgid),
            'parent': '{}'.format(orgid),
            'displayName': displayname,
            'membership': format_membership(role['role'])
        }

    def get_member_groups(self, user, show_all):
        result = []
        feideid = get_feideid(user)
        for role in self.session.get_roles(feideid, None, self.maxrows):
            result.append(self.format_orgadmin_group(role))
        return result
