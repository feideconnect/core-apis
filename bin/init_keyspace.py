import argparse
import os
import sys
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
        self.connect()
        metadata = self.cluster.metadata
        print('Connected to cluster: ' + metadata.cluster_name)
        print('Node:', self.node)

    def connect(self):
        nodes = [self.node]
        try:
            self.cluster = Cluster(nodes)
        except NoHostAvailable as e:
            print(e)
            sys.exit(1)
        self.session = self.cluster.connect()

    def exec_cql(self, stmt, msg):
        if msg:
            print(msg, '... ', end='', flush=True)
        res = self.session.execute(stmt)
        if msg:
            print('done')
        return res

    def keyspace_exists(self):
        res = self.exec_cql(TPL_EXISTS.format(self.keyspace), None)
        return len(list(res)) > 0

    def drop_keyspace(self):
        self.exec_cql(TPL_DROP.format(self.keyspace), 'dropping keyspace ' + self.keyspace)

    def create_keyspace(self):
        self.exec_cql(TPL_CREATE.format(self.keyspace, REPLICATION),
                      'creating keyspace ' + self.keyspace)


def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('-f', '--force', dest='force', action='store_true',
                        help="drop and recreate keyspace")
    parser.set_defaults(force=False)
    return parser.parse_args()


def main():
    db_node = os.environ.get('DP_CASSANDRA_TEST_NODE', 'cassandra-test-coreapis')
    db_keyspace = os.environ.get('DP_CASSANDRA_TEST_KEYSPACE', 'test_coreapis')
    kinit = KeyspaceInitializer(db_node, db_keyspace)
    args = parse_args()
    exists = kinit.keyspace_exists()
    if exists:
        if args.force:
            kinit.drop_keyspace()
            exists = False
        else:
            print('Keyspace already exists, nothing to do')
    if not exists:
        kinit.create_keyspace()

if __name__ == '__main__':
    main()
