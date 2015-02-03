class BaseBackend(object):
    def __init__(self, prefix, maxrows):
        self.prefix = prefix
        self.maxrows = maxrows

    def _groupid(self, gid):
        return "{}:{}".format(self.prefix, gid)

    def get_membership(self, userid, groupid):
        pass

    def get_group(self, userid, groupid):
        pass

    def get_members(self, userid, groupid, show_all):
        pass

    def get_member_groups(self, userid, show_all):
        pass

    def get_groups(self, userid, query):
        pass

    def grouptypes(self):
        pass
