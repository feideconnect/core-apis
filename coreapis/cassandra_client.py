#! /usr/bin/env python
from cassandra.cluster import Cluster
from cassandra.query import dict_factory
from datetime import datetime
import pytz
import time


def create_session(contact_points, keyspace):
    cluster = Cluster(
        contact_points=contact_points
    )
    session = cluster.connect(keyspace)
    session.row_factory = dict_factory
    return session


def now():
    return datetime.now(tz=pytz.UTC)


def insert_client(session, id, client_secret, name, descr,
                  redirect_uri, scopes, scopes_requested, status,
                  type, owner):
    ts = now()
    prep = session.prepare('INSERT INTO client (id, client_secret, name, descr, redirect_uri, scopes, scopes_requested, status, type, created, updated, owner) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)')
    session.execute(prep.bind([id, client_secret, name, descr,
                               redirect_uri, scopes, scopes_requested,
                               status, type, ts, ts, owner]))


def get_client_by_id(session, clientid):
    prep = session.prepare('SELECT * FROM client WHERE id = ?')
    res = session.execute(prep.bind([clientid]))
    if len(res) == 0:
        raise KeyError('No such client')
    return res[0]


def get_clients_by_owner(session, owner):
    prep = session.prepare('SELECT * from client WHERE owner = ?')
    t0 = time.time()
    res = session.execute(prep.bind([owner]))
    print("Executed in %s ms" % ((time.time()-t0)*1000))
    return res


def get_clients_by_scope(session, scope):
    prep = session.prepare('SELECT * from client WHERE scopes CONTAINS ?')
    res = session.execute(prep.bind([scope]))
    return res


def get_token(session, tokenid):
    prep = session.prepare('SELECT * FROM oauth_tokens WHERE access_token = ?')
    res = session.execute(prep.bind([tokenid]))
    if len(res) == 0:
        raise KeyError('No such token')
    return res[0]
