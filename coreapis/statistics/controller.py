from coreapis.utils import LogWrapper, \
    get_platform_admins, get_feideids
import coreapis.cassandra_client


class StatisticsController(object):

    def __init__(self, settings):
        contact_points = settings.get('cassandra_contact_points')
        authz = settings.get('cassandra_authz')
        keyspace = settings.get('cassandra_keyspace')
        timer = settings.get('timer')

        self.t = timer
        self.log = LogWrapper('peoplesearch.PeopleSearchController')
        self.db = coreapis.cassandra_client.Client(contact_points, keyspace, authz)
        self.search_max_replies = 50
        platformadmins_file = settings.get('platformadmins_file')
        self.platformadmins = get_platform_admins(platformadmins_file)

    def is_platform_admin(self, user):
        if user is None:
            return False
        for feideid in get_feideids(user):
            if feideid in self.platformadmins:
                return True
        return False

    def get_statistics(self, date, metric, user):
        return {
            r['metric']: r['value'] for r in self.db.get_statistics(date, metric)
        }
