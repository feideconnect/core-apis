#! /usr/bin/env python
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
import time
import json


class Client(object):
    def __init__(self, contact_points, keyspace):
        cluster = Cluster(
            contact_points=contact_points
        )
        self.session = cluster.connect(keyspace)
        self.session.row_factory = dict_factory
        self.s_get_client = self.session.prepare('SELECT * FROM clients WHERE id = ?')
        self.s_delete_client = self.session.prepare('DELETE FROM clients WHERE id = ?')
        self.s_get_token = self.session.prepare('SELECT * FROM oauth_tokens WHERE access_token = ?')
        self.s_get_user = self.session.prepare('SELECT * FROM users WHERE userid = ?')
        self.s_get_apigk = self.session.prepare('SELECT * FROM apigk WHERE id = ?')

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

    def get_clients(self, selectors, values, maxrows):
        if len(selectors) != len(values):
            raise KeyError('Selectors and values not same length')
        if len(selectors) == 0:
            stmt = 'SELECT * from clients LIMIT {}'.format(maxrows)
        else:
            stmt = 'SELECT * from clients WHERE {} LIMIT {} ALLOW FILTERING'.format(' and '.join(selectors), maxrows)
        print("cql: {}".format(stmt))
        prep = self.session.prepare(stmt)
        res = self.session.execute(prep.bind(values))
        t0 = time.time()
        print("Executed in %s ms" % ((time.time()-t0)*1000))
        return res

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
        backend_data = res[0]
        backend_data['expose'] = json.loads(backend_data['expose'])
        backend_data['trust'] = json.loads(backend_data['trust'])
        return backend_data
