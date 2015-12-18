import datetime
import uuid

import blist
from eventlet.pools import Pool as EventletPool
from pyramid.config import Configurator
import pyramid.renderers

from .aaa import TokenAuthenticationPolicy, TokenAuthorizationPolicy
from .utils import Timer, format_datetime, ResourcePool


def options(request):
    resp = pyramid.response.Response('')
    return resp


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    authn_policy = TokenAuthenticationPolicy()
    authz_policy = TokenAuthorizationPolicy()
    config.set_authentication_policy(authn_policy)
    config.set_authorization_policy(authz_policy)
    if global_config.get('use_eventlets', '') == 'true':
        pool = EventletPool
    else:
        pool = ResourcePool
    log_timings = global_config.get('log_timings', 'false').lower() == 'true'

    timer = Timer(global_config['statsd_server'], int(global_config['statsd_port']),
                  global_config['statsd_prefix'], log_timings, pool)
    config.add_renderer('logo', 'coreapis.utils.LogoRenderer')
    config.add_settings(cassandra_contact_points=global_config['cassandra_contact_points'].split(', '))
    config.add_settings(cassandra_keyspace=global_config['cassandra_keyspace'])
    config.add_settings(timer=timer)
    config.add_settings(log_timings=log_timings)
    config.add_route('pre_flight', pattern='/*path', request_method='OPTIONS')
    config.add_view(options, route_name='pre_flight')
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
    if all_enabled or 'clientadm' in enabled_components:
        config.include('coreapis.clientadm.views.configure', route_prefix='clientadm')
    if all_enabled or 'apigkadm' in enabled_components:
        config.include('coreapis.apigkadm.views.configure', route_prefix='apigkadm')
    if all_enabled or 'gk' in enabled_components:
        config.include('coreapis.gk.views.configure', route_prefix='gk')
    if all_enabled or 'authorizations' in enabled_components:
        config.include('coreapis.authorizations.views.configure', route_prefix='authorizations')
    if all_enabled or 'adhocgroupadm' in enabled_components:
        config.include('coreapis.adhocgroupadm.views.configure', route_prefix='adhocgroups')
    if all_enabled or 'groups' in enabled_components:
        config.include('coreapis.groups.views.configure', route_prefix='groups')
    if all_enabled or 'org' in enabled_components:
        config.include('coreapis.org.views.configure', route_prefix='orgs')
    if all_enabled or 'userinfo' in enabled_components:
        config.include('coreapis.userinfo.views.configure', route_prefix='userinfo')
    config.scan('coreapis.error_views')
    config.add_settings(realm=global_config['oauth_realm'])
    config.add_tween('coreapis.utils.RequestTimingTween')
    json_renderer = pyramid.renderers.JSON(indent=4)
    json_renderer.add_adapter(datetime.datetime, lambda x, y: format_datetime(x))
    json_renderer.add_adapter(blist.sortedset, lambda x, y: list(x))
    json_renderer.add_adapter(uuid.UUID, lambda x, y: str(x))
    config.add_renderer('json', json_renderer)
    return config.make_wsgi_app()
