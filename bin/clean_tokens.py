#! /usr/bin/env python
import argparse
from configparser import SafeConfigParser

from coreapis.cassandra_client import Client
from coreapis.utils import now
from coreapis import scopes

DESCRIPTION = "Check and clean oauth_tokens from database"


def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('--config', default="production.ini",
                        help="Config file to use")
    parser.add_argument('--clean-expired', action='store_true', help="delete expired tokens")
    parser.add_argument('--clean-corrupt', action='store_true', help="delete corrupt tokens")
    parser.add_argument('--verbose', '-v', action='store_true', help="verbose output")

    return parser.parse_args()


def parse_config(filename):
    parser = SafeConfigParser()
    parser.read(filename)
    return {
        'contact_points': parser['DEFAULT']['cassandra_contact_points'].split(', '),
        'keyspace': parser['DEFAULT']['cassandra_keyspace'],
    }


def verbose(args, msg):
    if args.verbose:
        print(msg)


def main():
    args = parse_args()
    config = parse_config(args.config)
    session = Client(config['contact_points'], config['keyspace'])
    expired = []
    corrupt = []
    valid = 0
    for token in session.session.execute('SELECT * from oauth_tokens'):
        tscopes = token.get('scope', set())
        if scopes is None:
            tscopes = set()
        apis = {s.split('_')[1] for s in tscopes if scopes.is_gkscopename(s)}
        if not token.get('validuntil', None):
            verbose(args, 'Token {} has no validuntil'.format(token['access_token']))
            corrupt.append(token['access_token'])
        elif token['apigkid'] != '' and token['subtokens'] is not None:
            verbose(args, 'Token {} has both apigkid and subtokens set'.format(token['access_token']))
            corrupt.append(token['access_token'])
        elif any((s for s in token['scope'] if s.startswith('gk_'))) and token['subtokens'] is None:
            verbose(args, 'Token {} has gk scopes but no subtokens set'.format(token['access_token']))
            corrupt.append(token['access_token'])
        elif len(scopes.filter_missing_mainscope(tscopes)) != len(tscopes):
            verbose(args, 'Token {} has gk subscope but misses corresponding mainscope'.format(token['access_token']))
            corrupt.append(token['access_token'])
        elif any((api for api in apis if api not in token['subtokens'])):
            verbose(args, 'Token {} misses subtokens for some apis'.format(token['access_token']))
            corrupt.append(token['access_token'])
        elif not token['scope']:
            verbose(args, 'Token {} has no scopes'.format(token['access_token']))
            corrupt.append(token['access_token'])
        elif token['validuntil'] < now():
            verbose(args, 'Token {} expired at {}'.format(token['access_token'], token['validuntil']))
            expired.append(token['access_token'])
        else:
            valid += 1

    print("Found {} valid, {} expired and {} corrupt tokens".format(valid, len(expired), len(corrupt)))

    if args.clean_expired:
        print("Cleaning expired tokens")
        for access_token in expired:
            session.delete_token(access_token)
        print("Done")

    if args.clean_corrupt:
        print("Cleaning corrupt tokens")
        for access_token in corrupt:
            session.delete_token(access_token)
        print("Done")

if __name__ == '__main__':
    main()
