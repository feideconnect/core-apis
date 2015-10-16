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
        chooser = lambda data: utils.accept_language_matcher(request, data)
        assert self.data.pick_lang(chooser) == 'unittesting is fun'

    def test_fallback_priority(self):
        request = Request({})
        request.headers['Accept-Language'] = 'se;q=0.8,de;q=0.6'
        chooser = lambda data: utils.accept_language_matcher(request, data)
        assert self.data.pick_lang(chooser) == 'unittesting er gøy'

    def test_no_language_header(self):
        request = Request({})
        chooser = lambda data: utils.accept_language_matcher(request, data)
        assert self.data.pick_lang(chooser) == 'unittesting er gøy'

    def test_fall_through(self):
        data = utils.translatable({'de': 'Achtung bitte!'})
        request = Request({})
        chooser = lambda data: utils.accept_language_matcher(request, data)
        assert data.pick_lang(chooser) == 'Achtung bitte!'

    def test_pick_lang(self):
        request = Request({})
        request.headers['Accept-Language'] = 'en-US,en;q=0.8,nb;q=0.6'
        data = [{'foo': self.data, 'baz': 'ugle'}, [{'bar': self.data}]]
        chooser = lambda data: utils.accept_language_matcher(request, data)
        assert utils.pick_lang(chooser, data) == [{'foo': 'unittesting is fun', 'baz': 'ugle'}, [{'bar': 'unittesting is fun'}]]


class TestValidUrl(TestCase):
    def test_valid_urls(self):
        assert utils.valid_url('https://example.com')
        assert utils.valid_url('http://example.com')
        assert utils.valid_url('https://example.com/file')
        assert utils.valid_url('https://example.com:123')

    def test_invalid_urls(self):
        assert not utils.valid_url('ftp://example.com')
        assert not utils.valid_url('https://foo:baR@example.com')
        assert not utils.valid_url('https:///FOO')
