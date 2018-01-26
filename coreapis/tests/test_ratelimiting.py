import unittest
import mock
import datetime
from pyramid import testing


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        from coreapis.utils import RateLimiter
        client_max_share = 0.1
        self.bucket_capacity = 3
        self.bucket_leak_rate = 10
        self.ratelimiter = RateLimiter(client_max_share,
                                       self.bucket_capacity, self.bucket_leak_rate)
        self.remote_addr = "127.0.0.1"
        self.nwatched = int(1./client_max_share + 0.5)

    def tearDown(self):
        testing.tearDown()

    def test_unspaced_calls(self):
        faketime = datetime.datetime.now()
        with mock.patch('coreapis.utils.now', return_value=faketime):
            for _ in range(self.bucket_capacity):
                res = self.ratelimiter.check_rate(self.remote_addr)
                assert res is True
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is False

    def test_spaced_calls(self):
        faketime = datetime.datetime.now()
        with mock.patch('coreapis.utils.now', return_value=faketime):
            for _ in range(self.bucket_capacity):
                res = self.ratelimiter.check_rate(self.remote_addr)
                assert res is True
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is False
        faketime += datetime.timedelta(milliseconds=1)
        with mock.patch('coreapis.utils.now', return_value=faketime):
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is True
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is False
        faketime += datetime.timedelta(milliseconds=1000./self.bucket_leak_rate + 1)
        with mock.patch('coreapis.utils.now', return_value=faketime):
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is True

    def test_few_clients(self):
        faketime = datetime.datetime.now()
        with mock.patch('coreapis.utils.now', return_value=faketime):
            for _ in range(self.bucket_capacity + 1):
                self.ratelimiter.check_rate(self.remote_addr)
            for i in range(self.nwatched - 1):
                self.ratelimiter.check_rate(str(i))
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is False

    def test_many_clients(self):
        faketime = datetime.datetime.now()
        with mock.patch('coreapis.utils.now', return_value=faketime):
            for _ in range(self.bucket_capacity + 1):
                self.ratelimiter.check_rate(self.remote_addr)
            for i in range(self.nwatched + 1):
                self.ratelimiter.check_rate(str(i))
            res = self.ratelimiter.check_rate(self.remote_addr)
            assert res is True
