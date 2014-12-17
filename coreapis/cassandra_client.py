#! /usr/bin/env python
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
import time
from .utils import now


class Client(object):
    def __init__(self, contact_points, keyspace):
        cluster = Cluster(
            contact_points=contact_points
        )
        self.session = cluster.connect(keyspace)
        self.session.row_factory = dict_factory
        self.s_get_client = self.session.prepare('SELECT * FROM clients WHERE id = ?')
        self.s_get_token = self.session.prepare('SELECT * FROM oauth_tokens WHERE access_token = ?')
        self.s_get_user = self.session.prepare('SELECT * FROM users WHERE userid = ?')

    def insert_client(self, id, client_secret, name, descr,
                      redirect_uri, scopes, scopes_requested, status,
                      type, owner):
        ts = now()
        prep = self.session.prepare('INSERT INTO client (id, client_secret, name, descr, redirect_uri, scopes, scopes_requested, status, type, created, updated, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
        self.session.execute(prep.bind([id, client_secret, name, descr,
                                        redirect_uri, scopes, scopes_requested,
                                        status, type, ts, ts, owner]))

    def get_client_by_id(self, clientid):
        prep = self.s_get_client
        res = self.session.execute(prep.bind([clientid]))
        if len(res) == 0:
            raise KeyError('No such client')
        return res[0]

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
