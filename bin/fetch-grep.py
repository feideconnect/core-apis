#! /usr/bin/env python
import requests
from coreapis.utils import parse_datetime
from coreapis.cassandra_client import Client
from configparser import SafeConfigParser
import argparse

DESCRIPTION = "Fetch grep code data from udir and store in cassandra"
BASE_URL = 'http://data.udir.no/kl06/'
TYPES = [
    'programomraader',
    'aarstrinn',
    'utdanningsprogram',
]


def fetch(base_url, greptype):
    url = "{}{}.json".format(base_url, greptype)
    resp = requests.get(url)
    return resp.json()


def parse_multilang(data):
    res = {}
    for entry in data:
        text = entry['verdi']
        origlang = entry['noekkel']
        if '#' in origlang:
            lang = origlang.split('#', 1)[1]
            if len(lang) != 3:
                raise ValueError('unhandled language code: {}'.format(origlang))
        elif origlang == 'default':
            lang = origlang
        else:
            raise ValueError('unhandled language code: {}'.format(origlang))
        res[lang] = text
    return res


def parse_entry(data, grep_type):
    return {
        'last_changed': parse_datetime(data['sist-endret']),
        'code': data['kode'],
        'id': data['id'],
        'title': parse_multilang(data['tittel']),
        'type': grep_type,
    }


def parse_args():
    parser = argparse.ArgumentParser(description=DESCRIPTION)
    parser.add_argument('--config', default="production.ini",
                        help="Config file to use")
    parser.add_argument('--url', default=BASE_URL, help="Base url to fetch data from")

    return parser.parse_args()


def parse_config(filename):
    parser = SafeConfigParser()
    parser.read(filename)
    return {
        'contact_points': parser['DEFAULT']['cassandra_contact_points'].split(', '),
        'keyspace': parser['DEFAULT']['cassandra_keyspace'],
    }


def main():
    args = parse_args()
    config = parse_config(args.config)
    session = Client(config['contact_points'], config['keyspace'])

    for grep_type in TYPES:
        data = fetch(args.url, grep_type)
        for entry in data:
            session.insert_grep_code(parse_entry(entry, grep_type))


if __name__ == '__main__':
    main()
