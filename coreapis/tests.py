import unittest

from pyramid import testing


class ViewTests(unittest.TestCase):
    def setUp(self):
        self.config = testing.setUp()
        self.config.include('coreapis.views.configure')

    def tearDown(self):
        testing.tearDown()

    def test_test_open(self):
        from .views import test_open
        request = testing.DummyRequest()
        info = test_open(request)
        self.assertEqual(info['status'], 'open')

    def test_test_client_unauthorized(self):
        from .views import test_client
        request = testing.DummyRequest()
        info = test_client(request)
        self.assertEqual(request.response.status_code, 402)

    def test_test_user_unauthorized(self):
        from .views import test_user
        request = testing.DummyRequest()
        info = test_user(request)
        self.assertEqual(request.response.status_code, 402)
