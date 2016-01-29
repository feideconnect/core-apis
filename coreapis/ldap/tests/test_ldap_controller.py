from unittest import TestCase

import mock
import pytest

from coreapis.ldap import controller
from coreapis.utils import ValidationError


class TestLookupFeideid(TestCase):
    def setUp(self):
        m = mock.mock_open(read_data='{}')
        settings = {
            'timer': mock.MagicMock(),
            'ldap_config_file': 'testdata/test-ldap-config.json',
            'statsd_factory': mock.MagicMock(),
        }
        self.ldap = controller.LDAPController(settings)

    def test_feide_multiple_users(self):
        self.ldap.ldap_search = mock.MagicMock(return_value=[{'attributes': {'cn': ['Test User']}},
                                                             {'attributes': {}}])
        res = self.ldap.lookup_feideid('noone@feide.no', ['cn'])
        assert res == {'cn': ['Test User']}

    def test_feide_no_at(self):
        with pytest.raises(ValidationError):
            self.ldap.lookup_feideid('foo', ['cn'])

    def test_feide_ldap_injection(self):
        with pytest.raises(ValidationError):
            self.ldap.lookup_feideid('foo)', ['cn'])
        with pytest.raises(ValidationError):
            self.ldap.lookup_feideid('(bar', ['cn'])
        with pytest.raises(ValidationError):
            self.ldap.lookup_feideid('baz*', ['cn'])
        with pytest.raises(ValidationError):
            self.ldap.lookup_feideid('test\\', ['cn'])
