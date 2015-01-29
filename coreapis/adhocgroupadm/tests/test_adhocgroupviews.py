import unittest
import mock
import uuid
from copy import deepcopy
from webtest import TestApp
from pyramid import testing
from coreapis import main, middleware
from coreapis.utils import parse_datetime, json_normalize
import py.test

post_body_minimal = {
    'name': 'per',
    'public': True,
}

post_body_maximal = {
    'name': 'per',
    'owner': '4f4e4b2b-bf7b-49f8-b703-cc6f4fc93493',
    'id': 'max-gk',
    'created': '2015-01-12T14:05:16+01:00', 'descr': 'green',
    'updated': '2015-01-12T14:05:16+01:00',
    'descr': 'new descr',
    'public': True,
}

user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
groupid1 = uuid.UUID("00000000-0000-0000-0001-000000000001")
group1 = {
    "updated": parse_datetime("2015-01-26T16:05:59Z"),
    "created": parse_datetime("2015-01-23T13:50:09Z"),
    "id": groupid1,
    "owner": user1,
    "name": "pre update",
    "descr": "some data",
    "public": False,
}


class AdHocGroupAdmTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        app = main({
            'statsd_server': 'localhost',
            'statsd_port': '8125',
            'statsd_prefix': 'feideconnect.tests',
            'oauth_realm': 'test realm',
            'cassandra_contact_points': '',
            'cassandra_keyspace': 'notused',
        }, enabled_components='adhocgroupadm', adhocgroupadm_maxrows=100)
        mw = middleware.MockAuthMiddleware(app, 'test realm')
        self.session = Client
        self.testapp = TestApp(mw)

    def tearDown(self):
        testing.tearDown()

    def test_get_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = group1
        res = self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=200, headers=headers)
        assert res.json == json_normalize(group1)

    def test_missing_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.side_effect = KeyError()
        self.testapp.get('/adhocgroups/{}'.format(uuid.uuid4()), status=404, headers=headers)

    def test_list_groups(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_groups.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/adhocgroups/', status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_list_groups_by_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_groups.return_value = [{'foo': 'bar'}]
        res = self.testapp.get('/adhocgroups/?owner={}'.format('00000000-0000-0000-0000-000000000001'),
                               status=200, headers=headers)
        out = res.json
        assert 'foo' in out[0]

    def test_post_group_minimal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group = mock.MagicMock(side_effect=KeyError)
        res = self.testapp.post_json('/adhocgroups/', post_body_minimal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_group_maximal(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.side_effect = KeyError()
        res = self.testapp.post_json('/adhocgroups/', post_body_maximal, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_group_missing_name(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body.pop('name')
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_invalid_json(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = 'foo'
        self.testapp.post('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_other_user(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['owner'] = 'owner'
        self.session().insert_group = mock.MagicMock()
        self.session().get_group.side_effect = KeyError()
        res = self.testapp.post_json('/adhocgroups/', body, status=201, headers=headers)
        out = res.json
        assert out['owner'] == '00000000-0000-0000-0000-000000000001'

    def test_post_group_invalid_text(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['descr'] = 42
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_invalid_text_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = [42]
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_invalid_list(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['redirect_uri'] = 'http://www.vg.no'
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_post_group_unknown_attr(self):
        headers = {'Authorization': 'Bearer user_token'}
        body = deepcopy(post_body_minimal)
        body['foo'] = 'bar'
        self.session().insert_group = mock.MagicMock()
        self.testapp.post_json('/adhocgroups/', body, status=400, headers=headers)

    def test_delete_group(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = {'owner': uuid.UUID('00000000-0000-0000-0000-000000000001')}
        self.testapp.delete('/adhocgroups/{}'.format(uuid.uuid4()), status=204, headers=headers)

    def test_delete_group_no_id(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.testapp.delete('/adhocgroups/', status=404, headers=headers)

    def test_update_no_change(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        res = self.testapp.patch_json('/adhocgroups/updatable', {}, status=200, headers=headers)
        updated = res.json
        expected = json_normalize(group1)
        assert updated['updated'] > expected['updated']
        del updated['updated']
        del expected['updated']
        assert updated == expected

    def test_update_invalid_request(self):
        headers = {'Authorization': 'Bearer user_token'}
        self.session().get_group.return_value = deepcopy(group1)
        self.testapp.patch('/adhocgroups/updatable', '{', status=400, headers=headers)
        self.testapp.patch_json('/adhocgroups/updatable', {'endpoints': 'file:///etc/shadow'},
                                status=400, headers=headers)

    def test_update_not_owner(self):
        headers = {'Authorization': 'Bearer user_token'}
        to_update = deepcopy(group1)
        to_update['owner'] = uuid.uuid4()
        self.session().get_group.return_value = to_update
        self.testapp.patch_json('/adhocgroups/updatable', {},
                                status=401, headers=headers)
