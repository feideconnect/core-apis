from pyramid.view import view_config
from pyramid.exceptions import HTTPNotFound
from pyramid.response import Response
import logging
import ldap3
import json
from coreapis.utils import ValidationError
from PIL import Image
import io
import base64
from .tokens import crypt_token, decrypt_token

THUMB_SIZE = 128, 128


def configure(config):
    config.add_settings(profile_image_key=
                        base64.b64decode(config.get_settings().get('profile_token_secret')))
    config.add_route('person_search', '/search/{org}/{name}')
    config.add_route('list_realms', '/orgs')
    config.add_route('profile_photo', '/people/profilephoto/{token}')


def get_ldap_config():
    return json.load(open('ldap-config.json'))


def get_connection(org):
    conf = get_ldap_config()
    orgconf = conf[org]
    server_pool = ldap3.ServerPool(None, ldap3.POOLING_STRATEGY_ROUND_ROBIN, active=True)
    for server in orgconf['servers']:
        if ':' in server:
            host, port = server.split(':', 1)
            port = int(port)
        else:
            host, port = server, None
        server = ldap3.Server(host, port=port, use_ssl=True)
        server_pool.add(server)
    if 'bind_user' in orgconf:
        user = orgconf['bind_user']['dn']
        password = orgconf['bind_user']['password']
    else:
        user = None
        password = None
    con = ldap3.Connection(server_pool, auto_bind=True,
                           user=user, password=password,
                           client_strategy=ldap3.STRATEGY_SYNC,
                           check_names=True)
    return con


def get_base_dn(org):
    return get_ldap_config()[org]['base_dn']


def handle_exclude(org, search):
    exclude_filter = get_ldap_config()[org].get('exclude', None)
    if exclude_filter:
        search = "(&{}(!{}))".format(search, exclude_filter)
    return search


def flatten(user, attributes):
    for attr in attributes:
        if attr in user:
            user[attr] = user[attr][0]


def validate_query(string):
    for char in ('(', ')', '*', '\\'):
        if char in string:
            raise ValidationError('Bad character in request')


@view_config(route_name='person_search', renderer='json', permission='scope_personsearch')
def person_search(request):
    org = request.matchdict['org']
    search = request.matchdict['name']
    key = request.registry.settings.profile_image_key
    validate_query(search)
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if org not in get_ldap_config().keys():
        raise HTTPNotFound('Unknown org')
    t = request.registry.settings.timer
    with t.time('ps.ldap_connect'):
        con = get_connection(org)
    base_dn = get_base_dn(org)
    search_filter = '(cn=*{}*)'.format(search)
    search_filter = handle_exclude(org, search_filter)
    attrs = ['cn', 'displayName', 'mail', 'mobile', 'eduPersonPrincipalName']
    with t.time('ps.ldap_search'):
        con.search(base_dn, search_filter, ldap3.SEARCH_SCOPE_WHOLE_SUBTREE, attributes=attrs)
    res = con.response
    with t.time('ps.process_results'):
        result = [dict(r['attributes']) for r in res]
        for person in result:
            flatten(person, ('cn', 'displayName', 'eduPersonPrincipalName'))
        for person in result:
            if 'eduPersonPrincipalName' in person:
                feideid = person['eduPersonPrincipalName']
                del person['eduPersonPrincipalName']
                person['id'] = 'feide:' + feideid
                person['profile_image_token'] = crypt_token(person['id'], key)
    return result


@view_config(route_name='list_realms', renderer='json', permission='scope_personsearch')
def list_realms(request):
    conf = get_ldap_config()
    return {realm: data['display'] for realm, data in conf.items()}


@view_config(route_name='profile_photo')
def profilephoto(request):
    token = request.matchdict['token']
    key = request.registry.settings.profile_image_key
    user = decrypt_token(token, key)
    if not ':' in user:
        raise ValidationError('user id must contain ":"')
    idtype, user = user.split(':', 1)
    if idtype == 'feide':
        if not '@' in user:
            raise ValidationError('feide id must contain @')
        _, realm = user.split('@', 1)
        con = get_connection(realm)
        validate_query(user)
        base_dn = get_base_dn(realm)
        search_filter = '(eduPersonPrincipalName={})'.format(user)
        search_filter = handle_exclude(realm, search_filter)  # Is this needed here?
        con.search(base_dn, search_filter, ldap3.SEARCH_SCOPE_WHOLE_SUBTREE,
                   attributes=['jpegPhoto'])
        res = con.response
        if len(res) == 0:
            logging.debug('Could not find user for %s', user)
            raise HTTPNotFound()
        if len(res) > 1:
            logging.warning('Multiple matches to eduPersonPrincipalName')
        attributes = res[0]['attributes']
        if not 'jpegPhoto' in attributes:
            logging.debug('User %s has not jpegPhoto', user)
            raise HTTPNotFound()
        data = attributes['jpegPhoto'][0]
        fake_file = io.BytesIO(data)
        image = Image.open(fake_file)
        image.thumbnail(THUMB_SIZE)
        fake_output = io.BytesIO()
        image.save(fake_output, format='JPEG')
        logging.debug('image is %d bytes', len(fake_output.getbuffer()))
        response = Response(fake_output.getbuffer(), charset=None)
        response.content_type = 'image/jpeg'
        return response
    else:
        raise ValidationError("Unhandled user id type '{}'".format(idtype))
