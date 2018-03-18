import ssl

import ldap3

import coreapis.ldap


def ldap_exception_argument(ex):
    if isinstance(ex.args[0], Exception):
        return ldap_exception_argument(ex.args[0])
    return ex.args[0]


def check_object(con, dn, objtype, needed_attributes):
    errors = []
    con.search(dn, '(objectClass=*)', ldap3.BASE,
               attributes=list(needed_attributes), size_limit=1)
    if len(con.response) == 0:
        errors.append("Could not lookup {} {}".format(objtype, dn))
    else:
        orgattributes = con.response[0]['attributes']
        for attribute in needed_attributes:
            if attribute not in orgattributes:
                errors.append("Attribute {} missing on {} {}".format(attribute, objtype, dn))
    return errors


def check_attributes(connection):
    attributes = connection.response[0]['attributes']
    errors = []
    for attribute in coreapis.ldap.REQUIRED_PERSON_ATTRIBUTES:
        if attribute not in attributes:
            errors.append('Attribute {} missing on person'.format(attribute))
    if 'eduPersonOrgDN' in attributes:
        orgDN = coreapis.ldap.get_single(attributes['eduPersonOrgDN'])
        errors.extend(check_object(connection, orgDN, 'organization',
                                   coreapis.ldap.REQUIRED_ORG_ATTRIBUTES))
    if 'eduPersonOrgUnitDN' in attributes:
        orgUnitDN = attributes['eduPersonOrgUnitDN'][0]
        errors.extend(check_object(connection, orgUnitDN, 'organizational unit',
                                   coreapis.ldap.REQUIRED_ORG_UNIT_ATTRIBUTES))
    return errors


def get_search_status(connection):
    if len(connection.response) == 0:
        return {
            'result': 'empty response looking up feideid',
        }
    errors = check_attributes(connection)
    if errors:
        return {
            'result': 'Data Error',
            'message': "\n".join(errors),
        }
    else:
        return {
            'result': 'success',
        }


def record_ldap_exception(ex, result, message):
    status = {
        'result': result,
        'class': ex.__class__.__name__,
        'message': message,
    }
    if len(ex.args) > 1 and isinstance(ex.args[1], list) and len(ex.args[1][0]) > 2:
        status['details'] = ex.args[1][0][2].args[0]
    return status


def record_exception(ex):
    message = 'Unknown error'
    if len(ex.args) > 0:
        message = ex.args[0]
    status = {
        'result': 'other error',
        'class': ex.__class__.__name__,
        'message': message,
    }
    return status


def server_status(server, base_dn, search_filter, user, password, tls):
    if ':' in server:
        host, port = server.split(':', 1)
        port = int(port)
    else:
        host, port = server, None
    ldapserver = ldap3.Server(host, port=port, use_ssl=True, connect_timeout=1, tls=tls)

    try:
        con = ldap3.Connection(ldapserver, auto_bind=True,
                               user=user, password=password,
                               client_strategy=ldap3.SYNC,
                               return_empty_attributes=False,
                               check_names=True)
        con.search(base_dn, search_filter, ldap3.SUBTREE,
                   attributes=coreapis.ldap.REQUIRED_PERSON_ATTRIBUTES, size_limit=1)
        status = get_search_status(con)
    except ldap3.core.exceptions.LDAPCommunicationError as ex:
        status = record_ldap_exception(ex, 'Communications Error', ldap_exception_argument(ex))
    except ldap3.core.exceptions.LDAPBindError as ex:
        status = record_ldap_exception(ex, 'bind_error', ex.args[0])
    except Exception as ex:
        status = record_exception(ex)
    return status

def ldap_status(realm, feideid, ldap_config, ldap_certs):

    if not realm or realm not in ldap_config:
        return {'error': 'Missing configuration for realm {}'.format(realm)}
    orgconfig = ldap_config[realm]

    status = {}
    base_dn = orgconfig['base_dn']
    search_filter = '(eduPersonPrincipalName={})'.format(feideid)
    tls = ldap3.Tls(validate=ssl.CERT_REQUIRED,
                    ca_certs_file=ldap_certs)
    if 'bind_user' in orgconfig:
        user = orgconfig['bind_user']['dn']
        password = orgconfig['bind_user']['password']
    else:
        user = None
        password = None
    for server in orgconfig['servers']:
        status[server] = server_status(server, base_dn, search_filter, user, password, tls)
    return status
