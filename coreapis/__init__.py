from pyramid.config import Configurator
from .aaa import TokenAuthenticationPolicy, TokenAuthorizationPolicy


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    authn_policy = TokenAuthenticationPolicy()
    authz_policy = TokenAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    config.include('coreapis.views.configure', route_prefix='test')
    config.scan()
    return config.make_wsgi_app()
