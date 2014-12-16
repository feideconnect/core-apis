from pyramid.config import Configurator
from .aaa import TokenAuthenticationPolicy, TokenAuthorizationPolicy
from .utils import Timer


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
    timer = Timer(global_config['statsd_server'], int(global_config['statsd_port']),
                  global_config['statsd_prefix'])
    config.add_settings(timer=timer)
    config.add_tween('coreapis.utils.RequestTimingTween')
    return config.make_wsgi_app()
