from coreapis import cassandra_client
from coreapis.clientadm.controller import ClientAdmController
from coreapis.ldap.controller import validate_query
from coreapis.peoplesearch.controller import flatten
from coreapis.utils import LogWrapper, ValidationError
from coreapis.utils import get_platform_admins

LDAP_ATTRIBUTES = ['displayName', 'mail', 'eduPersonPrincipalName']
def _get_photo_secid(secids):
    for secid in secids:
        if secid.startswith('p:'):
            return secid


class OrgPersonController(object):

    def __init__(self, settings):
        self.search_max_replies = settings.get('orgpersons_max_replies', 50)
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.ldap = settings.get('ldap_controller')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)
        self.log = LogWrapper('orgpersons.OrgPersonController')
        self.userinfo_base_url = settings.get('userinfo_base_url')
        self.tmr = settings.get('timer')
        self.cadm_controller = ClientAdmController(settings)

    # Services that do not represent users get access if client orgauthorization
    # for the org being queried has the gk_orgpersons_search scope.
    # Admin users also get access.
    def has_permission(self, clientid, orgid, user):
        if self.cadm_controller.is_admin(user, orgid):
            return True
        if user:
            self.log.info("orgpersons not available to users", userid=user['userid'])
            return False
        client = self.cadm_controller.get(clientid)
        if 'gk_orgpersons_search' in self.cadm_controller.get_orgauthorization(client, orgid):
            return True
        return False

    def _format_person(self, person):
        flatten(person, LDAP_ATTRIBUTES)
        new_person = {
            'name': person['displayName'],
            'email': person['mail'],
        }
        feideid = 'feide:' + person['eduPersonPrincipalName']

        userid = None
        try:
            userid = self.session.get_userid_by_userid_sec(feideid)
        except KeyError:
            self.log.debug("never logged into dataporten yet", feideid=feideid)
        if userid:
            subject = self.session.get_user_by_id(userid)
            new_person['sub'] = subject['userid']
            photo_secid = _get_photo_secid(subject['userid_sec'])
            if photo_secid:
                url = '{}/v1/user/media/{}'.format(self.userinfo_base_url, photo_secid)
                new_person['picture'] = url
                subject['userid_sec'].remove(photo_secid)
            new_person['dataporten-userid_sec'] = subject['userid_sec']
        return new_person

    def _search(self, org, query, max_replies):
        self.log.debug("_search", org=org, query=query)
        if max_replies is None or max_replies > self.search_max_replies:
            max_replies = self.search_max_replies
        validate_query(query)
        if '@' in query:
            search_filter = '(|(mail={})(eduPersonPrincipalName={}))'.format(query, query)
        else:
            search_filter = '(displayName=*{}*)'.format(query)
        search_filter = '(&{}(objectClass=person))'.format(search_filter)
        self.log.debug("_search", search_filter=search_filter)
        res = self.ldap.ldap_search(org, search_filter, 'SUBTREE',
                                    attributes=LDAP_ATTRIBUTES, size_limit=max_replies)
        with self.tmr.time('ps.process_results'):
            result = [dict(r['attributes']) for r in res]
            new_result = []
            for person in result:
                try:
                    new_result.append(self._format_person(person))
                except KeyError:
                    self.log.warn('Failed to read mandatory attribute for person in search')
            return new_result

    def get_orgpersons(self, orgid, query, max_replies=10):
        return self._search(orgid, query, max_replies)

    def get_orgperson(self, principalname):
        person = self.ldap.lookup_feideid(principalname, LDAP_ATTRIBUTES)
        try:
            return self._format_person(person)
        except KeyError:
            raise RuntimeError("mandatory person attribute missing from ldap, person={}"
                                  .format(person))
