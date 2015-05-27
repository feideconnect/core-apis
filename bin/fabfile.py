from fabric.api import local, run, settings, task
from os import path

BACKUP_ROOT = "/var/lib/fcbackup"
BACKUP_DIR_TMPL = "fc-backup-{}"

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
    return path.join(backup_root, BACKUP_DIR_TMPL.format(tag))


def mkbdir(backup_root, tag):
    bdir = backupdir(backup_root, tag)
    local('mkdir -p {}'.format(bdir))
    return bdir


def run_cqlsh(command):
    node = CASSANDRA_NODES[0]
    with settings(host_string=node):
        outercmd = "cqlsh -k {} -e '{}' {}".format(KEYSPACE, command, node)
        res = run(outercmd, pty=False, quiet=True)
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


@task
def backup_schema(tag='foo', backup_root=BACKUP_ROOT):
    bdir = mkbdir(backup_root, tag)
    fname = 'schema.sql'
    with open(path.join(bdir, fname), 'w') as f:
        f.write(get_schema())


@task
def backup_table(tag='foo', backup_root=BACKUP_ROOT, table=TABLES[0]):
    bdir = mkbdir(backup_root, tag)
    fname = '{}.csv'.format(table)
    with open(path.join(bdir, fname), 'w') as f:
        f.write(get_table(table))


@task
def backup_tables(tag='foo', backup_root=BACKUP_ROOT):
    for table in TABLES:
        backup_table(tag, backup_root, table)
