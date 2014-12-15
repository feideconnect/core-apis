from pyramid.config import Configurator


def main(global_config, **settings):
    """ This function returns a Pyramid WSGI application.
    """
    config = Configurator(settings=settings)
    config.include('coreapis.views.configure', route_prefix='test')
    config.scan()
    return config.make_wsgi_app()
