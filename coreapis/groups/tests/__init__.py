import uuid
import logging

import eventlet

from coreapis.groups import BaseBackend

USER1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
USER2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
GROUPID1 = 'fc:test:1'
GROUPID2 = 'fc:test:2'

GROUP1 = {
    'id': GROUPID1,
    'displayName': 'Test group 1',
}
GROUP2 = {
    'id': GROUPID2,
    'displayName': 'Test group 2',
    'public': True,
}


class StaleBackend(BaseBackend):
    def get_groups(self, user, query):
        logging.debug('getting groups')
        for _ in range(200):
            eventlet.sleep(0.2)
        return []

    def get_member_groups(self, user, show_all):
        logging.debug('getting groups')
        for _ in range(200):
            eventlet.sleep(0.2)
        return []

    def grouptypes(self):
        return []


class CrashBackend(BaseBackend):
    def get_groups(self, user, query):
        logging.debug('getting groups')
        raise RuntimeError("crash backend in action")

    def get_member_groups(self, user, show_all):
        logging.debug('getting groups')
        raise RuntimeError("crash backend in action")

    def grouptypes(self):
        return []


class MockBackend(BaseBackend):
    def get_membership(self, user, groupid):
        if user['userid'] == USER1 and groupid == GROUPID1:
            return {
                'basic': 'member',
            }
        raise KeyError('not member')

    def get_group(self, user, groupid):
        if user['userid'] == USER1 and groupid == GROUPID1:
            return GROUP1
        raise KeyError('No such group')

    def get_members(self, user, groupid, show_all, include_member_ids):
        if user['userid'] == USER1 and groupid == GROUPID1:
            result = [
                {
                    "name": "test user 1",
                    "membership": {
                        "basic": "member",
                    }
                },
            ]
            if show_all:
                result.append({
                    "name": "test user 2",
                    "membership": {
                        "basic": "member",
                        "active": False,
                    }
                })
            return result
        raise KeyError("not member")

    def get_member_groups(self, user, show_all):
        if user['userid'] == USER1:
            return [GROUP1]
        if user['userid'] == USER2 and show_all:
            return [GROUP1]
        return []

    def get_groups(self, user, query):
        return (g for g in (GROUP1, GROUP2) if query is None or query in g['displayName'])

    def grouptypes(self):
        return [
            {
                'id': 'dataporten:test',
                'displayName': "test groups",
            }
        ]
