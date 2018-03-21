import unittest

import mock
import webtest

from coreapis import middleware


userid1 = '00000000-0000-0000-0000-000000000001'
clientid1 = '00000000-0000-0000-0000-000000000004'


class GatekeepedMiddlewareTests(unittest.TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.app = mock.Mock()
        timer = None
        self.mw = middleware.GatekeepedMiddleware(self.app, 'testrealm',
                                                  'contact_points', 'keyspace',
                                                  timer, False, None, 'testuser', 'testpass')
        self.session = Client()
        self.testapp = webtest.TestApp(self.mw)

    def testGetAuthorization(self):
        assert self.mw.get_authorization({}) is None
        assert self.mw.get_authorization({'HTTP_AUTHORIZATION': 'Bearer foo'}) is None
        assert self.mw.get_authorization({'HTTP_AUTHORIZATION': 'Basic foo'}) == 'foo'

    def testOKAll(self):
        self.session.get_user_by_id.return_value = 'testuserobject'
        self.session.get_client_by_id.return_value = 'testclientobject'
        self.testapp.authorization = ('Basic', ('testuser', 'testpass'))

        def app(environ, start_response):
            start_response('200 OK', [])
            assert environ.get('FC_TOKEN') == 'token'
            assert environ.get('FC_SCOPES') == ['test_subscope', 'test']
            assert environ.get('FC_USER') == 'testuserobject'
            assert environ.get('FC_CLIENT') == 'testclientobject'
            return []
        self.app.side_effect = app

        headers = {
            'X-Dataporten-Userid': userid1,
            'X-Dataporten-Clientid': clientid1,
            'X-Dataporten-gatekeeper': 'test',
            'X-Dataporten-scopes': 'subscope',
            'X-Dataporten-token': 'token',
        }
        self.testapp.get('/', status=200, headers=headers)
        assert self.app.called

    def testOKSubscopes(self):
        self.session.get_user_by_id.return_value = 'testuserobject'
        self.session.get_client_by_id.return_value = 'testclientobject'
        self.testapp.authorization = ('Basic', ('testuser', 'testpass'))

        def app(environ, start_response):
            start_response('200 OK', [])
            assert environ.get('FC_TOKEN') == 'token'
            assert environ.get('FC_SCOPES') == ['test_subscope1', 'test_subscope2', 'test']
            assert environ.get('FC_USER') is None
            assert environ.get('FC_CLIENT') == 'testclientobject'
            return []
        self.app.side_effect = app

        headers = {
            'X-Dataporten-Clientid': clientid1,
            'X-Dataporten-gatekeeper': 'test',
            'X-Dataporten-scopes': 'subscope1,subscope2',
            'X-Dataporten-token': 'token',
        }
        self.testapp.get('/', status=200, headers=headers)
        assert self.app.called

    def testOKUser(self):
        self.session.get_user_by_id.return_value = 'testuserobject'
        self.session.get_client_by_id.return_value = 'testclientobject'
        self.testapp.authorization = ('Basic', ('testuser', 'testpass'))

        def app(environ, start_response):
            start_response('200 OK', [])
            assert environ.get('FC_TOKEN') == 'token'
            assert environ.get('FC_SCOPES') == ['test']
            assert environ.get('FC_USER') == 'testuserobject'
            assert environ.get('FC_CLIENT') == 'testclientobject'
            return []
        self.app.side_effect = app

        headers = {
            'X-Dataporten-Userid': userid1,
            'X-Dataporten-Clientid': clientid1,
            'X-Dataporten-gatekeeper': 'test',
            'X-Dataporten-token': 'token',
        }
        self.testapp.get('/', status=200, headers=headers)
        assert self.app.called

    def testUnauthenticated(self):
        def app(environ, start_response):
            start_response('200 OK', [])
            assert environ.get('FC_TOKEN') is None
            assert environ.get('FC_USER') is None
            assert environ.get('FC_SCOPES') is None
            assert environ.get('FC_CLIENT') is None
            return []

        self.app.side_effect = app
        self.testapp.get('/', status=200)
        assert self.app.called

    def testUnauthorized(self):
        self.testapp.authorization = ('Basic', ('wronguser', 'wrongpass'))
        self.testapp.get('/', status=401)
        assert not self.app.called
