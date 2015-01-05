from pyramid.view import view_config
from pyramid.exceptions import HTTPNotFound
import logging
import ldap3


def configure(config):
    config.add_route('person_search', '/search/{org}/{name}')


def get_connection(org):
    server = ldap3.Server('ldap.uninett.no', use_ssl=True)
    con = ldap3.Connection(server, auto_bind=True,
                           client_strategy=ldap3.STRATEGY_SYNC,
                           check_names=True)
    return con


def get_base_dn(org):
    return 'cn=people,dc=uninett,dc=no'


@view_config(route_name='person_search', renderer='json', permission='scope_personsearch')
def person_search(request):
    org = request.matchdict['org']
    search = request.matchdict['name']
    if not org or not search:
        raise HTTPNotFound('missing org or search term')
    if org != 'uninett':
        raise HTTPNotFound('Unknown org')
    con = get_connection(org)
    base_dn = get_base_dn(org)
    search_filter = '(cn=*{}*)'.format(search)
    attrs = ['cn', 'displayName', 'mail', 'mobile']
    con.search(base_dn, search_filter, ldap3.SEARCH_SCOPE_WHOLE_SUBTREE, attributes=attrs)
    res = con.response
    return [dict(r['attributes']) for r in res]
