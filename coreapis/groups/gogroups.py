from urllib.parse import unquote as urlunquote, quote as urlquote
import datetime
import pytz
from coreapis.utils import translatable, now, LogWrapper

GO_TYPES = {
    'u': translatable({
        'nb': 'undervisningsgruppe',
    }),
    'b': translatable({
        'nb': 'basisgruppe',
    }),
    'a': translatable({
        'nb': 'andre grupper',
        'en': 'other groups',
    }),
}
AFFILIATION_NAMES = {
    'faculty': translatable({
        'nb': 'Lærer',
        'nn': 'Lærar',
    }),
    'staff': translatable({
        'nb': 'Stab',
    }),
    'employee': translatable({
        'nb': 'Ansatt',
        'nn': 'Tilsett',
    }),
    'student': translatable({
        'nb': 'Elev',
    }),
    #        'alum': translatable({
    #        }),
    'affiliate': translatable({
        'nb': 'Ekstern',
    }),
    #        'library-walk-in': translatable({
    #        }),
    'member': translatable({
        'nb': 'Annet',
        'nn': 'Anna',
    })
}
GOGROUP_PREFIX = 'urn:mace:feide.no:go:group:'
GOGROUPID_PREFIX = 'urn:mace:feide.no:go:groupid:'


def go_split(string):
    return [urlunquote(part) for part in string.split(':')]


def go_join(parts):
    return ":".join((urlquote(part) for part in parts))


def parse_go_date(date):
    res = datetime.datetime.strptime(date, '%Y-%m-%d')
    return res.replace(tzinfo=pytz.UTC)


def format_go_date(date):
    return date.strftime('%Y-%m-%d')


def groupid_entitlement(group_id_base):
    return "{}{}".format(GOGROUPID_PREFIX, group_id_base)


class GOGroup(object):
    def __init__(self, group_string, *, canonicalize=True):
        self.log = LogWrapper('groups.ldapbackend.gogroups')
        if not group_string.startswith(GOGROUP_PREFIX):
            raise KeyError("Found malformed group info: {}".format(group_string))
        parts = go_split(group_string)
        if len(parts) != 13:
            raise KeyError("Found malformed group info: {}".format(group_string))
        group_type, grep_code, organization, _group_id, valid_from, valid_to, role, name = parts[5:]
        self.group_type = group_type
        self.grep_code = grep_code
        self.organization = organization
        self._group_id = _group_id
        self.valid_from = parse_go_date(valid_from)
        self.valid_to = parse_go_date(valid_to)
        self.role = role
        self.name = name
        if canonicalize:
            self.group_type = self.group_type.lower()
            self.grep_code = self.grep_code.upper()
            self.organization = self.organization.upper()
            self._group_id = self._group_id.lower()
            self.role = self.role.lower()

    def valid(self):
        ts = now()
        return ts >= self.valid_from and ts <= self.valid_to

    def group_id_base(self):
        return go_join((self.group_type, self.organization, self._group_id,
                        format_go_date(self.valid_from),
                        format_go_date(self.valid_to)))

    def group_id(self, prefix, realm):
        return ':'.join((prefix, realm, self.group_id_base()))

    def format_group(self, prefix, realm, parent_prefix):
        result = {
            'id': self.group_id(prefix, realm),
            'displayName': self.name,
            'type': 'fc:gogroup',
            'notBefore': self.valid_from,
            'notAfter': self.valid_to,
            'go_type': self.group_type,
            'parent': '{}:{}:unit:{}'.format(parent_prefix, realm, self.organization),
            'membership': self.membership(),
        }
        if self.group_type in GO_TYPES:
            result['go_type_displayName'] = GO_TYPES[self.group_type]
        else:
            self.log.warn('Found invalid go group type', GO_TYPE=self.group_type)
        return result

    def groupid_entitlement(self):
        return groupid_entitlement(self.group_id_base())

    def membership(self):
        membership = {
            'basic': 'admin' if self.role == 'faculty' else 'member',
            'affiliation': self.role,
        }
        if self.role in AFFILIATION_NAMES:
            membership['displayName'] = AFFILIATION_NAMES[self.role]
        else:
            membership['displayName'] = self.role
        return membership

    @classmethod
    def candidate(cls, string):
        return string.startswith(GOGROUP_PREFIX)
