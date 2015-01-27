from unittest import TestCase
from coreapis import utils


class TestMisc(TestCase):
    def test_public_userinfo(self):
        input = {
            'name': {
                'feide:example.com': 'Test User',
                'ugle:foo.bar': 'Wrong user',
            },
            'selectedsource': 'feide:example.com',
            'userid_sec': [
                'feide:test@example.com',
                'p:00000000-0000-0000-0000-000000000001',
            ]
        }
        output = {
            'name': 'Test User',
            'id': 'p:00000000-0000-0000-0000-000000000001',
        }
        assert utils.public_userinfo(input) == output
