from coreapis.utils import (LogWrapper, translatable, get_platform_admins)
from coreapis.id_providers import get_feideids
from . import BaseBackend

PLATFORMADMIN_TYPE = 'fc:platformadmin'
PLATFORMADMIN_GROUPID = PLATFORMADMIN_TYPE + ':admins'

SCOPES_NEEDED = {'scope_groups-orgadmin'}

PLATFORMADMIN_DISPLAYNAME_NB = "Plattformadministratorer for Dataporten"
PLATFORMADMIN_DISPLAYNAME_NN = "Plattformadministratorar for Dataporten"
PLATFORMADMIN_DISPLAYNAME_EN = "Dataporten Platform Administrators"

PLATFORMADMIN_DISPLAYNAMES = {
    'fallback': PLATFORMADMIN_DISPLAYNAME_NB,
    'nb': PLATFORMADMIN_DISPLAYNAME_NB,
    'nn': PLATFORMADMIN_DISPLAYNAME_NN,
    'en': PLATFORMADMIN_DISPLAYNAME_EN,
}

PLATFORMADMIN_MEMBERSHIP = {
    'basic': 'admin',
    'displayName': 'Administrator'
}


def format_platformadmin_group():
    return {
        'id': PLATFORMADMIN_GROUPID,
        'type': PLATFORMADMIN_TYPE,
        'displayName': translatable(PLATFORMADMIN_DISPLAYNAMES),
        'membership': PLATFORMADMIN_MEMBERSHIP
    }


class PlatformAdminBackend(BaseBackend):
    def __init__(self, prefix, maxrows, settings):
        super(PlatformAdminBackend, self).__init__(prefix, maxrows, settings)
        self.log = LogWrapper('groups.platformadminbackend')
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)
        self.scopes_needed = SCOPES_NEEDED

    def is_platform_admin(self, user):
        feideids = get_feideids(user)
        for admin in self.platformadmins:
            if admin in feideids:
                return True
        return False

    def get_members(self, user, groupid, show_all, include_member_ids):
        if not self.is_platform_admin(user):
            raise KeyError("Not member of group")
        if not groupid == PLATFORMADMIN_GROUPID:
            raise KeyError("Not platformadmin group")
        result = []
        for admin in self.platformadmins:
            result.append({
                'userid': 'feide:' + str(admin),
                'membership': PLATFORMADMIN_MEMBERSHIP
            })
        return result

    def get_member_groups(self, user, show_all):
        if not self.is_platform_admin(user):
            return []
        return [format_platformadmin_group()]

    def get_group(self, user, groupid):
        if not self.is_platform_admin(user):
            raise KeyError("Not member of group")
        if not groupid == PLATFORMADMIN_GROUPID:
            raise KeyError("Not platformadmin group")
        return format_platformadmin_group()

    def get_groups(self, user, query):
        if not self.is_platform_admin(user):
            raise KeyError("Not member of group")
        if query:
            raise KeyError("Querying not supported")
        return [format_platformadmin_group()]

    def grouptypes(self):
        return [
            {
                'id': PLATFORMADMIN_TYPE,
                'displayName': translatable(PLATFORMADMIN_DISPLAYNAMES),
            }
        ]
