from pyramid.view import view_config
from pyramid.httpexceptions import HTTPForbidden


def configure(config):
    config.add_route('status', '/')
    config.scan(__name__)


@view_config(route_name='status', renderer='json')
def status(request):
    if not request.headers.get('X-dp-status-token', None) == request.registry.settings.status_token:
        raise HTTPForbidden('No access')
    return {
        'info': request.registry.settings.status_data,
        'components': {key: value()
                       for key, value in request.registry.settings.status_methods.items()},
    }
