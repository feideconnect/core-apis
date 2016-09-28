#! /usr/bin/env python
import contextlib
import datetime
import json

from cassandra.cluster import Cluster
import cassandra
from cassandra.query import dict_factory
import pytz

from coreapis.utils import LogWrapper, now, translatable, get_cassandra_cluster_args


def parse_apigk(obj):
    for key in ('scopedef', 'trust'):
        if key in obj:
            if obj[key]:
                obj[key] = json.loads(obj[key])
    for key in ('scopes', 'scopes_requested', 'status'):
        if key in obj:
            if obj[key]:
                obj[key] = list(obj[key])
    return obj


def datetime_hack_dict_factory(colnames, rows):
    res = dict_factory(colnames, rows)
    for elt in res:
        for key, val in elt.items():
            if isinstance(val, datetime.datetime):
                elt[key] = val.replace(tzinfo=pytz.UTC)
    return res


class DummyTimer(object):
    @contextlib.contextmanager
    def time(self, counter):
        yield


class Client(object):
    def __init__(self, contact_points, keyspace, use_eventlets=False, authz=None):
        self.log = LogWrapper('coreapis.cassandraclient')
        connection_class = None
        if use_eventlets:
            from cassandra.io.eventletreactor import EventletConnection
            connection_class = EventletConnection
            self.log.info("Using eventlet based cassandra connection")
        cluster_args = get_cassandra_cluster_args(contact_points, connection_class, authz)
        cluster = Cluster(**cluster_args)
        self.prepared = {}
        self.default_columns = {
            'clients': [
                'owner', 'name', 'type', 'status', 'scopes_requested',
                'client_secret', 'created', 'redirect_uri', 'descr', 'id', 'scopes',
                'updated', 'organization', 'orgauthorization', 'authproviders',
                'systemdescr', 'privacypolicyurl', 'homepageurl', 'loginurl', 'supporturl',
                'authoptions'],
            'apigk': [
                'id', 'requireuser', 'created', 'name', 'scopedef', 'httpscertpinned',
                'status', 'descr', 'updated', 'trust', 'endpoints', 'owner',
                'organization', 'systemdescr', 'privacypolicyurl', 'docurl',
                'scopes', 'scopes_requested', 'allow_unauthenticated'],
            'groups': [
                'id', 'created', 'descr', 'name', 'owner', 'public', 'updated',
                'invitation_token'],
            'group_members': ['userid', 'groupid', 'status', 'type', 'added_by'],
            'organizations': [
                'organization_number', 'type', 'realm', 'id', 'name', 'fs_groups', 'services',
                'uiinfo'],
            'orgroles': ['identity', 'orgid', 'role'],
        }
        self.json_columns = {
            'clients': ['authoptions'],
            'apigk': ['scopedef', 'trust'],
            'organizations': ['uiinfo'],
            'orgroles': []
        }
        self.session = cluster.connect(keyspace)
        self.session.row_factory = datetime_hack_dict_factory
        self.session.default_consistency_level = cassandra.ConsistencyLevel.LOCAL_QUORUM
        self.timer = DummyTimer()

    def _prepare(self, query):
        if query in self.prepared:
            return self.prepared[query]
        prep = self.session.prepare(query)
        self.prepared[query] = prep
        return prep

    def _get_compound_pk(self, table, idvs, columns, idcolumns):
        where = ' AND '.join(('{} = ?'.format(col) for col in idcolumns))
        stmt = 'SELECT {} FROM {} WHERE {}'.format(','.join(columns), table, where)
        prep = self._prepare(stmt)
        res = self.session.execute(prep.bind(idvs))
        try:
            return next(iter(res))
        except StopIteration:
            raise KeyError('{} entry not found'.format(table))

    def _get(self, table, idv, columns=None, idcolumn='id'):
        if columns is None:
            columns = self.default_columns[table]
        return self._get_compound_pk(table, [idv], columns, [idcolumn])

    @staticmethod
    def val_to_store(client, colname, jsoncols):
        ret = client[colname]
        if colname in jsoncols:
            ret = json.dumps(ret)
        return ret

    def insert_generic(self, data, tablename):
        table_columns = self.default_columns[tablename]
        colnames = ','.join(table_columns)
        placeholders = ('?,'*len(table_columns))[:-1]  # '?,?,..,?'
        stmt = 'INSERT INTO {} ({}) VALUES ({})'.format(tablename, colnames, placeholders)
        prep = self._prepare(stmt)
        jsoncols = set(self.json_columns[tablename])
        bindvals = [self.val_to_store(data, colname, jsoncols) for colname in table_columns]
        self.session.execute(prep.bind(bindvals))

    def insert_client(self, client):
        self.insert_generic(client, 'clients')

    def get_client_by_id(self, clientid):
        return self._get('clients', clientid)

    def get_generic(self, table, selectors, values, maxrows):
        if len(selectors) != len(values):
            raise KeyError('Selectors and values not same length')
        cols = ','.join(self.default_columns[table])
        if len(selectors) == 0:
            stmt = 'SELECT {} from {} LIMIT {}'.format(cols, table, maxrows)
        else:
            tmpl = 'SELECT {} from {} WHERE {} LIMIT {} ALLOW FILTERING'
            stmt = tmpl.format(cols, table, ' and '.join(selectors), maxrows)
        with self.timer.time('cassandra.get_generic.{}'.format(table)):
            prep = self._prepare(stmt)
            res = self.session.execute(prep.bind(values))
        return res

    def get_clients(self, selectors, values, maxrows):
        return self.get_generic('clients', selectors, values, maxrows)

    def get_clients_by_owner(self, owner):
        prep = self._prepare('SELECT * from clients WHERE owner = ?')
        with self.timer.time('cassandra.get_clients_by_owner'):
            res = self.session.execute(prep.bind([owner]))
        return res

    def get_clients_by_scope(self, scope):
        prep = self._prepare('SELECT * from clients WHERE scopes CONTAINS ?')
        res = self.session.execute(prep.bind([scope]))
        return res

    def get_clients_by_scope_requested(self, scope):
        prep = self._prepare('SELECT * from clients WHERE scopes_requested CONTAINS ?')
        res = self.session.execute(prep.bind([scope]))
        return res

    def delete_client(self, clientid):
        prep = self._prepare('DELETE FROM clients WHERE id = ?')
        with self.timer.time('cassandra.delete_client'):
            self.session.execute(prep.bind([clientid]))
            authzq = self._prepare('SELECT userid FROM oauth_authorizations WHERE clientid = ?')
            userids = self.session.execute(authzq.bind([clientid]))
            for row in userids:
                userid = row['userid']
                self.delete_authorization(userid, clientid)

    def insert_orgauthorization(self, clientid, realm, scopes):
        prep = self._prepare('UPDATE clients SET orgauthorization[?] = ? WHERE id = ?')
        self.session.execute(prep.bind([realm, scopes, clientid]))

    def delete_orgauthorization(self, clientid, realm):
        prep = self._prepare('DELETE orgauthorization[?] FROM clients WHERE id = ?')
        self.session.execute(prep.bind([realm, clientid]))

    def get_token(self, tokenid):
        return self._get('oauth_tokens', tokenid, ['*'], 'access_token')

    def get_tokens_by_scope(self, scope):
        prep = self._prepare('SELECT * FROM oauth_tokens WHERE scope contains ?')
        return self.session.execute(prep.bind([scope]))

    def update_token_scopes(self, access_token, scopes):
        prep = self._prepare('UPDATE oauth_tokens SET scope = ? WHERE access_token = ?')
        self.session.execute(prep.bind([scopes, access_token]))

    def get_user_by_id(self, userid):
        return self._get('users', userid,
                         ['userid', 'aboveagelimit', 'created', 'email', 'name',
                          'selectedsource', 'updated', 'usageterms',
                          'userid_sec', 'userid_sec_seen'],
                         'userid')

    def get_user_profilephoto(self, userid):
        userinfo = self._get('users', userid,
                             ['selectedsource', 'profilephoto', 'updated'], 'userid')
        selectedsource = userinfo['selectedsource']
        profilephoto = userinfo['profilephoto']
        updated = userinfo['updated']
        if profilephoto is None:
            return None, updated
        return profilephoto.get(selectedsource, None), updated

    def insert_user(self, userid, email, name, profilephoto,
                    profilephotohash, selectedsource, userid_sec):
        tstamp = now()
        sec_prep = self._prepare('INSERT INTO userid_sec (userid_sec, userid) VALUES (?, ?)')
        for sec in userid_sec:
            self.session.execute(sec_prep.bind([sec, userid]))

        userid_sec_seen = {sec: tstamp for sec in userid_sec}
        prep = self._prepare('INSERT INTO users (userid, created, email, name, profilephoto, profilephotohash, selectedsource, updated, userid_sec, userid_sec_seen) VALUES (?,?,?,?,?,?,?,?,?,?)')
        self.session.execute(prep.bind([
            userid,
            tstamp,
            email,
            name,
            profilephoto,
            profilephotohash,
            selectedsource,
            tstamp,
            userid_sec,
            userid_sec_seen
        ]))

    def reset_user(self, userid):
        prep = self._prepare('INSERT INTO users (userid, usageterms,email, name, profilephoto, profilephotohash, selectedsource, aboveagelimit) VALUES (?,?,?,?,?,?,?,?)')
        self.session.execute(prep.bind([
            userid, False, {}, {}, {}, {}, None, None
        ]))

    def get_userid_by_userid_sec(self, sec):
        return self._get('userid_sec', sec, ['userid'], 'userid_sec')['userid']

    def get_apigk(self, gkid):
        return parse_apigk(self._get('apigk', gkid))

    def get_apigks(self, selectors, values, maxrows):
        return [parse_apigk(gk) for gk in self.get_generic('apigk', selectors, values, maxrows)]

    def delete_apigk(self, gkid):
        prep = self._prepare('DELETE FROM apigk WHERE id = ?')
        self.session.execute(prep.bind([gkid]))

    def insert_apigk(self, apigk):
        self.insert_generic(apigk, 'apigk')

    def _get_logo(self, table, idvalue):
        res = self._get(table, idvalue, ['logo', 'updated'])
        return res['logo'], res['updated']

    def get_client_logo(self, clientid):
        return self._get_logo('clients', clientid)

    def get_apigk_logo(self, gkid):
        return self._get_logo('apigk', gkid)

    def save_logo(self, table, itemid, data, updated):
        prep = self._prepare('INSERT INTO {} (id, logo, updated) VALUES (?, ?, ?)'.format(table))
        self.session.execute(prep.bind([itemid, data, updated]))

    def get_authorizations(self, userid):
        prep = self._prepare('SELECT * FROM oauth_authorizations WHERE userid = ?')
        return self.session.execute(prep.bind([userid]))

    def delete_token(self, token):
        prep = self._prepare('DELETE FROM oauth_tokens WHERE access_token = ?')
        prep.consistency_level = cassandra.ConsistencyLevel.ALL
        self.session.execute(prep.bind([token]))

    def delete_authorization(self, userid, clientid):
        stmt = 'DELETE FROM oauth_authorizations WHERE userid = ? AND clientid = ?'
        prep_del_auth = self._prepare(stmt)
        prep_del_auth.consistency_level = cassandra.ConsistencyLevel.ALL
        self.session.execute(prep_del_auth.bind([userid, clientid]))
        prep_find_tokens = self._prepare('SELECT access_token FROM oauth_tokens WHERE userid = ? AND clientid = ? ALLOW FILTERING')
        for token in self.session.execute(prep_find_tokens.bind([userid, clientid])):
            tokenid = token['access_token']
            self.log.debug('deleting token', token=tokenid)
            self.delete_token(tokenid)

    def get_oauth_authorizations_by_scope(self, scope):
        prep = self._prepare('SELECT * FROM oauth_authorizations WHERE scopes CONTAINS ?')
        return self.session.execute(prep.bind([scope]))

    def update_oauth_authorization_scopes(self, auth):
        prep = self._prepare('INSERT INTO oauth_authorizations (userid, clientid, scopes) VALUES (?, ?, ?)')
        self.session.execute(prep.bind([auth['userid'], auth['clientid'], auth['scopes']]))

    def get_group(self, groupid):
        return self._get('groups', groupid)

    def delete_group(self, groupid):
        prep = self._prepare('DELETE FROM groups WHERE id = ?')
        self.session.execute(prep.bind([groupid]))

    def insert_group(self, group):
        prep = self._prepare('INSERT INTO groups (id, created, descr, name, owner, updated, public, invitation_token) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
        self.session.execute(prep.bind([
            group['id'],
            group['created'],
            group['descr'],
            group['name'],
            group['owner'],
            group['updated'],
            group['public'],
            group['invitation_token'],
        ]))

    def get_group_logo(self, groupid):
        return self._get_logo('groups', groupid)

    def get_groups(self, selectors, values, maxrows):
        return self.get_generic('groups', selectors, values, maxrows)

    def get_group_members(self, groupid):
        prep = self._prepare('SELECT * FROM group_members WHERE groupid=?')
        return self.session.execute(prep.bind([groupid]))

    def add_group_member(self, groupid, userid, mtype, status, added_by):
        prep = self._prepare('INSERT INTO group_members (groupid, userid, type, status, added_by) values (?,?,?,?,?)')
        self.session.execute(prep.bind([groupid, userid, mtype, status, added_by]))

    def set_group_member_status(self, groupid, userid, status):
        prep = self._prepare('INSERT INTO group_members (groupid, userid, status) values (?,?,?)')
        self.session.execute(prep.bind([groupid, userid, status]))

    def set_group_member_type(self, groupid, userid, mtype):
        prep = self._prepare('INSERT INTO group_members (groupid, userid, type) values (?,?,?)')
        self.session.execute(prep.bind([groupid, userid, mtype]))

    def del_group_member(self, groupid, userid):
        prep = self._prepare('DELETE FROM group_members WHERE groupid = ? AND userid = ?')
        self.session.execute(prep.bind([groupid, userid]))

    def get_membership_data(self, groupid, userid):
        return self._get_compound_pk('group_members', [groupid, userid],
                                     ['*'], ['groupid', 'userid'])

    def get_group_memberships(self, userid, mtype, status, maxrows):
        selectors = ['userid = ?']
        values = [userid]
        if mtype is not None:
            selectors.append('type = ?')
            values.append(mtype)
        if status is not None:
            selectors.append('status = ?')
            values.append(status)
        return self.get_generic('group_members', selectors, values, maxrows)

    def insert_grep_code(self, grep):
        prep = self._prepare('INSERT INTO grep_codes (id, code, title, type, last_changed) values (?,?,?,?,?)')
        self.session.execute(prep.bind([grep['id'], grep['code'], grep['title'],
                                        grep['type'], grep['last_changed']]))

    def get_grep_code(self, grepid):
        return self._get('grep_codes', grepid, ['*'])

    def get_grep_code_by_code(self, code, greptype):
        prep = self._prepare('SELECT * from grep_codes WHERE code = ? and type = ? ALLOW FILTERING')
        data = list(self.session.execute(prep.bind([code, greptype])))
        if len(data) == 0:
            raise KeyError('No such grep code')
        return data[0]

    def get_org(self, orgid):
        data = self._get('organizations', orgid)
        if 'name' in data and data['name'] is not None:
            data['name'] = translatable(data['name'])
        return data

    def get_org_by_realm(self, realm):
        data = self._get('organizations', realm, idcolumn='realm')
        if 'name' in data and data['name'] is not None:
            data['name'] = translatable(data['name'])
        return data

    def list_orgs(self):
        tbl = 'organizations'
        stmt = 'SELECT {} from {}'.format(','.join(self.default_columns[tbl]), tbl)
        prep = self._prepare(stmt)
        data = self.session.execute(prep)
        for item in data:
            if 'name' in item and item['name'] is not None:
                item['name'] = translatable(item['name'])
            yield item

    def insert_org(self, org):
        self.insert_generic(org, 'organizations')

    def delete_org(self, orgid):
        prep = self._prepare('DELETE FROM organizations WHERE id = ?')
        self.session.execute(prep.bind([orgid]))

    def get_org_logo(self, orgid):
        res = self._get('organizations', orgid, ['logo', 'logo_updated'])
        return res['logo'], res['logo_updated']

    def save_org_logo(self, table, itemid, data, updated):
        stmt = 'INSERT INTO {} (id, logo, logo_updated) VALUES (?, ?, ?)'.format(table)
        prep = self._prepare(stmt)
        self.session.execute(prep.bind([itemid, data, updated]))

    def org_use_fs_groups(self, realm):
        prep = self._prepare('SELECT id FROM organizations WHERE realm = ?'
                             ' and services contains \'fsgroups\' ALLOW FILTERING')
        res = list(self.session.execute(prep.bind([realm])))
        if len(res) == 0:
            return False
        return True

    def is_org_admin(self, identity, orgid):
        prep = self._prepare('SELECT role from orgroles where identity = ? AND orgid = ?')
        res = list(self.session.execute(prep.bind([identity, orgid])))
        if len(res) == 0:
            return False
        return 'admin' in res[0]['role']

    def get_mandatory_clients(self, realm):
        prep = self._prepare('SELECT clientid from mandatory_clients where realm = ?')
        res = self.session.execute(prep.bind([realm]))
        return [x['clientid'] for x in res]

    def add_mandatory_client(self, realm, clientid):
        prep = self._prepare('INSERT INTO mandatory_clients (realm, clientid) values (?, ?)')
        self.session.execute(prep.bind([realm, clientid]))

    def del_mandatory_client(self, realm, clientid):
        prep = self._prepare('DELETE FROM mandatory_clients WHERE realm = ? AND clientid = ?')
        return self.session.execute(prep.bind([realm, clientid]))

    def add_services(self, org, services):
        stmt = 'UPDATE organizations set services = services + ? WHERE id = ?'
        prep = self._prepare(stmt)
        self.session.execute(prep.bind([services, org]))

    def del_services(self, org, services):
        stmt = 'UPDATE organizations set services = services - ? WHERE id = ?'
        prep = self._prepare(stmt)
        self.session.execute(prep.bind([services, org]))

    def get_roles(self, selectors, values, maxrows):
        return self.get_generic('orgroles', selectors, values, maxrows)

    def insert_role(self, role):
        self.insert_generic(role, 'orgroles')

    def del_role(self, orgid, identity):
        prep = self._prepare('DELETE FROM orgroles WHERE orgid = ? AND identity = ?')
        self.session.execute(prep.bind([orgid, identity]))

    def apigk_allowed_dn(self, dn):
        prep = self._prepare('SELECT dn from remote_apigatekeepers WHERE dn = ?')
        res = list(self.session.execute(prep.bind([dn])))
        return len(res) > 0

    def get_logins_stats(self, clientid, dates, authsource, maxrows):
        cols = 'date, authsource, timeslot, login_count'
        tmpl = 'SELECT {} FROM logins_stats WHERE clientid = ? AND date in ({})'
        dateslots = (','.join(['?']*len(dates)))  # e.g. (?,?,?)
        stmt = tmpl.format(cols, dateslots)
        bindvals = [clientid]
        bindvals += (str(date) for date in dates)
        if maxrows:
            limit = ' LIMIT {}'.format(maxrows)
        else:
            limit = ''
        if authsource:
            stmt += ' AND authsource = ?'
            bindvals.append(authsource)
            limit += ' ALLOW FILTERING'
        stmt += limit
        prep = self._prepare(stmt)
        return self.session.execute(prep.bind(bindvals))

    def get_statistics(self, date, metric):
        statement = 'SELECT * from statistics WHERE date=?'
        if metric:
            statement += " AND metric=?"
        prep = self._prepare(statement)
        params = [date]
        if metric:
            params.append(metric)
        return self.session.execute(prep.bind(params))
