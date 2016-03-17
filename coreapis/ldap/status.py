import ssl

import ldap3


def ldap_exception_argument(ex):
    if isinstance(ex.args[0], Exception):
        return ldap_exception_argument(ex.args[0])
    return ex.args[0]


def ldap_status(realm, feideid, ldap_config, ldap_certs):

    if not realm or realm not in ldap_config:
        return {'error': 'Missing configuration for realm {}'.format(realm)}
    orgconfig = ldap_config[realm]

    status = {}
    base_dn = orgconfig['base_dn']
    search_filter = '(eduPersonPrincipalName={})'.format(feideid)
    attributes = ['eduPersonPrincipalName', 'eduPersonOrgDN']
    tls = ldap3.Tls(validate=ssl.CERT_REQUIRED,
                    ca_certs_file=ldap_certs)
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
