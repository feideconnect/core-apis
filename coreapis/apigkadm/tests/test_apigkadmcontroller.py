import unittest
import mock
import uuid
from copy import deepcopy
from coreapis import apigkadm
from coreapis.utils import ValidationError
import py.test
from coreapis.apigkadm.tests.data import post_body_minimal, post_body_maximal, pre_update
from coreapis.clientadm.tests.helper import retrieved_user


class TestAPIGKAdmController(unittest.TestCase):
    @mock.patch('coreapis.apigkadm.controller.cassandra_client.Client')
    def setUp(self, Client):
        self.controller = apigkadm.controller.APIGKAdmController([], '', 20)

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

    def test_has_permission(self):
        assert self.controller.has_permission(pre_update, None) is False
        other_user = deepcopy(retrieved_user)
        other_user['userid'] = uuid.uuid4()
        assert self.controller.has_permission(pre_update, other_user) is False
        assert self.controller.has_permission(pre_update, retrieved_user) is True
        apigk = deepcopy(pre_update)
        apigk['organization'] = 'test:org'
        is_org_admin = mock.MagicMock()
        self.controller.is_org_admin = is_org_admin
        is_org_admin.return_value = False
        assert self.controller.has_permission(apigk, retrieved_user) is False
        is_org_admin.return_value = True
        assert self.controller.has_permission(apigk, retrieved_user) is True
