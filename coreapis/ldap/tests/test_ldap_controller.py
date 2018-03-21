from unittest import TestCase

import mock
import pytest

from coreapis.ldap import controller
from coreapis.utils import ValidationError


class TestLookupFeideid(TestCase):
    def setUp(self):
        mock.mock_open(read_data='{}')
        settings = {
            'timer': mock.MagicMock(),
            'ldap_config_file': 'testdata/test-ldap-config.json',
            'statsd_factory': mock.MagicMock(),
            'statsd_host_factory': mock.MagicMock(),
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

    def test_parse_config_twice(self):
        self.ldap.config_mtime = 0
        self.ldap.parse_ldap_config()
        self.test_feide_multiple_users()


class MockStat(object):
    def __init__(self):
        self.st_mtime = 0


class TestParseConfigNoElapsedTime(TestCase):
    def setUp(self):
        mock.mock_open(read_data='{}')
        settings = {
            'timer': mock.MagicMock(),
            'ldap_config_file': 'testdata/test-ldap-config.json',
            'statsd_factory': mock.MagicMock(),
            'statsd_host_factory': mock.MagicMock(),
        }
        with mock.patch('os.stat', return_value=MockStat()):
            self.ldap = controller.LDAPController(settings)

    def test_parse_config_no_elapsed_time(self):
        pass  # We just care about setup
