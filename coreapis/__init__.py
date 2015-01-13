from pyramid.config import Configurator
import datetime
import uuid
import blist
import pyramid.renderers
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
    timer = Timer(global_config['statsd_server'], int(global_config['statsd_port']),
                  global_config['statsd_prefix'])
    config.add_settings(cassandra_contact_points=global_config['cassandra_contact_points'].split(', '))
    config.add_settings(cassandra_keyspace=global_config['cassandra_keyspace'])
    config.add_settings(timer=timer)
    if 'enabled_components' in settings:
        enabled_components = set(settings['enabled_components'].split(','))
        all_enabled = False
    else:
        all_enabled = True
        enabled_components = set()
    if all_enabled or 'testing' in enabled_components:
        config.include('coreapis.testing_views.configure', route_prefix='test')
    if all_enabled or 'peoplesearch' in enabled_components:
        config.include('coreapis.peoplesearch.views.configure', route_prefix='peoplesearch')
    config.scan('coreapis.error_views')
    config.add_settings(realm=global_config['oauth_realm'])
    config.add_tween('coreapis.utils.RequestTimingTween')
    json_renderer = pyramid.renderers.JSON()
    json_renderer.add_adapter(datetime.datetime, lambda x, y: x.isoformat())
    json_renderer.add_adapter(blist.sortedset, lambda x, y: list(x))
    json_renderer.add_adapter(uuid.UUID, lambda x, y: str(x))
    config.add_renderer('json', json_renderer)
    return config.make_wsgi_app()
