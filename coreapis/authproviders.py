from coreapis import feide
from coreapis.utils import ValidationError

REGISTER_APIGK = 'register_apigk'
REGISTER_CLIENT = 'register_client'


class FeideProvider(object):
    provider_name = 'feide'
    ops_supported = [REGISTER_APIGK, REGISTER_CLIENT]
    special_realms = {feide.TEST_REALM, feide.GUEST_USER_REALM}

    def has_user_permission(self, user_key, operation):
        if operation not in self.ops_supported:
            return False
        else:
            _, _, realm = user_key.partition('@')
            return realm not in self.special_realms

    def check_client_update(self, session, client):
        pass


class IdportenProvider(object):
    provider_name = 'idporten'

    def has_user_permission(self, user, operation):
        return False

    def check_client_update(self, session, client):
        clientid = client['id']
        orgid = client.get('organization')
        if not orgid:
            fmt = '{} requested by client {} and no organization'
            raise ValidationError(fmt.format(self.provider_name, clientid))
        try:
            org = session.get_org(orgid)
        except KeyError:
            raise ValidationError('No such organization: {}'.format(orgid))
        services = org.get('services', [])
        if self.provider_name not in services:
            fmt = 'Org {} not approved for {}, requested by client {}'
            raise ValidationError(fmt.format(orgid, self.provider_name, clientid))


class AuthProvidersManager(object):
    providers = {klass.provider_name: klass
                 for klass in [FeideProvider, IdportenProvider]}

    def _has_identity_permission(self, identity, operation):
        provider_name, _, user_key = identity.partition(':')
        provider = self.providers.get(provider_name)
        if provider:
            return provider().has_user_permission(user_key, operation)
        else:
            return False

    # True if user - not acting in the capacity of an org admin - has
    # permission to perform operation
    def has_user_permission(self, user, operation):
        return any(self._has_identity_permission(identity, operation)
                   for identity in user['userid_sec'])

    # For certain authentication providers, there are additional constraints
    # that must be satisfied when inserting/updating a client.
    # This method raises an exception if any constraint is not met.
    def check_client_update(self, session, client):
        for provider_name in client.get('authproviders', []):
            provider = self.providers.get(provider_name)
            if provider:
                provider().check_client_update(session, client)


authprovmgr = AuthProvidersManager()
