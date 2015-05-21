from unittest import TestCase
import mock
from coreapis.userinfo import controller


class TestUserInfo(TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        self.controller = controller.UserInfoController([], 'keyspace', mock.MagicMock)

    def test_userinfo(self):
        user = {'userid_sec': ['feide:dd@vg.no']}
        info = {
            'title;lang-no-no': ['Prosjektmotarbeider'],
            'displayName': ['Donald Duck']
        }
        self.controller.ldap.lookup_feideid = mock.MagicMock(return_value=info)
        res = self.controller.get_userinfo(user, lambda x: True)
        assert type(res['title']) == list
        assert type(res['displayName']) == str


class TestMisc(TestCase):
    def setUp(self):
        self.scopes = {'scope_userinfo', 'scope_userinfo-feide'}

    def test_allowed_attributes(self):
        candidates = controller.USER_INFO_ATTRIBUTES_FEIDE
        allowed = controller.allowed_attributes(controller.USER_INFO_ATTRIBUTES_FEIDE,
                                                lambda x: x in self.scopes)
        assert len(allowed) == len(candidates['userinfo']) + len(candidates['userinfo-feide'])
