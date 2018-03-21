from unittest import TestCase
import uuid
from coreapis import utils
import py.test
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


class TestPreferredEmail(TestCase):
    def test_ok(self):
        user = {
            'email': {'feide:example.org': 'test@example.org'},
            'userid': uuid.uuid4(),
            'selectedsource': 'feide:example.org',
        }
        assert utils.preferred_email(user) == 'test@example.org'

    def test_empty(self):
        assert utils.preferred_email({}) is None

    def test_no_selectedsource(self):
        user = {
            'email': {'feide:example.org': 'test@example.org'},
            'userid': uuid.uuid4(),
        }
        assert utils.preferred_email(user) == 'test@example.org'

    def test_no_addr(self):
        user = {
            'email': {'feide:example.org': ''},
            'userid': uuid.uuid4(),
        }
        assert utils.preferred_email(user) is None


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

        def chooser(data):
            return utils.accept_language_matcher(request, data)
        assert self.data.pick_lang(chooser) == 'unittesting is fun'

    def test_fallback_priority(self):
        request = Request({})
        request.headers['Accept-Language'] = 'se;q=0.8,de;q=0.6'

        def chooser(data):
            return utils.accept_language_matcher(request, data)
        assert self.data.pick_lang(chooser) == 'unittesting er gøy'

    def test_no_language_header(self):
        request = Request({})

        def chooser(data):
            return utils.accept_language_matcher(request, data)
        assert self.data.pick_lang(chooser) == 'unittesting er gøy'

    def test_fall_through(self):
        data = utils.translatable({'de': 'Achtung bitte!'})
        request = Request({})

        def chooser(data):
            return utils.accept_language_matcher(request, data)
        assert data.pick_lang(chooser) == 'Achtung bitte!'

    def test_pick_lang(self):
        request = Request({})
        request.headers['Accept-Language'] = 'en-US,en;q=0.8,nb;q=0.6'
        data = [{'foo': self.data, 'baz': 'ugle'}, [{'bar': self.data}]]

        def chooser(data):
            return utils.accept_language_matcher(request, data)
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


class TestValidName(TestCase):
    def test_valid_names(self):
        for name in (
                "Dataporten klient 1",
                "Dataporten & stuff",
                "Kient-4+",
                ):
            assert utils.valid_name(name) == name

    def test_invalid_names(self):
        for name in (
                "",
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa'
                'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
                False,
                None,
                42,
                ):
            with py.test.raises(ValueError):
                utils.valid_name(name)

    def test_adaption(self):
        assert utils.valid_name("<script>") == "script"
        assert utils.valid_name("foo\rbar") == "foobar"
        assert utils.valid_name("   foo") == "foo"
        assert utils.valid_name("øæå") == "øæå"
        assert utils.valid_name("my\u1680bad") == "mybad"


class TestValidDescription(TestCase):
    def test_valid_descriptions(self):
        for description in (
                "Dataporten klient 1\nFine ting",
                "Kient-4+\n\nintro\n\nmer info",
                ):
            assert utils.valid_description(description) == description

    def test_invalid_descriptions(self):
        for description in (
                3,
                "foobar"*1000,
                ):
            with py.test.raises(ValueError):
                utils.valid_description(description)

    def test_adaption(self):
        assert utils.valid_description("   foo") == "foo"
        assert utils.valid_description("øæå") == "øæå"
        assert utils.valid_description("foo \n\n \n\n bar") == "foo\n\nbar"


class TestLogToken(TestCase):
    def test_string(self):
        assert utils.log_token('7d4a4d65-8670-4b75-994b-894872fe1d46') == '739384b61d0cd34c2da0687e7aab162e'

    def test_uuid(self):
        assert utils.log_token(uuid.UUID('7d4a4d65-8670-4b75-994b-894872fe1d46')) == '739384b61d0cd34c2da0687e7aab162e'
