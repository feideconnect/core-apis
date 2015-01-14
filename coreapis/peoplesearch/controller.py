import datetime
import pytz
import json
import ldap3
import hashlib
from coreapis.utils import ValidationError, LogWrapper, now
from .tokens import crypt_token, decrypt_token
from PIL import Image
import io
from cassandra.cluster import Cluster
from cassandra.query import dict_factory

THUMB_SIZE = 128, 128


def flatten(user, attributes):
    for attr in attributes:
        if attr in user:
            user[attr] = user[attr][0]


def validate_query(string):
    for char in ('(', ')', '*', '\\'):
        if char in string:
            raise ValidationError('Bad character in request')


def make_etag(data):
    m = hashlib.md5()
    m.update(data)
    return m.hexdigest()


class LDAPController(object):
    def __init__(self, timer):
        self.t = timer
        self.config = json.load(open('ldap-config.json'))
        self.log = LogWrapper('peoplesearch.LDAPController')
        self.servers = {}
        for org in self.config:
            orgconf = self.config[org]
            server_pool = ldap3.ServerPool(None, ldap3.POOLING_STRATEGY_ROUND_ROBIN, active=True)
            for server in orgconf['servers']:
                if ':' in server:
                    host, port = server.split(':', 1)
                    port = int(port)
                else:
                    host, port = server, None
                server = ldap3.Server(host, port=port, use_ssl=True)
                server_pool.add(server)
            self.servers[org] = server_pool

    def get_ldap_config(self):
        return self.config

    def get_connection(self, org):
        orgconf = self.config[org]
        if 'bind_user' in orgconf:
            user = orgconf['bind_user']['dn']
            password = orgconf['bind_user']['password']
        else:
            user = None
            password = None
        con = ldap3.Connection(self.servers[org], auto_bind=True,
                               user=user, password=password,
                               client_strategy=ldap3.STRATEGY_SYNC,
                               check_names=True)
        return con

    def get_base_dn(self, org):
        return self.get_ldap_config()[org]['base_dn']

    def handle_exclude(self, org, search):
        exclude_filter = self.get_ldap_config()[org].get('exclude', None)
        if exclude_filter:
            search = "(&{}(!{}))".format(search, exclude_filter)
        return search

    def ldap_search(self, org, search_filter, scope, attributes):
        with self.t.time('ps.ldap_connect'):
            con = self.get_connection(org)
        search_filter = self.handle_exclude(org, search_filter)
        with self.t.time('ps.ldap_search'):
            con.search(self.get_base_dn(org), search_filter, scope, attributes=attributes)
        return con.response


class CassandraCache(object):
    def __init__(self, contact_points, keyspace):
        cluster = Cluster(
            contact_points=contact_points
        )
        self.session = cluster.connect(keyspace)
        self.session.row_factory = dict_factory
        self.s_lookup = self.session.prepare('SELECT * from profile_image_cache where user=?')
        self.s_insert = self.session.prepare('UPDATE profile_image_cache set last_modified=?, etag=?, last_updated=?, image=? WHERE user=?')

    def lookup(self, user):
        res = self.session.execute(self.s_lookup.bind([user]))
        if len(res) == 0:
            return None
        entry = res[0]
        for key, value in entry.items():
            if isinstance(value, datetime.datetime):
                entry[key] = value.replace(tzinfo=pytz.UTC)
        return entry

    def insert(self, user, last_updated, last_modified, etag, image):
        self.session.execute(self.s_insert.bind([last_modified, etag, last_updated, image, user]))


class PeopleSearchController(object):

    def __init__(self, key, timer, ldap_controller, contact_points, cache_keyspace,
                 cache_update_seconds):
        self.key = key
        self.t = timer
        self.ldap = ldap_controller
        self.image_cache = dict()
        self.log = LogWrapper('peoplesearch.PeopleSearchController')
        self.db = CassandraCache(contact_points, cache_keyspace)
        self.cache_update_age = datetime.timedelta(seconds=cache_update_seconds)

    def valid_org(self, org):
        return org in self.ldap.get_ldap_config()

    def orgs(self):
        conf = self.ldap.get_ldap_config()
        return {realm: data['display'] for realm, data in conf.items()}

    def search(self, org, query):
        validate_query(query)
        search_filter = '(&(cn=*{}*)(objectClass=norEduPerson))'.format(query)
        attrs = ['cn', 'displayName', 'eduPersonPrincipalName']
        res = self.ldap.ldap_search(org, search_filter, ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                                    attributes=attrs)
        with self.t.time('ps.process_results'):
            result = [dict(r['attributes']) for r in res]
            for person in result:
                flatten(person, ('cn', 'displayName', 'eduPersonPrincipalName'))
            new_result = []
            for person in result:
                new_person = {}
                if 'eduPersonPrincipalName' in person:
                    feideid = person['eduPersonPrincipalName']
                    person['id'] = 'feide:' + feideid
                    new_person['profile_image_token'] = crypt_token(person['id'], self.key)
                if 'displayName' in person:
                    new_person['name'] = person['displayName']
                elif 'cn' in person:
                    new_person['name'] = person['cn']
                new_result.append(new_person)
            return new_result

    def _profile_image_feide(self, user):
        if not '@' in user:
            raise ValidationError('feide id must contain @')
        _, realm = user.split('@', 1)
        validate_query(user)
        search_filter = '(eduPersonPrincipalName={})'.format(user)
        res = self.ldap.ldap_search(realm, search_filter,
                                    ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                                    attributes=['jpegPhoto'])
        if len(res) == 0:
            self.log.debug('Could not find user for %s' % user)
            return None, None, None
        if len(res) > 1:
            self.log.warn('Multiple matches to eduPersonPrincipalName')
        attributes = res[0]['attributes']
        if not 'jpegPhoto' in attributes:
            self.log.debug('User %s has not jpegPhoto' % user)
            return None, None, None
        data = attributes['jpegPhoto'][0]
        return data, make_etag(data), now()

    def decrypt_profile_image_token(self, token):
        return decrypt_token(token, self.key)

    def _fetch_profile_image(self, user):
        if not ':' in user:
            raise ValidationError('user id must contain ":"')
        idtype, user = user.split(':', 1)
        if idtype == 'feide':
            data, etag, last_modified = self._profile_image_feide(user)
        else:
            raise ValidationError("Unhandled user id type '{}'".format(idtype))
        if data is None:
            return None, None, None
        with self.t.time('ps.profileimage.scale'):
            fake_file = io.BytesIO(data)
            image = Image.open(fake_file)
            image.thumbnail(THUMB_SIZE)
            fake_output = io.BytesIO()
            image.save(fake_output, format='JPEG')
            return fake_output.getbuffer(), etag, last_modified

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
