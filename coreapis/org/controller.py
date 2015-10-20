import json
from coreapis.utils import LogWrapper, get_feideid
from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.clientadm.controller import ClientAdmController


class OrgController(CrudControllerBase):
    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        timer = settings.get('timer')
        maxrows = settings.get('clientadm_maxrows')
        ldap_config = settings.get('ldap_config_file', 'ldap-config.json')
        super(OrgController, self).__init__(maxrows)
        self.t = timer
        self.log = LogWrapper('org.OrgController')
        self.session = cassandra_client.Client(contact_points, keyspace)
        self.log.debug('org controller init', keyspace=keyspace)
        self.cadm_controller = ClientAdmController(settings)
        self.ldap_config = json.load(open(ldap_config))

    def format_org(self, org):
        has_ldapgroups = False
        has_peoplesearch = False
        psconf = None
        realm = org['realm']
        if realm in self.ldap_config:
            has_ldapgroups = True
            realmconf = self.ldap_config[realm]
            psconf = realmconf.get('peoplesearch')
            if psconf:
                for v in psconf.values():
                    if v != "none":
                        has_peoplesearch = True
                        break
        org['has_ldapgroups'] = has_ldapgroups
        org['has_peoplesearch'] = has_peoplesearch
        org['peoplesearch'] = psconf
        if 'uiinfo' in org and org['uiinfo']:
            org['uiinfo'] = json.loads(org['uiinfo'])
        return org

    def show_org(self, orgid):
        org = self.format_org(self.session.get_org(orgid))
        return org

    def list_orgs(self, want_peoplesearch=None):
        res = []
        for org in self.session.list_orgs():
            org = self.format_org(org)
            if want_peoplesearch is None:
                res.append(org)
            else:
                if want_peoplesearch == org['has_peoplesearch']:
                    res.append(org)
        return res

    def get_logo(self, orgid):
        logo, updated = self.session.get_org_logo(orgid)
        if logo is None or updated is None:
            return None, None
        return logo, updated

    def list_mandatory_clients(self, orgid):
        org = self.session.get_org(orgid)
        clientids = self.session.get_mandatory_clients(org['realm'])
        cadm = self.cadm_controller
        return [cadm.get_public_client(cadm.get(clientid)) for clientid in clientids]

    def add_mandatory_client(self, user, orgid, clientid):
        org = self.session.get_org(orgid)
        realm = org['realm']
        self.log.info('making client mandatory for organization',
                      audit=True, orgid=orgid, clientid=clientid,
                      user=get_feideid(user))
        self.session.add_mandatory_client(realm, clientid)

    def del_mandatory_client(self, user, orgid, clientid):
        org = self.session.get_org(orgid)
        realm = org['realm']
        self.log.info('making client optional for organization',
                      audit=True, orgid=orgid, clientid=clientid,
                      user=get_feideid(user))
        self.session.del_mandatory_client(realm, clientid)

    def has_permission(self, user, orgid):
        if user is None or not self.is_org_admin(user, orgid):
            return False
        org = self.session.get_org(orgid)
        if not org['realm']:
            return False
        return True
