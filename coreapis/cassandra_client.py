#! /usr/bin/env python
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
import time
import json
import datetime
import pytz
from coreapis.utils import LogWrapper


def parse_apigk(obj):
    for key in ('expose', 'scopedef', 'trust'):
        if key in obj:
            if obj[key]:
                obj[key] = json.loads(obj[key])
    return obj


def datetime_hack_dict_factory(colnames, rows):
    res = dict_factory(colnames, rows)
    for el in res:
        for key, val in el.items():
            if isinstance(val, datetime.datetime):
                el[key] = val.replace(tzinfo=pytz.UTC)
    return res


class Client(object):
    def __init__(self, contact_points, keyspace, use_eventlets=False):
        self.log = LogWrapper('coreapis.cassandraclient')
        connection_class = None
        if use_eventlets:
            from cassandra.io.eventletreactor import EventletConnection
            connection_class = EventletConnection
            self.log.info("Using eventlet based cassandra connection")
        cluster = Cluster(
            contact_points=contact_points,
            connection_class=connection_class,
        )
        self.default_columns = {
            'clients': 'owner,name,type,status,scopes_requested,client_secret,created,redirect_uri,descr,id,scopes,updated',
            'apigk': 'id,requireuser,created,name,scopedef,httpscertpinned,status,descr,expose,updated,trust,endpoints,owner',
            'groups': 'id,created,descr,name,owner,public,updated',
            'group_members': 'userid,groupid,status,type',
        }
        self.session = cluster.connect(keyspace)
        self.session.row_factory = datetime_hack_dict_factory
        self.s_get_client = self.session.prepare('SELECT {} FROM clients WHERE id = ?'.format(self.default_columns['clients']))
        self.s_delete_client = self.session.prepare('DELETE FROM clients WHERE id = ?')
        self.s_get_token = self.session.prepare('SELECT * FROM oauth_tokens WHERE access_token = ?')
        self.s_get_user = self.session.prepare('SELECT * FROM users WHERE userid = ?')
        self.s_get_apigk = self.session.prepare('SELECT {} FROM apigk WHERE id = ?'.format(self.default_columns['apigk']))
        self.s_delete_apigk = self.session.prepare('DELETE FROM apigk WHERE id = ?')
        self.s_get_client_logo = self.session.prepare('SELECT logo, updated FROM clients WHERE id = ?')
        self.s_get_apigk_logo = self.session.prepare('SELECT logo, updated FROM apigk WHERE id = ?')
        self.s_get_authorizations = self.session.prepare('SELECT * FROM oauth_authorizations WHERE userid = ?')
        self.s_delete_authorization = self.session.prepare('DELETE FROM oauth_authorizations WHERE userid = ? AND clientid = ?')
        self.s_delete_token = self.session.prepare('DELETE FROM oauth_tokens WHERE access_token = ?')
        self.s_get_group = self.session.prepare('SELECT {} FROM groups WHERE id = ?'.format(self.default_columns['groups']))
        self.s_delete_group = self.session.prepare('DELETE FROM groups WHERE id = ?')
        self.s_get_group_logo = self.session.prepare('SELECT logo, updated FROM groups WHERE id = ?')

    def insert_client(self, id, client_secret, name, descr,
                      redirect_uri, scopes, scopes_requested, status,
                      type, create_ts, update_ts, owner):
        prep = self.session.prepare('INSERT INTO clients (id, client_secret, name, descr, redirect_uri, scopes, scopes_requested, status, type, created, updated, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
        self.session.execute(prep.bind([id, client_secret, name, descr,
                                        redirect_uri, scopes, scopes_requested,
                                        status, type, create_ts, update_ts, owner]))

    def get_client_by_id(self, clientid):
        prep = self.s_get_client
        res = self.session.execute(prep.bind([clientid]))
        if len(res) == 0:
            raise KeyError('No such client')
        return res[0]

    def get_generic(self, table, selectors, values, maxrows):
        if len(selectors) != len(values):
            raise KeyError('Selectors and values not same length')
        cols = self.default_columns[table]
        if len(selectors) == 0:
            stmt = 'SELECT {} from {} LIMIT {}'.format(cols, table, maxrows)
        else:
            stmt = 'SELECT {} from {} WHERE {} LIMIT {} ALLOW FILTERING'.format(cols, table, ' and '.join(selectors), maxrows)
        print("cql: {}".format(stmt))
        t0 = time.time()
        prep = self.session.prepare(stmt)
        res = self.session.execute(prep.bind(values))
        print("Executed in %s ms" % ((time.time()-t0)*1000))
        return res

    def get_clients(self, selectors, values, maxrows):
        return self.get_generic('clients', selectors, values, maxrows)

    def get_clients_by_owner(self, owner):
        prep = self.session.prepare('SELECT * from clients WHERE owner = ?')
        t0 = time.time()
        res = self.session.execute(prep.bind([owner]))
        print("Executed in %s ms" % ((time.time()-t0)*1000))
        return res

    def get_clients_by_scope(self, scope):
        prep = self.session.prepare('SELECT * from clients WHERE scopes CONTAINS ?')
        res = self.session.execute(prep.bind([scope]))
        return res

    def get_clients_by_scope_requested(self, scope):
        prep = self.session.prepare('SELECT * from clients WHERE scopes_requested CONTAINS ?')
        res = self.session.execute(prep.bind([scope]))
        return res

    def delete_client(self, clientid):
        prep = self.s_delete_client
        t0 = time.time()
        self.session.execute(prep.bind([clientid]))
        t0 = time.time()
        print("Executed in %s ms" % ((time.time()-t0)*1000))

    def get_token(self, tokenid):
        prep = self.s_get_token
        res = self.session.execute(prep.bind([tokenid]))
        if len(res) == 0:
            raise KeyError('No such token')
        return res[0]

    def get_user_by_id(self, userid):
        prep = self.s_get_user
        res = self.session.execute(prep.bind([userid]))
        if len(res) == 0:
            raise KeyError('No such user')
        return res[0]

    def get_user_by_userid_sec(self, sec):
        prep = self.session.prepare('SELECT * from users where userid_sec CONTAINS ?')
        res = self.session.execute(prep.bind([sec]))
        if len(res) == 0:
            raise KeyError('No such user')
        if len(res) > 1:
            raise RuntimeError('inconsistent database')
        return res[0]

    def get_apigk(self, id):
        prep = self.s_get_apigk
        res = self.session.execute(prep.bind([id]))
        if len(res) == 0:
            raise KeyError('No such apigk')
        apigk = res[0]
        parse_apigk(apigk)
        return apigk

    def get_apigks(self, selectors, values, maxrows):
        return [parse_apigk(gk) for gk in self.get_generic('apigk', selectors, values, maxrows)]

    def delete_apigk(self, id):
        prep = self.s_delete_apigk
        self.session.execute(prep.bind([id]))

    def insert_apigk(self, apigk):
        prep = self.session.prepare('INSERT INTO apigk (id, created, descr, endpoints, expose, httpscertpinned, name, owner, requireuser, scopedef, status, trust, updated) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
        self.session.execute(prep.bind([apigk['id'],
                                        apigk['created'],
                                        apigk['descr'],
                                        apigk['endpoints'],
                                        json.dumps(apigk['expose']),
                                        apigk['httpscertpinned'],
                                        apigk['name'], apigk['owner'],
                                        apigk['requireuser'],
                                        json.dumps(apigk['scopedef']),
                                        apigk['status'],
                                        json.dumps(apigk['trust']),
                                        apigk['updated']]))

    def get_client_logo(self, clientid):
        res = self.session.execute(self.s_get_client_logo.bind([clientid]))
        if len(res) == 0:
            raise KeyError('no such client')
        return res[0]['logo'], res[0]['updated']

    def get_apigk_logo(self, gkid):
        res = self.session.execute(self.s_get_apigk_logo.bind([gkid]))
        if len(res) == 0:
            raise KeyError('no such client')
        return res[0]['logo'], res[0]['updated']

    def save_logo(self, table, itemid, data, updated):
        prep = self.session.prepare('INSERT INTO {} (id, logo, updated) VALUES (?, ?, ?)'.format(table))
        self.session.execute(prep.bind([itemid, data, updated]))

    def get_authorizations(self, userid):
        return self.session.execute(self.s_get_authorizations.bind([userid]))

    def delete_token(self, token):
        return self.session.execute(self.s_delete_token.bind([token]))

    def delete_authorization(self, userid, clientid):
        self.session.execute(self.s_delete_authorization.bind([userid, clientid]))
        prep = self.session.prepare('SELECT access_token FROM oauth_tokens WHERE userid = ? AND clientid = ? ALLOW FILTERING')
        for token in self.session.execute(prep.bind([userid, clientid])):
            tokenid = token['access_token']
            self.log.debug('deleting token', token=tokenid)
            self.delete_token(tokenid)

    def get_group(self, groupid):
        prep = self.s_get_group
        res = self.session.execute(prep.bind([groupid]))
        if len(res) == 0:
            raise KeyError('No such group')
        return res[0]

    def delete_group(self, groupid):
        prep = self.s_delete_group
        self.session.execute(prep.bind([groupid]))

    def insert_group(self, group):
        prep = self.session.prepare('INSERT INTO groups (id, created, descr, name, owner, updated, public) VALUES (?, ?, ?, ?, ?, ?, ?)')
        self.session.execute(prep.bind([
            group['id'],
            group['created'],
            group['descr'],
            group['name'],
            group['owner'],
            group['updated'],
            group['public'],
        ]))

    def get_group_logo(self, groupid):
        res = self.session.execute(self.s_get_group_logo.bind([groupid]))
        if len(res) == 0:
            raise KeyError('no such group')
        return res[0]['logo'], res[0]['updated']

    def get_groups(self, selectors, values, maxrows):
        return self.get_generic('groups', selectors, values, maxrows)

    def get_group_members(self, groupid):
        prep = self.session.prepare('SELECT * FROM group_members WHERE groupid=?')
        return self.session.execute(prep.bind([groupid]))

    def add_group_member(self, groupid, userid, mtype, status):
        prep = self.session.prepare('INSERT INTO group_members (groupid, userid, type, status) values (?,?,?,?)')
        return self.session.execute(prep.bind([groupid, userid, mtype, status]))

    def set_group_member_status(self, groupid, userid, status):
        prep = self.session.prepare('INSERT INTO group_members (groupid, userid, status) values (?,?,?)')
        return self.session.execute(prep.bind([groupid, userid, status]))

    def del_group_member(self, groupid, userid):
        prep = self.session.prepare('DELETE FROM group_members WHERE groupid = ? AND userid = ?')
        return self.session.execute(prep.bind([groupid, userid]))

    def get_membership_data(self, groupid, userid):
        prep = self.session.prepare('SELECT * FROM group_members WHERE groupid=? AND userid=?')
        return self.session.execute(prep.bind([groupid, userid]))

    def get_group_memberships(self, userid, mtype, status, maxrows):
        selectors = ['userid = ?']
        values = [userid]
        if not mtype is None:
            selectors.append('type = ?')
            values.append(mtype)
        if not status is None:
            selectors.append('status = ?')
            values.append(status)
        return self.get_generic('group_members', selectors, values, maxrows)
