import json
import re

import valideer as V

from coreapis.utils import (
    LogWrapper, get_platform_admins, AlreadyExistsError, ValidationError,
    json_normalize, userinfo_for_log)
from coreapis.cache import Cache
from coreapis import cassandra_client
from coreapis.crud_base import CrudControllerBase
from coreapis.clientadm.controller import ClientAdmController
from coreapis.ldap.status import ldap_status

VALID_SERVICES = ['auth', 'avtale', 'idporten', 'pilot', 'fsgroups', 'nostatus']
VALID_PREFIXES = ['facebook', 'feide', 'github', 'linkedin', 'nin', 'twitter']
VALID_ROLENAMES = ['admin', 'mercantile', 'technical']


def not_empty(thing):
    return len(thing) > 0


def valid_service(service):
    return service in VALID_SERVICES


def valid_feideid(feideid):
    pattern = r'[a-zA-Z0-9.-_]+@[a-zA-Z0-9-]+(\.[a-zA-Z0-9-]+)'
    return re.match(pattern, feideid)


def valid_identity(identity):
    provider_prefix, separator, user_key = identity.partition(':')
    if separator != ':':
        ret = False
    elif provider_prefix == 'feide':
        ret = valid_feideid(user_key)
    elif provider_prefix in VALID_PREFIXES and user_key != '':
        ret = True
    else:
        ret = False
    return ret


def valid_rolenames(rolenames):
    try:
        return all(name in VALID_ROLENAMES for name in rolenames)
    except TypeError:
        return False


class OrgController(CrudControllerBase):
    schema = {
        # Required
        '+id': 'string',
        '+name': V.AllOf(V.Mapping(key_schema=V.String(min_length=2, max_length=3),
                                   value_schema='string'),
                         not_empty),  # Just len works, but who would understand the message?
        # Other attributes
        'fs_groups': '?boolean',
        'realm': '?string',
        'type': V.Nullable(['string']),
        'organization_number': '?string',
        'uiinfo': V.Nullable({}),
        'services': V.Nullable([valid_service]),
        # Virtual attributes - not stored in database
        'has_ldapgroups': '?boolean',
        'has_peoplesearch': '?boolean',
        'peoplesearch': V.Nullable({})
    }
    geo_schema = {
        '+lat': 'number',
        '+lon': 'number',
    }
    platformadmin_attrs = []
    platformadmin_attrs_update = []
    protected_attrs = ['has_ldapgroups', 'has_peoplesearch', 'peoplesearch']
    protected_attrs_update = ['id']

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        timer = settings.get('timer')
        maxrows = settings.get('orgadmin_maxrows')
        ldap_config = settings.get('ldap_config_file', 'ldap-config.json')
        super(OrgController, self).__init__(maxrows)
        self.t = timer
        self.log = LogWrapper('org.OrgController')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        self.log.debug('org controller init', keyspace=keyspace)
        self.cadm_controller = ClientAdmController(settings)
        self.ldap_config_file = ldap_config
        self.ldap_certs = settings.get('ldap_ca_certs', None)
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)
        self.ldap_config_cache = Cache(300, 'org.OrgController.ldap_config_cache')

    def _get_ldap_config(self):
        with open(self.ldap_config_file) as configfile:
            return json.load(configfile)

    @property
    def ldap_config(self):
        return self.ldap_config_cache.get('conf', self._get_ldap_config)

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
                for val in psconf.values():
                    if val != "none":
                        has_peoplesearch = True
                        break
        org['has_ldapgroups'] = has_ldapgroups
        org['has_peoplesearch'] = has_peoplesearch
        org['peoplesearch'] = psconf
        if 'uiinfo' in org and org['uiinfo']:
            org['uiinfo'] = json.loads(org['uiinfo'])
        return org

    def get(self, orgid):
        self.log.debug('Get org', orgid=orgid)
        org = self.session.get_org(orgid)
        return org

    def show_org(self, orgid):
        org = self.format_org(self.get(orgid))
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

    def add_org(self, user, org):
        org = self.validate(org)
        if self.exists(org['id']):
            raise AlreadyExistsError('item already exists')
        self.log.info('adding organization',
                      audit=True, orgid=org['id'], user=userinfo_for_log(user))
        self.session.insert_org(org)
        return org

    def update_org(self, user, orgid, attrs):
        org = json_normalize(self.show_org(orgid))
        org.update(attrs)
        org = self.validate(org)
        self.log.info('updating organization',
                      audit=True, orgid=orgid, attrs=attrs,
                      user=userinfo_for_log(user))
        self.session.insert_org(org)
        return org

    def delete_org(self, user, orgid):
        if self.list_mandatory_clients(orgid):
            raise ValidationError('org {} has mandatory clients'.format(orgid))
        if self.list_org_roles(orgid):
            raise ValidationError('org {} has roles'.format(orgid))
        self.log.info('delete organization',
                      audit=True, orgid=orgid, user=userinfo_for_log(user))
        self.session.delete_org(orgid)

    def get_logo(self, orgid):
        logo, updated = self.session.get_org_logo(orgid)
        if logo is None or updated is None:
            return None, None
        return logo, updated

    def _save_logo(self, orgid, data, updated):
        self.session.save_org_logo('organizations', orgid, data, updated)

    def validate_geo(self, geo):
        validator = V.parse(self.geo_schema, additional_properties=False)
        validator.validate(geo)
        if not ((-180. <= geo['lon'] <= 180.) and (-90. <= geo['lat'] <= 90.)):
            raise ValidationError('coordinates outside range: {}'.format(geo))

    def update_geo(self, user, orgid, payload, add):
        try:
            for geo in payload:
                self.validate_geo(geo)
        except V.ValidationError:
            raise ValidationError('payload must be an array of coordinates: {}'.format(payload))

        org = self.session.get_org(orgid)
        self.log.info('updating geo coordinates for organization',
                      audit=True, orgid=orgid, payload=payload, add=add,
                      user=userinfo_for_log(user))
        print("uiinfo:", org.get('uiinfo'))
        uiinfo = json.loads(org.get('uiinfo', "{}"))
        if add:
            geos = uiinfo.get('geo', []) + payload
        else:
            geos = payload
        uiinfo['geo'] = geos
        org['uiinfo'] = uiinfo
        self.session.insert_org(org)

    def list_mandatory_clients(self, orgid):
        org = self.session.get_org(orgid)
        clientids = []
        if org.get('realm'):
            clientids = self.session.get_mandatory_clients(org['realm'])
        cadm = self.cadm_controller
        return cadm.get_public_client_list(self.session.get_clients_by_id(clientids).values())

    def add_mandatory_client(self, user, orgid, clientid):
        org = self.session.get_org(orgid)
        realm = org['realm']
        self.log.info('making client mandatory for organization',
                      audit=True, orgid=orgid, clientid=clientid,
                      user=userinfo_for_log(user))
        self.session.add_mandatory_client(realm, clientid)

    def del_mandatory_client(self, user, orgid, clientid):
        org = self.session.get_org(orgid)
        realm = org['realm']
        self.log.info('making client optional for organization',
                      audit=True, orgid=orgid, clientid=clientid,
                      user=userinfo_for_log(user))
        self.session.del_mandatory_client(realm, clientid)

    def list_services(self, orgid):
        org = self.session.get_org(orgid)
        services = org.get('services', [])
        if services is None:
            services = []
        return list(services)

    def add_service(self, user, orgid, service):
        if not valid_service(service):
            raise ValidationError('payload must be a valid service')
        self.log.info('enabling service for organization',
                      audit=True, orgid=orgid, service=service,
                      user=userinfo_for_log(user))
        services = set()
        services.add(service)
        self.session.add_services(orgid, services)

    def del_service(self, user, orgid, service):
        if not valid_service(service):
            raise ValidationError('not a valid service')
        self.log.info('disabling service for organization',
                      audit=True, orgid=orgid, service=service,
                      user=userinfo_for_log(user))
        services = set()
        services.add(service)
        self.session.del_services(orgid, services)

    def list_org_roles(self, orgid):
        roles = self.session.get_roles(['orgid = ?'], [orgid], self.maxrows)
        return [dict(identity=role['identity'], role=role['role']) for role in roles]

    def add_org_role(self, user, orgid, identity, rolenames):
        if not valid_identity(identity):
            raise ValidationError('{} is not a valid identity'.format(identity))
        if not valid_rolenames(rolenames):
            raise ValidationError('{} is not a list of valid role names'.format(rolenames))
        self.log.info('enabling role for organization',
                      audit=True, orgid=orgid, identity=identity, rolenames=rolenames,
                      user=userinfo_for_log(user))
        role = dict(orgid=orgid, identity=identity, role=rolenames)
        self.session.insert_role(role)

    def del_org_role(self, user, orgid, identity):
        if not valid_identity(identity):
            raise ValidationError('not a valid identity')
        self.log.info('disabling role for organization',
                      audit=True, orgid=orgid, identity=identity,
                      user=userinfo_for_log(user))
        self.session.del_role(orgid, identity)

    def has_permission(self, user, org, needs_platform_admin):
        if user is None or not self.is_admin(user, org['id']):
            print("Fail a")
            print(user)
            return False
        if needs_platform_admin and not self.is_platform_admin(user):
            print("Fail b")
            return False
        return True

    def ldap_status(self, user, orgid, feideid):
        org = self.session.get_org(orgid)
        realm = org.get('realm', None)
        return ldap_status(realm, feideid, self.ldap_config, self.ldap_certs)
