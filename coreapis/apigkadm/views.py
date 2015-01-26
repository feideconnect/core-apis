from pyramid.view import view_config
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotFound, HTTPConflict
from pyramid.response import Response
from .controller import APIGKAdmController
from coreapis.utils import AlreadyExistsError, get_userid
import json
import logging


def configure(config):
    contact_points = config.get_settings().get('cassandra_contact_points')
    keyspace = config.get_settings().get('cassandra_keyspace')
    maxrows = config.get_settings().get('apigkadm_maxrows')
    gkadm_controller = APIGKAdmController(contact_points, keyspace, maxrows)
    config.add_settings(gkadm_controller=gkadm_controller)
    config.add_request_method(lambda r: r.registry.settings.gkadm_controller, 'gkadm_controller',
                              reify=True)
    config.add_route('get_apigk', '/apigks/{id}', request_method='GET')
    config.add_route('list_apigks', '/apigks/', request_method='GET')
    config.add_route('add_apigk', '/apigks/', request_method='POST')
    config.add_route('delete_apigk', '/apigks/{id}', request_method='DELETE')
    config.add_route('update_apigk', '/apigks/{id}', request_method='PATCH')
    config.scan(__name__)


@view_config(route_name='list_apigks', renderer='json', permission='scope_apigkadmin')
def list_apigks(request):
    return request.gkadm_controller.list(request.params)


@view_config(route_name='get_apigk', renderer='json', permission='scope_apigkadmin')
def get_apigk(request):
    gkid = request.matchdict['id']
    try:
        apigk = request.gkadm_controller.get(gkid)
    except KeyError:
        raise HTTPNotFound()
    return apigk


@view_config(route_name='add_apigk', renderer='json', request_method='POST',
             permission='scope_apigkadmin')
def add_apigk(request):
    userid = get_userid(request)
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        apigk = request.gkadm_controller.add(payload, userid)
        request.response.status = 201
        request.response.location = "{}{}".format(request.url, apigk['id'])
        return apigk
    except AlreadyExistsError:
        raise HTTPConflict("apigk with this id already exists")


@view_config(route_name='delete_apigk', renderer='json', permission='scope_apigkadmin')
def delete_apigk(request):
    gkid = request.matchdict['id']
    try:
        request.gkadm_controller.delete(gkid)
        return Response(status=204,
                        content_type='application/json; charset={}'.format(request.charset))
    except ValueError:
        logging.exception("error during delete")
        raise HTTPBadRequest


@view_config(route_name='update_apigk', renderer='json', permission='scope_apigkadmin')
def update_apigk(request):
    gkid = request.matchdict['id']
    try:
        payload = json.loads(request.body.decode(request.charset))
    except:
        raise HTTPBadRequest
    try:
        apigk = request.gkadm_controller.update(gkid, payload)
        return apigk
    except KeyError:
        raise HTTPNotFound
    except:
        raise HTTPBadRequest
