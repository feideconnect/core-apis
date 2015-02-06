from unittest import TestCase
import mock
from coreapis.peoplesearch import controller
from coreapis.utils import now, ValidationError
import datetime
import pytest
import io
from PIL import Image


class TestProfileImageCacheLogic(TestCase):

    age = 100

    def setUp(self):
        with mock.patch('coreapis.peoplesearch.controller.CassandraCache') as cache:
            self.controller = controller.PeopleSearchController('key', mock.MagicMock(),
                                                                mock.MagicMock(), [],
                                                                'keyspace', self.age)
            self.cache = cache

    def test_cache_miss(self):
        self.controller.db.lookup = mock.MagicMock(return_value=None)
        self.controller._fetch_profile_image = mock.MagicMock(return_value=(1, 2, 3))
        self.controller.cache_profile_image = mock.MagicMock()
        image, etag, last_modified = self.controller.profile_image('testuser')
        self.controller._fetch_profile_image.assert_called_with('testuser')
        self.controller.cache_profile_image.assert_called_with('testuser', 3, 2, 1)

    def test_cache_stale_updated(self):
        cache = {
            'last_modified': now(),
            'last_updated': now() - datetime.timedelta(seconds=self.age),
            'etag': 1,
            'image': 2
        }
        self.controller.db.lookup = mock.MagicMock(return_value=cache)
        modified_time = now()
        self.controller._fetch_profile_image = mock.MagicMock(return_value=(4, 5, modified_time))
        self.controller.cache_profile_image = mock.MagicMock()
        image, etag, last_modified = self.controller.profile_image('testuser')
        self.controller._fetch_profile_image.assert_called_with('testuser')
        self.controller.cache_profile_image.assert_called_with('testuser', modified_time, 5, 4)

    def test_cache_stale_not_updated(self):
        modified_time = now()
        cache = {
            'last_modified': modified_time,
            'last_updated': now() - datetime.timedelta(seconds=self.age),
            'etag': 1,
            'image': 2
        }
        self.controller.db.lookup = mock.MagicMock(return_value=cache)
        self.controller._fetch_profile_image = mock.MagicMock(return_value=(2, 1, now()))
        self.controller.cache_profile_image = mock.MagicMock()
        image, etag, last_modified = self.controller.profile_image('testuser')
        self.controller._fetch_profile_image.assert_called_with('testuser')
        self.controller.cache_profile_image.assert_called_with('testuser', modified_time, 1, 2)

    def test_cache_up_to_date(self):
        modified_time = now()
        cache = {
            'last_modified': modified_time,
            'last_updated': modified_time,
            'etag': 1,
            'image': 2
        }
        self.controller.db.lookup = mock.MagicMock(return_value=cache)
        self.controller._fetch_profile_image = mock.MagicMock(return_value=(2, 1, now()))
        self.controller.cache_profile_image = mock.MagicMock()
        image, etag, last_modified = self.controller.profile_image('testuser')
        assert image == 2
        assert etag == 1
        assert last_modified == modified_time
        assert not self.controller._fetch_profile_image.called
        assert not self.controller.cache_profile_image.called


class TestProfileImageFetch(TestCase):
    def setUp(self):
        self.ldap = mock.MagicMock()
        with mock.patch('coreapis.peoplesearch.controller.CassandraCache'):
            self.controller = controller.PeopleSearchController('key', mock.MagicMock(),
                                                                mock.MagicMock(), [],
                                                                'keyspace', 0)
            self.controller.ldap = self.ldap

    def test_feide_no_user(self):
        self.controller.ldap.ldap_search = mock.MagicMock(return_value=[])
        image, etag, modified = self.controller._profile_image_feide('noone@feide.no')
        assert image is None
        assert etag is None
        assert modified is None

    def test_feide_no_image(self):
        self.controller.ldap.ldap_search = mock.MagicMock(return_value=[{'attributes': {}}])
        image, etag, modified = self.controller._profile_image_feide('noone@feide.no')
        assert image is None
        assert etag is None
        assert modified is None

    def test_feide(self):
        with open('testdata/blank.jpg', 'rb') as fh:
            imgdata = fh.read()
        self.controller.ldap.lookup_feideid.return_value = {'jpegPhoto': [imgdata]}
        image, etag, modified = self.controller._profile_image_feide('noone@feide.no')
        assert etag == '29e57d60210642ece67970a0cd9fd11b'
        assert image == imgdata


class TestLookupFeideid(TestCase):
    def setUp(self):
        m = mock.mock_open(read_data='{}')
        with mock.patch('coreapis.peoplesearch.controller.open', m, create=True):
            self.ldap = controller.LDAPController(mock.MagicMock())

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


class TestFetchProfileImage(TestCase):
    def setUp(self):
        with mock.patch('coreapis.peoplesearch.controller.CassandraCache'):
            self.controller = controller.PeopleSearchController('key', mock.MagicMock(),
                                                                mock.MagicMock(), [],
                                                                'keyspace', 0)

    def test_malformed_user(self):
        with pytest.raises(ValidationError):
            self.controller._fetch_profile_image('bad user id format')

    def test_unsupported_user(self):
        with pytest.raises(ValidationError):
            self.controller._fetch_profile_image('unsupported:foo')

    def test_no_img(self):
        self.controller.profile_image_feide = mock.MagicMock(return_value=(None, None, None))
        image, etag, last_modified = self.controller._fetch_profile_image('feide:noone@example.com')
        assert image is not None
        assert etag == '23a3776bada0ac91a01dd43bf9cce84b'
        assert last_modified is not None
        assert isinstance(last_modified, datetime.datetime)

    def test_ok(self):
        with open('testdata/blank.jpg', 'rb') as fh:
            imgdata = fh.read()
        modified = now()
        self.controller._profile_image_feide = mock.MagicMock(return_value=(imgdata, 'etag', modified))
        image, etag, last_modified = self.controller._fetch_profile_image('feide:noone@example.com')
        assert image != imgdata
        assert etag == 'etag'
        assert last_modified == modified
        fake_file = io.BytesIO(image)
        image = Image.open(fake_file)
        assert image.format == 'JPEG'
        width, height = image.size
        assert width <= 128
        assert height <= 128


class TestMisc(TestCase):
    def test_validate_query(self):
        with pytest.raises(ValidationError):
            controller.validate_query(')')
        with pytest.raises(ValidationError):
            controller.validate_query('(')
        with pytest.raises(ValidationError):
            controller.validate_query('*')
        with pytest.raises(ValidationError):
            controller.validate_query('\\')

    def test_flatten(self):
        indata = {'foo': ['bar']}
        testdata = indata.copy()
        controller.flatten(testdata, ('foo',))
        assert testdata == {'foo': 'bar'}
        testdata = indata.copy()
        controller.flatten(testdata, ('bar',))
        assert testdata == indata
