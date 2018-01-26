from unittest import TestCase
from unittest import mock
from coreapis.userinfo import controller


class TestUserInfo(TestCase):
    @mock.patch('coreapis.middleware.cassandra_client.Client')
    def setUp(self, Client):
        settings = {
            'cassandra_contact_points': [],
            'cassandra_keyspace': 'keyspace',
            'ldap_controller': mock.MagicMock
        }
        self.controller = controller.UserInfoController(settings)

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
        self.scopes = {'scope_profile', 'scope_userid-feide'}

    def test_allowed_attributes(self):
        candidates = controller.USER_INFO_ATTRIBUTES_FEIDE
        allowed = controller.allowed_attributes(controller.USER_INFO_ATTRIBUTES_FEIDE,
                                                lambda x: x in self.scopes)
        assert len(allowed) == len(candidates['profile']) + len(candidates['userid-feide'])
