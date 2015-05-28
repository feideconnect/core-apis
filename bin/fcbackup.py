from os import (path, makedirs)
import subprocess

BACKUP_ROOT = "/var/backups"
BACKUP_DIR = "fcbackup"

CASSANDRA_NODES = ['158.38.213.74', '158.38.213.91', '158.38.213.87']
KEYSPACE = 'feideconnect'
TABLES = [
    'organizations',
    'oauth_tokens',
    'clients',
    'grep_codes',
    'roles',
    'group_members',
    'apigk',
    'clients_counters',
    'userid_sec',
    'mandatory_clients',
    'groups',
    'oauth_authorizations',
    'users',
    'oauth_codes',

]


def backupdir(backup_root, tag):
    bdir = path.join(backup_root, BACKUP_DIR)
    if tag != '':
        bdir = '{}-{}'.format(bdir, tag)
    return bdir


def mkbdir(backup_root, tag):
    bdir = backupdir(backup_root, tag)
    if not path.exists(bdir):
        makedirs(bdir)
    return bdir


def run_cqlsh(command):
    node = CASSANDRA_NODES[0]
    outercmd = "cqlsh -k {} -e '{}' {}".format(KEYSPACE, command, node)
    res = subprocess.Popen(outercmd, shell=True, stdout=subprocess.PIPE).stdout.read()
    ret = []
    for line in res.splitlines():
        if line.find('rows exported in') == -1:
            ret.append(line)
    return ('\n').join(ret)


def get_schema():
    command = 'describe keyspace {};'.format(KEYSPACE)
    return run_cqlsh(command)


def get_table(tablename=TABLES[0]):
    command = 'copy {} to stdout;'.format(tablename)
    return run_cqlsh(command)


def backup_schema(backup_root=BACKUP_ROOT, tag=''):
    bdir = mkbdir(backup_root, tag)
    fname = 'schema.sql'
    with open(path.join(bdir, fname), 'w') as f:
        f.write(get_schema())


def backup_table(backup_root=BACKUP_ROOT, table=TABLES[0], tag=''):
    bdir = mkbdir(backup_root, tag)
    fname = '{}.csv'.format(table)
    with open(path.join(bdir, fname), 'w') as f:
        f.write(get_table(table))


def backup_tables(backup_root=BACKUP_ROOT, tag=''):
    for table in TABLES:
        backup_table(backup_root, table, tag)


if __name__ == '__main__':
    backup_schema()
    backup_tables()
