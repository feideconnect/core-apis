import base64
import datetime
import hashlib
import io

from PIL import Image

from coreapis.utils import ValidationError, LogWrapper, now, \
    get_platform_admins, get_feideids
from .tokens import crypt_token, decrypt_token
import coreapis.cassandra_client
from coreapis.ldap.controller import validate_query
from coreapis.ldap import PEOPLE_SEARCH_ATTRIBUTES, get_single

THUMB_SIZE = 128, 128
SINGLE_VALUED_ATTRIBUTES = ['cn', 'displayName', 'eduPersonPrincipalName']


def flatten(user, attributes):
    for attr in attributes:
        if attr in user:
            user[attr] = get_single(user[attr])


def make_etag(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


def in_org(user, org):
    for uid in [uid for uid in user['userid_sec'] if uid.startswith('feide:')]:
        _, uorg = uid.split('@')
        if uorg == org:
            return True
    return False


class CassandraCache(coreapis.cassandra_client.Client):
    def __init__(self, contact_points, keyspace, authz):
        super(CassandraCache, self).__init__(contact_points, keyspace, False, authz)

    def lookup(self, user):
        s_lookup = self._prepare('SELECT * from profile_image_cache where user=?')
        res = list(self.session.execute(s_lookup.bind([user])))
        if len(res) == 0:
            return None
        entry = res[0]
        return entry

    def insert(self, user, last_updated, last_modified, etag, image):
        s_insert = self._prepare('UPDATE profile_image_cache set last_modified=?, etag=?, last_updated=?, image=? WHERE user=?')
        self.session.execute(s_insert.bind([last_modified, etag, last_updated, image, user]))


class PeopleSearchController(object):

    def __init__(self, ldap_controller, settings):
        key = base64.b64decode(settings.get('profile_token_secret'))
        contact_points = settings.get('cassandra_contact_points')
        authz = settings.get('cassandra_authz')
        cache_keyspace = settings.get('peoplesearch.cache_keyspace')
        cache_update_seconds = int(settings.get('peoplesearch.cache_update_seconds', 3600))
        timer = settings.get('timer')

        self.key = key
        self.t = timer
        self.ldap = ldap_controller
        self.image_cache = dict()
        self.log = LogWrapper('peoplesearch.PeopleSearchController')
        self.db = CassandraCache(contact_points, cache_keyspace, authz)
        self.cache_update_age = datetime.timedelta(seconds=cache_update_seconds)
        self.search_max_replies = 50
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)

    def valid_org(self, org):
        return org in self.ldap.get_ldap_config()

    def orgs(self):
        conf = self.ldap.get_ldap_config()
        return {realm: data['display'] for realm, data in conf.items()}

    def _format_person(self, person):
        flatten(person, SINGLE_VALUED_ATTRIBUTES)
        new_person = {}
        if 'eduPersonPrincipalName' in person:
            feideid = person['eduPersonPrincipalName']
            person['id'] = 'feide:' + feideid
            new_person['profile_image_token'] = crypt_token(person['id'], self.key)
        if 'displayName' in person:
            new_person['name'] = person['displayName']
        else:
            raise KeyError()
        return new_person

    def org_authorization_policy(self, org):
        res = {
            "employees": "none",
            "others": "none"
        }
        orgconf = self.ldap.get_ldap_config().get(org, {})
        psconf = orgconf.get('peoplesearch', {})
        for key, val in psconf.items():
            if key in {"employees", "others"}:
                res[key] = val
        return res

    def authorized_search_access(self, user, org):
        res = set()
        for key, val in self.org_authorization_policy(org).items():
            if val == 'all' or val == 'sameOrg' and in_org(user, org):
                res.add(key)
        return res

    def is_platform_admin(self, user):
        if user is None:
            return False
        for feideid in get_feideids(user):
            if feideid in self.platformadmins:
                return True
        return False

    def admin_search(self, org, query, user, sameorg, max_replies=None):
        access = set()
        for key, val in self.org_authorization_policy(org).items():
            if val == 'all' or val == 'sameOrg' and sameorg:
                access.add(key)
        return self._search(org, query, user, max_replies, access)

    def search(self, org, query, user, max_replies=None):
        access = self.authorized_search_access(user, org)
        return self._search(org, query, user, max_replies, access)

    def _search(self, org, query, user, max_replies, access):
        if not ('employees' in access or 'others' in access):
            return []
        if max_replies is None or max_replies > self.search_max_replies:
            max_replies = self.search_max_replies
        validate_query(query)
        if '@' in query:
            search_filter = '(mail={})'.format(query)
        elif query.isnumeric():
            search_filter = '(mobile={})'.format(query)
        else:
            search_filter = '(displayName=*{}*)'.format(query)
        search_filter = '(&{}(objectClass=person))'.format(search_filter)
        if 'others' in access and 'employees' not in access:
            search_filter = '(&{}(!(eduPersonAffiliation=employee)))'.format(search_filter)
        elif 'employees' in access and 'others' not in access:
            search_filter = '(&{}(eduPersonAffiliation=employee))'.format(search_filter)
        res = self.ldap.ldap_search(org, search_filter, 'SUBTREE',
                                    attributes=PEOPLE_SEARCH_ATTRIBUTES, size_limit=max_replies)
        with self.t.time('ps.process_results'):
            result = [dict(r['attributes']) for r in res]
            new_result = []
            for person in result:
                try:
                    new_result.append(self._format_person(person))
                except KeyError:
                    self.log.warn('Failed to read mandatory attribute for person in search')
            return new_result

    def _profile_image_feide(self, user):
        try:
            attributes = self.ldap.lookup_feideid(user, ['jpegPhoto'])
        except KeyError:
            return None, None, None
        if 'jpegPhoto' not in attributes:
            self.log.debug('User %s has no jpegPhoto' % user)
            return None, None, None
        data = get_single(attributes['jpegPhoto'])
        return data, make_etag(data), now()

    def decrypt_profile_image_token(self, token):
        return decrypt_token(token, self.key)

    def _default_image(self):
        with open('data/default-profile.jpg', 'rb') as fh:
            data = fh.read()
            etag = make_etag(data)
            return data, etag, now()

    def _fetch_profile_image(self, user):
        if ':' not in user:
            raise ValidationError('user id must contain ":"')
        idtype, user = user.split(':', 1)
        if idtype == 'feide':
            data, etag, last_modified = self._profile_image_feide(user)
        else:
            raise ValidationError("Unhandled user id type '{}'".format(idtype))
        if data is None:
            data, etag, last_modified = self._default_image()
        with self.t.time('ps.profileimage.scale'):
            fake_file = io.BytesIO(data)
            image = Image.open(fake_file)
            image.thumbnail(THUMB_SIZE)
            fake_output = io.BytesIO()
            image.save(fake_output, format='JPEG')
            return bytes(fake_output.getbuffer()), etag, last_modified

    def profile_image(self, user):
        cache = self.db.lookup(user)
        if cache is None:
            self.log.debug('image not in cache')
            image, etag, last_modified = self._fetch_profile_image(user)
            self.cache_profile_image(user, last_modified, etag, image)
            return image, etag, last_modified
        if cache['last_updated'] < (now() - self.cache_update_age):
            self.log.debug('image cache stale')
            image, etag, last_modified = self._fetch_profile_image(user)
            if etag == cache['etag']:
                last_modified = cache['last_modified']
                self.log.debug('image had not changed when refreshing cache')
            self.cache_profile_image(user, last_modified, etag, image)
            return image, etag, last_modified
        self.log.debug('image cache OK')
        return cache['image'], cache['etag'], cache['last_modified']

    def cache_profile_image(self, user, last_modified, etag, data):
        last_modified = last_modified.replace(microsecond=0)
        self.db.insert(user, now(), last_modified, etag, data)

    def get_user(self, feideid):
        person = self.ldap.lookup_feideid(feideid, PEOPLE_SEARCH_ATTRIBUTES)
        return self._format_person(person)
