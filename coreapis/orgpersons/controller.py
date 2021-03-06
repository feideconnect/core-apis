from coreapis import cassandra_client
from coreapis.clientadm.controller import ClientAdmController
from coreapis.ldap.controller import validate_query
from coreapis.peoplesearch.controller import flatten
from coreapis.utils import LogWrapper

from ldap3.utils.log import set_library_log_detail_level, BASIC
set_library_log_detail_level(BASIC)

LDAP_ATTRIBUTES = ['displayName', 'mail', 'eduPersonPrincipalName']


def _get_photo_secid(secids):
    for secid in secids:
        if secid.startswith('p:'):
            return secid
    return None


class OrgPersonController(object):

    def __init__(self, settings):
        self.search_max_replies = settings.get('orgpersons_max_replies', 50)
        contact_points = settings.get('cassandra_contact_points')
        keyspace = settings.get('cassandra_keyspace')
        authz = settings.get('cassandra_authz')
        self.ldap = settings.get('ldap_controller')
        self.session = cassandra_client.Client(contact_points, keyspace, authz=authz)
        self.log = LogWrapper('orgpersons.OrgPersonController')
        self.userinfo_base_url = settings.get('userinfo_base_url')
        self.tmr = settings.get('timer')
        self.cadm_controller = ClientAdmController(settings)

    def get_subscopes(self, clientid, searchrealm):
        client = self.cadm_controller.get(clientid)
        orgauthz = self.cadm_controller.get_orgauthorization(client, searchrealm)
        self.log.debug("get_subscopes", clientid=clientid, orgauthz=orgauthz)
        return [parts[2] for parts in [oa.split('_', 2) for oa in orgauthz] if len(parts) > 2]

    def _format_person(self, person):
        flatten(person, LDAP_ATTRIBUTES)
        new_person = {
            'name': person['displayName'],
            'email': person['mail'],
        }
        feideid = 'feide:' + person['eduPersonPrincipalName']
        new_person['userid_sec'] = [feideid]
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
            secids = set(new_person['userid_sec'])
            secids.update(subject['userid_sec'])
            new_person['userid_sec'] = list(secids)
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

    def search_users(self, orgid, query, max_replies=10):
        return self._search(orgid, query, max_replies)

    def lookup_user(self, principalname):
        person = self.ldap.lookup_feideid(principalname, LDAP_ATTRIBUTES)
        try:
            return self._format_person(person)
        except KeyError:
            raise RuntimeError("mandatory person attribute missing from ldap, person={}"
                               .format(person))
