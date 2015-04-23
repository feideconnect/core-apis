import unittest
import mock
from copy import deepcopy
from coreapis import apigkadm
from coreapis.utils import ValidationError
import py.test
from coreapis.apigkadm.tests.data import post_body_minimal, post_body_maximal


class TestValidation(unittest.TestCase):
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
