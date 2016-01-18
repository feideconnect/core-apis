import json
import ssl

import ldap3
#import ldap3.ssl

from coreapis.utils import LogWrapper, get_feideid, get_platform_admins
from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.clientadm.controller import ClientAdmController


def ldap_exception_argument(ex):
    if isinstance(ex.args[0], Exception):
        return ldap_exception_argument(ex.args[0])
    return ex.args[0]


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
        self.ldap_certs = settings.get('ldap_ca_certs', None)
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)

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
        if user is None or not self.is_admin(user, orgid):
            return False
        org = self.session.get_org(orgid)
        if not org['realm']:
            return False
        return True

    def ldap_status(self, user, orgid):
        org = self.session.get_org(orgid)
        realm = org.get('realm', None)
        if not realm or not realm in self.ldap_config:
            return {'error': 'Missing configuration for realm {}'.format(realm)}
        orgconfig = self.ldap_config[realm]
        feideid = get_feideid(user)

        status = {}
        base_dn = orgconfig['base_dn']
        search_filter = '(eduPersonPrincipalName={})'.format(feideid)
        attributes = ['eduPersonPrincipalName', 'eduPersonOrgDN']
        tls = ldap3.Tls(validate=ssl.CERT_REQUIRED,
                        ca_certs_file=self.ldap_certs)
        if 'bind_user' in orgconfig:
            user = orgconfig['bind_user']['dn']
            password = orgconfig['bind_user']['password']
        else:
            user = None
            password = None
        for server in orgconfig['servers']:
            if ':' in server:
                host, port = server.split(':', 1)
                port = int(port)
            else:
                host, port = server, None
            ldapserver = ldap3.Server(host, port=port, use_ssl=True, connect_timeout=1, tls=tls)

            try:
                con = ldap3.Connection(ldapserver, auto_bind=True,
                                       user=user, password=password,
                                       client_strategy=ldap3.STRATEGY_SYNC,
                                       check_names=True)
                con.search(base_dn, search_filter, ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                           attributes=attributes, size_limit=1)
                if len(con.response) == 0:
                    status[server] = {
                        'result': 'empty response',
                    }
                else:
                    status[server] = {
                        'result': 'success',
                    }
            except ldap3.core.exceptions.LDAPCommunicationError as ex:
                status[server] = {
                    'result': 'Communications Error',
                    'class': ex.__class__.__name__,
                    'message': ldap_exception_argument(ex),
                }
                if len(ex.args) > 1 and isinstance(ex.args[1], list) and len(ex.args[1][0]) > 2:
                    status[server]['details'] = ex.args[1][0][2].args[0]
            except ldap3.core.exceptions.LDAPBindError as ex:
                status[server] = {
                    'result': 'bind_error',
                    'class': ex.__class__.__name__,
                    'message': ex.args[0],
                }
                if len(ex.args) > 1 and isinstance(ex.args[1], list) and len(ex.args[1][0]) > 2:
                    status[server]['details'] = ex.args[1][0][2].args[0]
            except Exception as ex:
                message = 'Unknown error'
                if len(ex.args) > 0:
                    message = ex.args[0]
                status[server] = {
                    'result': 'other error',
                    'class': ex.__class__.__name__,
                    'message': message,
                }

        return status
