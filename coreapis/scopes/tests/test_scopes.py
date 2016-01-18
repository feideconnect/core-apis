from unittest import TestCase

from coreapis import scopes


class TestFilterMissingMainscope(TestCase):
    def test_empty(self):
        assert scopes.filter_missing_mainscope([]) == []

    def test_no_gk_scopes(self):
        assert scopes.filter_missing_mainscope(['groups', 'userinfo']) == ['groups', 'userinfo']

    def test_gk_just_mainscope(self):
        assert scopes.filter_missing_mainscope(['gk_foo']) == ['gk_foo']

    def test_gk_main_and_subscope(self):
        filter = ['gk_foo', 'gk_foo_bar']
        assert scopes.filter_missing_mainscope(filter) == filter

    def test_gk_missing_mainscope(self):
        assert scopes.filter_missing_mainscope(['gk_foo_bar']) == []
