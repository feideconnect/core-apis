import json
from coreapis.utils import LogWrapper
from coreapis import cassandra_client


class OrgController(object):
    def __init__(self, contact_points, keyspace, timer):
        self.t = timer
        self.config = json.load(open('ldap-config.json'))
        self.log = LogWrapper('org.OrgController')
        self.session = cassandra_client.Client(contact_points, keyspace)

    def show_org(self, orgid):
        org = self.session.get_org(orgid)
        return org

    def list_orgs(self):
        return self.session.list_orgs()

    def get_logo(self, orgid):
        logo, updated = self.session.get_org_logo(orgid)
        if logo is None or updated is None:
            return None, None
        return logo, updated
