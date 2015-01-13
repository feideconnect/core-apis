from unittest import TestCase
import mock
from coreapis.peoplesearch import controller
from coreapis.utils import now
import datetime


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
