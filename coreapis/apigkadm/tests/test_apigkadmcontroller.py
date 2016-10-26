import unittest
import mock
import uuid
from copy import deepcopy
from coreapis import apigkadm
from coreapis.apigkadm import controller
from coreapis.utils import ValidationError
import py.test
from coreapis.apigkadm.tests.data import post_body_minimal, post_body_maximal, pre_update
from coreapis.clientadm.tests.helper import retrieved_user


class TestValidURL(unittest.TestCase):
    def test_validation(self):
        assert apigkadm.controller.valid_gk_url('https://example.org/abc') is True
        assert apigkadm.controller.valid_gk_url('https://example.org/abc/bar') is True
        assert apigkadm.controller.valid_gk_url('https://example.org/') is False
        assert apigkadm.controller.valid_gk_url('https://example.org') is True
        assert apigkadm.controller.valid_gk_url('https://example.org:8000') is True
        assert apigkadm.controller.valid_gk_url('http://example.org:8000') is False


class TestAPIGKAdmController(unittest.TestCase):
    @mock.patch('coreapis.apigkadm.controller.cassandra_client.Client')
    def setUp(self, Client):
        settings = {
            'cassandra_contact_points': [],
            'cassandra_keyspace': 'keyspace',
            'clientadm_maxrows': 100
        }
        self.controller = apigkadm.controller.APIGKAdmController(settings)

    def test_validation(self):
        self.controller.validate(post_body_maximal)
        self.controller.validate(post_body_minimal)
        testdata = deepcopy(post_body_minimal)
        testdata['id'] = 'ab1'
        self.controller.validate(testdata)
        testdata['id'] = 'ab1-12abc123'
        self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = 'a'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = '1ab'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = 'abcdefghijklmeno'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = '.'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = '/'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = ':'
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['id'] = 'ab1'
            testdata['created'] = 42
            self.controller.validate(testdata)
        with py.test.raises(ValidationError):
            testdata['endpoints'] = ['https://ugle.uninett.no/']
            self.controller.validate(testdata)

    def test_has_permission(self):
        assert self.controller.has_permission(pre_update, None, None) is False
        other_user = deepcopy(retrieved_user)
        other_user['userid'] = uuid.uuid4()
        assert self.controller.has_permission(pre_update, other_user, None) is False
        assert self.controller.has_permission(pre_update, retrieved_user, None) is True
        apigk = deepcopy(pre_update)
        apigk['organization'] = 'test:org'
        is_org_admin = mock.MagicMock()
        self.controller.is_org_admin = is_org_admin
        is_org_admin.return_value = False
        assert self.controller.has_permission(apigk, retrieved_user, None) is False
        is_org_admin.return_value = True
        assert self.controller.has_permission(apigk, retrieved_user, None) is True
        is_org_admin.return_value = False
        get_my_groupids = mock.MagicMock()
        self.controller.get_my_groupids = get_my_groupids
        get_my_groupids.return_value = ['a']
        apigk['admins'] = ['b']
        assert self.controller.has_permission(apigk, retrieved_user, 'token') is False
        apigk['admins'] = ['a']
        assert self.controller.has_permission(apigk, retrieved_user, 'token') is True
        del apigk['organization']
        assert self.controller.has_permission(apigk, other_user, 'token') is True
        apigk['admins'] = ['b']
        assert self.controller.has_permission(apigk, other_user, 'token') is False
