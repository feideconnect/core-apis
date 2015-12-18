import uuid
import logging

import eventlet

from coreapis.groups import BaseBackend

user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
user2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
groupid1 = 'fc:test:1'
groupid2 = 'fc:test:2'

group1 = {
    'id': groupid1,
    'displayName': 'Test group 1',
}
group2 = {
    'id': groupid2,
    'displayName': 'Test group 2',
    'public': True,
}


class StaleBackend(BaseBackend):
    def get_groups(self, user, query):
        logging.debug('getting groups')
        for i in range(200):
            eventlet.sleep(0.2)
        return []

    def get_member_groups(self, user, show_all):
        logging.debug('getting groups')
        for i in range(200):
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
        if user['userid'] == user1 and groupid == groupid1:
            return {
                'basic': 'member',
            }
        raise KeyError('not member')

    def get_group(self, user, groupid):
        if user['userid'] == user1 and groupid == groupid1:
            return group1
        raise KeyError('No such group')

    def get_members(self, user, groupid, show_all, include_member_ids):
        if user['userid'] == user1 and groupid == groupid1:
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
        if user['userid'] == user1:
            return [group1]
        if user['userid'] == user2 and show_all:
            return [group1]
        return []

    def get_groups(self, user, query):
        return (g for g in (group1, group2) if query is None or query in g['displayName'])

    def grouptypes(self):
        return [
            {
                'id': 'feideconnect:test',
                'displayName': "test groups",
            }
        ]
