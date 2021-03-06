from pyramid.view import view_config
from pyramid.httpexceptions import HTTPNotFound, HTTPUnauthorized
from coreapis.utils import get_user
from .controller import UserInfoController


def configure(config):
    userinfo_controller = UserInfoController(config.get_settings())
    config.add_settings(userinfo_controller=userinfo_controller)
    config.add_request_method(lambda r: r.registry.settings['userinfo_controller'],
                              'userinfo_controller', reify=True)
    config.add_route('get_userinfo_v1', '/v1/userinfo')
    config.add_route('get_userinfo_profilephoto_v1', '/v1/user/media/{userid_sec}')
    config.scan(__name__)


@view_config(route_name='get_userinfo_v1', request_method="GET",
             renderer="json")
def get_userinfo_v1(request):
    user = get_user(request)
    if not user:
        raise HTTPUnauthorized('No logged in user to return info about')
    try:
        return request.userinfo_controller.get_userinfo(user, request.has_permission)
    except (KeyError, RuntimeError):
        raise HTTPNotFound


@view_config(route_name='get_userinfo_profilephoto_v1', request_method="GET",
             renderer="logo")
def get_profilephoto_v1(request):
    use_default = request.params.get('usedefault', 'true').lower() != 'false'
    userid_sec = request.matchdict['userid_sec']
    try:
        profilephoto, updated = request.userinfo_controller.get_profilephoto(userid_sec)
        if profilephoto or use_default:
            return profilephoto, updated, 'data/default-profile.jpg', 'image/jpeg'
        else:
            raise HTTPNotFound
    except KeyError:
        raise HTTPNotFound
