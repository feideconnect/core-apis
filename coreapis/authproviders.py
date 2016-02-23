from coreapis.utils import ValidationError


class IdportenProvider(object):
    provider_name = 'idporten'

    def __init__(self, session):
        self.session = session

    def check(self, client):
        clientid = client['id']
        orgid = client.get('organization')
        if not orgid:
            fmt = '{} requested by client {} and no organization'
            raise ValidationError(fmt.format(self.provider_name, clientid))
        try:
            org = self.session.get_org(orgid)
        except KeyError:
            raise ValidationError('No such organization: {}'.format(orgid))
        services = org.get('services')
        if self.provider_name not in services:
            fmt = 'Org {} not approved for {}, requested by client {}'
            raise ValidationError(fmt.format(orgid, self.provider_name, clientid))


class AuthProvidersManager(object):
    providers = {klass.provider_name: klass for klass in [IdportenProvider]}

    def __init__(self, session):
        self.session = session

    def handle_update(self, client):
        for provider_name in client.get('authproviders'):
            provider = self.providers.get(provider_name)
            if provider:
                provider(self.session).check(client)
