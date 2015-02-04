from coreapis.groups import BaseBackend
import uuid

user1 = uuid.UUID("00000000-0000-0000-0000-000000000001")
user2 = uuid.UUID("00000000-0000-0000-0000-000000000002")
groupid1 = 'test:1'
groupid2 = 'test:2'

group1 = {
    'id': groupid1,
    'displayName': 'Test group 1',
}
group2 = {
    'id': groupid2,
    'displayName': 'Test group 2',
    'public': True,
}



class MockBackend(BaseBackend):
    def get_membership(self, userid, groupid):
        if userid == user1 and groupid == groupid1:
            return {
                'basic': 'member',
            }
        raise KeyError('not member')

    def get_group(self, userid, groupid):
        if userid == user1 and groupid == groupid1:
            return group1
        raise KeyError('No such group')

    def get_members(self, userid, groupid, show_all):
        if userid == user1 and groupid == groupid1:
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

    def get_member_groups(self, userid, show_all):
        if userid == user1:
            return [group1]
        if userid == user2 and show_all:
            return [group1]
        return []

    def get_groups(self, userid, query):
        return (g for g in (group1, group2) if query is None or query in g['displayName'])

    def grouptypes(self):
        return [
            {
                'id': 'feideconnect:test',
                'displayName': "test groups",
            }
        ]
