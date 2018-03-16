import datetime
import os
import socket
import uuid

import blist
from eventlet.pools import Pool as EventletPool
import eventlet.green.threading
from pyramid.config import Configurator
import pyramid.renderers
import cassandra.util
import statsd

from .aaa import TokenAuthenticationPolicy, TokenAuthorizationPolicy
import coreapis.utils
from .utils import Timer, format_datetime, ResourcePool, LogWrapper, get_cassandra_authz


def options(request):
    resp = pyramid.response.Response('')
    return resp


def make_statsd_hostid():
    if 'DOCKER_HOST' in os.environ and 'DOCKER_INSTANCE' in os.environ:
        return '{}.{}'.format(os.environ['DOCKER_HOST'].replace('.', '_'),
                                os.environ['DOCKER_INSTANCE'])
    else:
        return socket.getfqdn().replace('.', '_')


def set_status_data_docker(status_data):
    docker_env = {x.lower(): y for x, y in os.environ.items() if x.startswith("DOCKER_")}
    if docker_env:
        LogWrapper.add_defaults(**docker_env)
        status_data.update(docker_env)

def set_status_data_build(status_data):
    for var in 'GIT_COMMIT', 'JENKINS_BUILD_NUMBER':
        if var in os.environ:
            status_data[var] = os.environ[var]


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
        coreapis.utils.__local = eventlet.green.threading.local()
    else:
        pool = ResourcePool
    log_timings = global_config.get('log_timings', 'false').lower() == 'true'

    statsd_server = global_config['statsd_server']
    statsd_port = int(global_config['statsd_port'])
    statsd_prefix = global_config['statsd_prefix']
    timer = Timer(statsd_server, statsd_port,
                  statsd_prefix, log_timings, pool)
    config.add_settings(statsd_factory=lambda: statsd.StatsClient(statsd_server, statsd_port,
                                                                  prefix=statsd_prefix))
    config.add_renderer('logo', 'coreapis.utils.LogoRenderer')
    contact_points = global_config['cassandra_contact_points'].split(', ')
    config.add_settings(cassandra_contact_points=contact_points)
    config.add_settings(cassandra_keyspace=global_config['cassandra_keyspace'])
    config.add_settings(cassandra_authz=get_cassandra_authz(global_config))
    config.add_settings(timer=timer)
    config.add_settings(log_timings=log_timings)

    statsd_host_prefix = "{}.{}".format(statsd_prefix, make_statsd_hostid())
    config.add_settings(statsd_host_factory=lambda: statsd.StatsClient(statsd_server, statsd_port,
                                                                       prefix=statsd_host_prefix))
    config.add_settings(status_data=dict(), status_methods=dict())

    config.add_route('pre_flight', pattern='/*path', request_method='OPTIONS')
    config.add_view(options, route_name='pre_flight')
    if 'enabled_components' in settings:
        enabled_components = set(settings['enabled_components'].split(','))
        all_enabled = False
    else:
        all_enabled = True
        enabled_components = set()
    main_component = settings.get('main_component', None)

    components = ['status', 'peoplesearch', 'clientadm', 'apigkadm', 'gk', 'authorizations',
                  'adhocgroups', 'groups', 'orgs', 'userinfo', 'statistics', 'orgpersons']
    log = LogWrapper('main')
    for component in components:
        if all_enabled or component in enabled_components:
            if component == main_component:
                prefix = ''
            else:
                prefix = component
            log.info("Enabling component", component=component, route_prefix=prefix)
            config.include('coreapis.{}.views.configure'.format(component), route_prefix=prefix)
    config.scan('coreapis.error_views')
    config.add_settings(realm=global_config['oauth_realm'])
    config.add_tween('coreapis.utils.RequestTimingTween')
    json_renderer = pyramid.renderers.JSON(indent=4)
    json_renderer.add_adapter(datetime.datetime, lambda x, y: format_datetime(x))
    json_renderer.add_adapter(blist.sortedset, lambda x, y: list(x))
    json_renderer.add_adapter(uuid.UUID, lambda x, y: str(x))
    json_renderer.add_adapter(cassandra.util.SortedSet, lambda x, y: list(x))
    config.add_renderer('json', json_renderer)
    status_data = config.get_settings().status_data
    set_status_data_docker(status_data)
    set_status_data_build(status_data)
    return config.make_wsgi_app()
