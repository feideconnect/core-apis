from unittest import TestCase
import uuid
from coreapis import utils
import py.test
from pyramid.testing import DummyRequest
from webob import Request


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


class TestGetFeideids(TestCase):
    def test_ok(self):
        user = {
            'userid_sec': ['feide:test@example.org', 'test:1234', 'feide:test@example.com'],
            'userid': uuid.uuid4(),
        }
        assert utils.get_feideids(user) == set(('test@example.org', 'test@example.com'))

    def test_no_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'mail:test@example.com'],
            'userid': uuid.uuid4(),
        }
        assert utils.get_feideids(user) == set()

    def test_malformed_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'feide:foo'],
            'userid': uuid.uuid4(),
        }
        assert utils.get_feideids(user) == set()


class TestGetFeideid(TestCase):
    def test_ok(self):
        user = {
            'userid_sec': ['test:1234', 'feide:test@example.com'],
            'userid': uuid.uuid4(),
        }
        assert utils.get_feideid(user) == 'test@example.com'

    def test_no_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'mail:test@example.com'],
            'userid': uuid.uuid4(),
        }
        with py.test.raises(RuntimeError):
            utils.get_feideid(user)

    def test_malformed_feideid(self):
        user = {
            'userid_sec': ['test:1234', 'feide:foo'],
            'userid': uuid.uuid4(),
        }
        with py.test.raises(RuntimeError):
            utils.get_feideid(user)


class TestTranslatable(TestCase):
    data = utils.translatable({
        'nb': 'unittesting er gøy',
        'en': 'unittesting is fun',
    })

    def test_best_match(self):
        request = Request({})
        request.headers['Accept-Language'] = 'en-US,en;q=0.8,nb;q=0.6'
        print(request.accept_language)
        assert self.data.pick_lang(request) == 'unittesting is fun'

    def test_fallback_priority(self):
        request = Request({})
        request.headers['Accept-Language'] = 'se;q=0.8,de;q=0.6'
        assert self.data.pick_lang(request) == 'unittesting er gøy'

    def test_no_language_header(self):
        request = Request({})
        assert self.data.pick_lang(request) == 'unittesting er gøy'

    def test_fall_through(self):
        data = utils.translatable({'de': 'Achtung bitte!'})
        request = Request({})
        assert data.pick_lang(request) == 'Achtung bitte!'

    def test_pick_lang(self):
        request = Request({})
        request.headers['Accept-Language'] = 'en-US,en;q=0.8,nb;q=0.6'
        data = [{'foo': self.data, 'baz': 'ugle'}, [{'bar': self.data}]]
        assert utils.pick_lang(request, data) == [{'foo': 'unittesting is fun', 'baz': 'ugle'}, [{'bar': 'unittesting is fun'}]]

    def test_disable_translation(self):
        request = Request({})
        request.headers['Accept-Language'] = 'en-US,en;q=0.8,nb;q=0.6'
        request.method = 'PUT'
        request.body = b'translate=false'
        request.environ['CONTENT_LENGTH'] = str(len(request.body))
        request.environ['CONTENT_TYPE'] = 'application/x-www-form-urlencoded'
        data = [{'foo': self.data, 'baz': 'ugle'}, [{'bar': self.data}]]
        expected = [
            {
                'foo': {'nb': 'unittesting er gøy',
                        'en': 'unittesting is fun'},
                'baz': 'ugle',
            },
            [
                {
                    'bar': {
                        'nb': 'unittesting er gøy',
                        'en': 'unittesting is fun'
                    }
                }
            ]
        ]
        assert utils.pick_lang(request, data) == expected
