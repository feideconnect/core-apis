from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound
from .controller import UserInfoController
from coreapis.utils import get_user


def configure(config):
    userinfo_controller = UserInfoController(config.get_settings())
    config.add_settings(userinfo_controller=userinfo_controller)
    config.add_request_method(lambda r: r.registry.settings.userinfo_controller,
                              'userinfo_controller', reify=True)
    config.add_route('get_userinfo', '/userinfo')
    config.add_route('get_userinfo_profilephoto', '/user/media/{userid_sec}')
    config.scan(__name__)


@view_config(route_name='get_userinfo', request_method="GET",
             permission='scope_userinfo', renderer="json")
def get_userinfo(request):
    user = get_user(request)
    return request.userinfo_controller.get_userinfo(user, request.has_permission)


@view_config(route_name='get_userinfo_profilephoto', request_method="GET",
             renderer="logo")
def get_profilephoto(request):
    try:
        profilephoto, updated = request.userinfo_controller.get_profilephoto(request.matchdict['userid_sec'])
        return profilephoto, updated, 'data/default-profile.jpg', 'image/jpeg'
    except KeyError:
        raise HTTPNotFound
