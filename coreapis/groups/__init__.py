from coreapis.utils import now


class IDHandler(object):
    def __init__(self, get_group, get_membership, get_members, get_logo, permissions_ok):
        self.get_group = get_group
        self.get_membership = get_membership
        self.get_members = get_members
        self.get_logo = get_logo
        self.permissions_ok = permissions_ok


class BaseBackend(object):
    def __init__(self, prefix, maxrows, settings):
        self.prefix = prefix
        self.maxrows = maxrows
        self.scopes_needed = set()

    def _groupid(self, gid):
        return "{}:{}".format(self.prefix, gid)

    def _intid(self, groupid):
        parts = groupid.split(':', 2)
        if len(parts) != 3:
            raise KeyError('Bad group id')
        return parts[2]

    def get_id_handlers(self):
        return {
            self.prefix: IDHandler(self.get_group, self.get_membership,
                                   self.get_members, self.get_logo, self.permissions_ok),
        }

    def permissions_ok(self, perm_checker):
        objections = [scope for scope in self.scopes_needed if not perm_checker(scope)]
        return len(objections) == 0

    def get_membership(self, user, groupid):
        pass

    def get_group(self, user, groupid):
        pass

    def get_members(self, user, groupid, show_all):
        pass

    def get_logo(self, groupid):
        return None, now()

    def get_member_groups(self, user, show_all):
        pass

    def get_groups(self, user, query):
        pass

    def grouptypes(self):
        pass
