from unittest import TestCase
import uuid
from coreapis import id_providers
import py.test


class TestGetFeideids(TestCase):
    def test_ok(self):
        user = {
            'userid_sec': ['feide:test@example.org', 'test:1234', 'feide:test@example.com'],
            'userid': uuid.uuid4(),
        }
        assert id_providers.get_feideids(user) == set(('test@example.org', 'test@example.com'))

    def test_no_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'mail:test@example.com'],
            'userid': uuid.uuid4(),
        }
        assert id_providers.get_feideids(user) == set()

    def test_malformed_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'feide:foo'],
            'userid': uuid.uuid4(),
        }
        assert id_providers.get_feideids(user) == set()


class TestGetFeideid(TestCase):
    def test_ok(self):
        user = {
            'userid_sec': ['test:1234', 'feide:test@example.com'],
            'userid': uuid.uuid4(),
        }
        assert id_providers.get_feideid(user) == 'test@example.com'

    def test_no_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'mail:test@example.com'],
            'userid': uuid.uuid4(),
        }
        with py.test.raises(RuntimeError):
            id_providers.get_feideid(user)

    def test_malformed_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'feide:foo'],
            'userid': uuid.uuid4(),
        }
        with py.test.raises(RuntimeError):
            id_providers.get_feideid(user)
