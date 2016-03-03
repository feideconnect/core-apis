import argparse
import os
import sys
import time
from cassandra.cluster import Cluster, NoHostAvailable


DESCRIPTION = 'Initialize Cassandra keyspace'

TPL_DROP = 'drop keyspace {}'
TPL_EXISTS = "SELECT * FROM system.schema_keyspaces WHERE keyspace_name = '{}'"
TPL_CREATE = 'CREATE KEYSPACE IF NOT EXISTS {} WITH replication = {}'
REPLICATION = {'class': 'SimpleStrategy', 'replication_factor': 1}


class KeyspaceInitializer(object):
    def __init__(self, node, keyspace):
        self.node = node
        self.keyspace = keyspace
        self.cluster = None
        self.session = None
        self.error = None
        self.connect()

    def connect(self):
        nodes = [self.node]
        self.cluster = Cluster(nodes)
        try:
            self.session = self.cluster.connect()
        except NoHostAvailable as e:
            self.error = e

    def exec_cql(self, stmt, msg, timeout=-1):
        if msg:
            print(msg, '... ', end='', flush=True)
        if timeout > 0:
            res = self.session.execute(stmt, timeout=timeout)
        else:
            res = self.session.execute(stmt)
        if msg:
            print('done')
        return res

    def keyspace_exists(self):
        res = self.exec_cql(TPL_EXISTS.format(self.keyspace), None)
        return len(list(res)) > 0

    def drop_keyspace(self):
        self.exec_cql(TPL_DROP.format(self.keyspace), 'dropping keyspace ' + self.keyspace,
                      timeout=30.)

    def create_keyspace(self):
        self.exec_cql(TPL_CREATE.format(self.keyspace, REPLICATION),
                      'creating keyspace ' + self.keyspace)


def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('-f', '--force', dest='force', action='store_true',
                        help="drop and recreate keyspace")
    parser.add_argument('-w', '--wait-for-db', dest='wait_for_db', action='store_true',
                        help="wait for db to become ready")
    parser.add_argument('-m', '--max-wait', type=int, help="max secs to wait for db")
    parser.set_defaults(force=False, wait_for_db=False, max_wait=100)
    return parser.parse_args()


def main():
    db_node = os.environ.get('DP_CASSANDRA_TEST_NODE', 'cassandra-test-coreapis')
    db_keyspace = os.environ.get('DP_CASSANDRA_TEST_KEYSPACE', 'test_coreapis')
    args = parse_args()
    now = time.time()
    if args.wait_for_db:
        latest = now + args.max_wait
    else:
        latest = now - 1
    while True:
        kinit = KeyspaceInitializer(db_node, db_keyspace)
        if kinit.session is None and time.time() < latest:
            print('database not ready, waiting ...')
            time.sleep(5)
            continue
        else:
            break
    if kinit.session is None:
        print(kinit.error)
        sys.exit(1)
    exists = kinit.keyspace_exists()
    if exists:
        if args.force:
            kinit.drop_keyspace()
            exists = False
        else:
            print('keyspace already exists, nothing to do')
    if not exists:
        kinit.create_keyspace()

if __name__ == '__main__':
    main()
