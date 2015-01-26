#! /usr/bin/env python
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
import time
import json
import datetime
import pytz


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
    def __init__(self, contact_points, keyspace):
        cluster = Cluster(
            contact_points=contact_points
        )
        self.session = cluster.connect(keyspace)
        self.session.row_factory = datetime_hack_dict_factory
        self.s_get_client = self.session.prepare('SELECT * FROM clients WHERE id = ?')
        self.s_delete_client = self.session.prepare('DELETE FROM clients WHERE id = ?')
        self.s_get_token = self.session.prepare('SELECT * FROM oauth_tokens WHERE access_token = ?')
        self.s_get_user = self.session.prepare('SELECT * FROM users WHERE userid = ?')
        self.s_get_apigk = self.session.prepare('SELECT * FROM apigk WHERE id = ?')
        self.s_delete_apigk = self.session.prepare('DELETE FROM apigk WHERE id = ?')

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
        if len(selectors) == 0:
            stmt = 'SELECT * from {} LIMIT {}'.format(table, maxrows)
        else:
            stmt = 'SELECT * from {} WHERE {} LIMIT {} ALLOW FILTERING'.format(table, ' and '.join(selectors), maxrows)
        print("cql: {}".format(stmt))
        prep = self.session.prepare(stmt)
        res = self.session.execute(prep.bind(values))
        t0 = time.time()
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
