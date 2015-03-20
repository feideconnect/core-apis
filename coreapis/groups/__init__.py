class IDHandler(object):
    def __init__(self, get_group, get_membership, get_members, get_logo):
        self.get_group = get_group
        self.get_membership = get_membership
        self.get_members = get_members
        self.get_logo = get_logo


class BaseBackend(object):
    def __init__(self, prefix, maxrows, config):
        self.prefix = prefix
        self.maxrows = maxrows

    def _groupid(self, gid):
        return "{}:{}".format(self.prefix, gid)

    def get_id_handlers(self):
        return {
            self.prefix: IDHandler(self.get_group, self.get_membership,
                                   self.get_members, self.get_logo),
        }

    def get_membership(self, user, groupid):
        pass

    def get_group(self, user, groupid):
        pass

    def get_members(self, user, groupid, show_all):
        pass

    def get_logo(self, groupid):
        pass

    def get_member_groups(self, user, show_all):
        pass

    def get_groups(self, user, query):
        pass

    def grouptypes(self):
        pass
