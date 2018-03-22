from pyramid.view import view_config

from .controller import StatisticsController


def configure(config):
    stats_controller = StatisticsController(config.get_settings())
    config.add_settings(stats_controller=stats_controller)
    config.add_request_method(lambda r: r.registry.settings.stats_controller, 'stats_controller',
                              reify=True)
    config.add_route('statistics', '/{date}/{metric:[^/]*}')
    config.scan(__name__)


@view_config(route_name='statistics', renderer='json', permission="scope_orgadmin")
def get_statistics(request):
    return request.stats_controller.get_statistics(request.matchdict['date'],
                                                   request.matchdict['metric'])
