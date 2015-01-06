from pyramid.view import view_config
from pyramid.exceptions import HTTPNotFound
import logging
import ldap3
import json
from .utils import ValidationError


def configure(config):
    config.add_route('person_search', '/search/{org}/{name}')
    config.add_route('list_realms', '/orgs')


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
    validate_query(search)
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if org not in get_ldap_config().keys():
        raise HTTPNotFound('Unknown org')
    con = get_connection(org)
    base_dn = get_base_dn(org)
    search_filter = '(cn=*{}*)'.format(search)
    search_filter = handle_exclude(org, search_filter)
    attrs = ['cn', 'displayName', 'mail', 'mobile', 'eduPersonPrincipalName']
    con.search(base_dn, search_filter, ldap3.SEARCH_SCOPE_WHOLE_SUBTREE, attributes=attrs)
    res = con.response
    result = [dict(r['attributes']) for r in res]
    for person in result:
        flatten(person, ('cn', 'displayName', 'eduPersonPrincipalName'))
    for person in result:
        if 'eduPersonPrincipalName' in person:
            feideid = person['eduPersonPrincipalName']
            del person['eduPersonPrincipalName']
            person['id'] = 'feide:' + feideid
    return result


@view_config(route_name='list_realms', renderer='json', permission='scope_personsearch')
def list_realms(request):
    conf = get_ldap_config()
    return {realm: data['display'] for realm, data in conf.items()}
