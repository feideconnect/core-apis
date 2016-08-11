#!/usr/bin/env python
import argparse
import json
import logging
import os
import re
import sys
from configparser import SafeConfigParser
import requests
import valideer as V
from cassandra.cluster import Cluster
import cassandra
from coreapis.utils import LogWrapper, get_cassandra_cluster_args

DESCRIPTION = """Sync organizations from Feide API to Dataporten.
Input can be from a file or a URL. One of these must be given.
If URL, feideapi_token_secret must also be given.

cassandra_contact_points and cassandra_keyspace are taken from
config file.
"""
URL = 'https://api.feide.no/2/'
ORGPATH = 'org/all/full'
SUBSPATH = 'sp/{}/full'


class CassandraClient(object):
    def __init__(self, log, contact_points, keyspace, config):
        self.log = log
        if config['cassandra_username']:
            options = get_cassandra_cluster_args(contact_points, None, config)
        else:
            options = dict(contact_points=contact_points)
        cluster = Cluster(**options)
        self.session = cluster.connect(keyspace)
        self.session.default_consistency_level = cassandra.ConsistencyLevel.LOCAL_QUORUM
        stmt = """
            INSERT INTO "organizations" (id, kindid, realm, type, organization_number, name)
            VALUES (?, ?, ?, ?, ?,?)
        """
        self.s_insert_org = self.session.prepare(stmt)
        stmt = """
            INSERT INTO "roles" (feideid, orgid, role)
            VALUES (?, ?, ?)
        """
        self.s_insert_role = self.session.prepare(stmt)
        self.s_get_orgs = 'SELECT "id", "kindid" from "organizations"'
        stmt = 'SELECT id from "organizations" WHERE kindid = ?'
        self.s_get_orgs_by_kindid = self.session.prepare(stmt)
        stmt = 'SELECT * from "roles" WHERE orgid = ?'
        self.s_get_roles_by_orgid = self.session.prepare(stmt)
        stmt = 'DELETE FROM "organizations" WHERE id = ?'
        self.s_delete_organization = self.session.prepare(stmt)
        stmt = 'DELETE FROM "roles" WHERE feideid = ? AND orgid = ?'
        self.s_delete_role = self.session.prepare(stmt)
        stmt = "UPDATE organizations set services = services {} {{'{}'}} where id = '{}'"
        self.s_update_service = stmt

    def insert_org(self, org):
        self.session.execute(self.s_insert_org.bind([
            org['id'], org['kindid'], org['realm'], org['type'],
            org['organization_number'], org['name']]))

    def insert_role(self, role):
        self.session.execute(self.s_insert_role.bind([
            role['feideid'], role['orgid'], role['role']]))

    def get_orgs(self):
        return self.session.execute(self.s_get_orgs)

    def get_orgs_by_kindid(self, kindid):
        return self.session.execute(self.s_get_orgs_by_kindid.bind([kindid]))

    def get_roles_by_orgid(self, orgid):
        return self.session.execute(self.s_get_roles_by_orgid.bind([orgid]))

    def delete_organization(self, orgid):
        self.session.execute(self.s_delete_organization.bind([orgid]))

    def delete_role(self, feideid, orgid):
        self.session.execute(self.s_delete_role.bind([feideid, orgid]))

    def update_service(self, orgid, service, add):
        oper = '+' if add else '-'
        stmt = self.s_update_service.format(oper, service, orgid)
        self.session.execute(stmt)


def make_orgid(feideorg):
    suffix = 'kind-{}'.format(feideorg['id'])
    realm = feideorg.get('realm')
    if realm:
        suffix = realm
    else:
        orgno = feideorg.get('organization_number')
        if orgno:
            suffix = 'org-{}'.format(orgno)
    return 'fc:org:{}'.format(suffix)


def make_org(feideorg, orgid):
    return {
        'id': orgid,
        'kindid': int(feideorg['id']),
        'realm': feideorg['realm'],
        'type': set(feideorg['type']),
        'organization_number': feideorg['organization_number'],
        'name': feideorg['name']
    }


def rolekey(role):
    return '#'.join([role['feideid'], role['orgid']])


def adapt_orgno(organization_number):
    if organization_number:
        rexp = r"^([a-z]{2})?(\d{9,})$"
        match = re.search(rexp, organization_number.lower())
        if match:
            country = match.group(1)
            if not country:
                country = 'no'
            return '{}{}'.format(country, match.group(2))
        else:
            raise V.ValidationError('Wrong format: {}'.format(organization_number))
    else:
        return None


def is_dataporten_subscriber(feideorg, feidesubs):
    kindid = feideorg['id']
    return any([subscriber['id'] == kindid for subscriber in feidesubs['subscribers']])


class Syncer(object):
    def __init__(self, log, client, sync_exclude):
        self.log = log
        self.client = client
        self.sync_exclude = sync_exclude
        ko_schema = {
            '+id': V.AdaptTo(int),
            'realm': V.Nullable('string'),
            '+type': ['string'],
            'organization_number': V.AdaptBy(adapt_orgno),
            '+name': V.Object(),
            'contacts_admin': [V.Object()],
            'contacts_technical': [V.Object()],
            'contacts_mercantile': [V.Object()],
            # Not used in dataporten
            'servers': ['string'],
            'support_email': V.Nullable('string'),
            'support_phone': V.Nullable('string'),
            'support_web': V.Nullable('string'),
        }
        kor_schema = {
            '+eduPersonPrincipalName': 'string',
            # Not used in dataporten
            'id': V.AdaptTo(int),
            'name': V.Nullable('string'),
            'email': V.Nullable('string'),
        }
        with V.parsing(additional_properties=False):
            self.ko_validator = V.parse(ko_schema)
            self.kor_validator = V.parse(kor_schema)

    def roles_from_api(self, feideorg, orgid):
        rolenames = {
            'contacts_admin': 'admin',
            'contacts_technical': 'technical',
            'contacts_mercantile': 'mercantile'
        }
        contacts = {}
        for kindrole, apirole in rolenames.items():
            members = feideorg.get(kindrole, [])
            for member in members:
                try:
                    self.kor_validator.validate(member)
                except V.ValidationError:
                    self.log.debug("Failed role validation", orgid=orgid, member=member)
                    continue
                feideid = member['eduPersonPrincipalName']
                contacts.setdefault(feideid, set())
                contacts[feideid].add(apirole)
        for feideid, roles in contacts.items():
            yield {
                'feideid': feideid.lower(),
                'orgid': orgid,
                'role': roles
            }

    @staticmethod
    def roles_from_db(rows):
        for row in rows:
            yield {
                'feideid': row[0],
                'orgid': row[1],
                'role': row[2]
            }

    def drop_roles(self, orgid):
        roles = self.client.get_roles_by_orgid(orgid)
        for role in roles:
            self.client.delete_role(role[0], role[1])

    def prune_roles(self, newroles, oldroles):
        newkeys = {rolekey(nrole) for nrole in newroles}
        for orole in oldroles:
            if not rolekey(orole) in newkeys:
                self.log.info('Dropping role', feideid=orole['feideid'],
                              orgid=orole['orgid'])
                self.client.delete_role(orole['feideid'], orole['orgid'])

    def sync_roles(self, newroles, oldroles):
        for role in newroles:
            self.client.insert_role(role)
        self.prune_roles(newroles, oldroles)

    def drop_org(self, orgid):
        self.drop_roles(orgid)
        self.client.delete_organization(orgid)

    def drop_orgs(self, dropped_kindids):
        for kindid in dropped_kindids:
            orgs = self.client.get_orgs_by_kindid(kindid)
            if orgs:
                orgid = orgs[0][0]
                if orgid in self.sync_exclude:
                    self.log.info("Not dropping org on exclude list", orgid=orgid)
                else:
                    self.log.info("Dropping org", orgid=orgid)
                    self.drop_org(orgid)

    def load_orgs(self, feideorgs, feidesubs):
        for feideorg in feideorgs:
            try:
                ko_cooked = self.ko_validator.validate(feideorg)
                oldorgs = self.client.get_orgs_by_kindid(int(feideorg['id']))
                oldroles = []
                if oldorgs:
                    orgid = oldorgs[0][0]
                    rows = self.client.get_roles_by_orgid(orgid)
                    oldroles = list(self.roles_from_db(rows))
                else:
                    orgid = make_orgid(ko_cooked)
                if orgid in self.sync_exclude:
                    self.log.info("Skipping org on exclude list", orgid=orgid)
                    continue
                org = make_org(ko_cooked, orgid)
            except V.ValidationError:
                self.log.warning("Failed org validation", id=feideorg['id'],
                                 organization_number=feideorg['organization_number'],
                                 realm=feideorg['realm'], name=feideorg['name'])
                continue
            roles = list(self.roles_from_api(ko_cooked, org['id']))
            try:
                self.client.insert_org(org)
            except TypeError as ex:
                self.log.error("Exception inserting org", exception=ex, org=org)
                continue
            self.sync_roles(roles, oldroles)
            self.client.update_service(org['id'], 'auth',
                                       is_dataporten_subscriber(feideorg, feidesubs))

    def sync_orgs(self, feideorgs, feidesubs):
        known_kindids = {org[1] for org in self.client.get_orgs()}
        kindids = {int(feideorg['id']) for feideorg in feideorgs}
        dropped_kindids = known_kindids.difference(kindids)
        self.load_orgs(feideorgs, feidesubs)
        self.drop_orgs(dropped_kindids)


class ApiError(requests.exceptions.RequestException):
    def __init__(self, message):
        super(ApiError, self).__init__(message)
        self.message = message


def get_json_from_url(url, token):
    headers = {
        'Authorization': 'Bearer {}'.format(token),
        'Accept-Encoding': 'gzip, deflate',
        'Accept': 'application/json',
    }
    req = requests.get(url, headers=headers)
    if req.status_code != 200:
        req.raise_for_status()
    content_type = req.headers['content-type']
    if content_type != 'application/json':
        raise ApiError("Wrong content type: {}".format(content_type))
    return req.json()


def parse_config(filename):
    parser = SafeConfigParser()
    parser.read(filename)
    return {
        'contact_points': parser['DEFAULT']['cassandra_contact_points'].split(', '),
        'keyspace': parser['DEFAULT']['cassandra_keyspace'],
        'sync_exclude': parser['DEFAULT'].get('feideapi_sync_exclude', '').split(','),
        'cassandra_cacerts': parser['DEFAULT'].get('cassandra_cacerts', None),
        'cassandra_username': parser['DEFAULT'].get('cassandra_username', None),
    }


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=DESCRIPTION)
    parser.add_argument('-c', '--config', default="production.ini",
                        help="Config file to use")
    parser.add_argument('-u', '--url', default=URL,
                        help='Feide API URL')
    parser.add_argument('-x', '--feideapi-token-secret',
                        help='Feide API token secret')
    parser.add_argument('-p', '--cassandra-password',
                        help='Cassandra password')
    parser.add_argument('-i', '--infile', type=argparse.FileType('r'),
                        help='Input file with organization data')
    parser.add_argument('-s', '--subsfile', type=argparse.FileType('r'),
                        help='Input file with subscription data')
    parser.add_argument('-d', '--delete-missing', action='store_true',
                        help='Delete organizations from Dataporten when missing from Feide API')
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    parser.add_argument('--sp-id', type=int, help="Kind id of service provider of the install to sync with")
    return parser.parse_args()


def fail(message):
    print(message)
    sys.exit(2)


def main():
    log = LogWrapper('sync_orgs')
    args = parse_args()
    config = parse_config(args.config)
    if args.verbose or os.environ.get('SYNC_ORGS_VERBOSE'):
        logging.basicConfig(level=logging.DEBUG)
    else:
        log.l.setLevel(logging.INFO)
        logging.basicConfig(level=logging.CRITICAL)
    log.info("Sync started")
    config['cassandra_password'] = args.cassandra_password
    session = CassandraClient(log, config['contact_points'], config['keyspace'], config)
    syncer = Syncer(log, session, sync_exclude=config['sync_exclude'])
    if args.infile:
        feideorgs = json.load(args.infile)
        feidesubs = json.load(args.subsfile)
    elif args.url:
        if args.feideapi_token_secret:
            orgurl = args.url + ORGPATH
            subsurl = args.url + SUBSPATH.format(args.sp_id)
            feideorgs = get_json_from_url(orgurl, args.feideapi_token_secret)
            feidesubs = get_json_from_url(subsurl, args.feideapi_token_secret)
        else:
            fail('Feide API token must be given in config file')
    else:
        fail("One of INFILE or URL/TOKEN must be given")
    if args.delete_missing:
        syncer.sync_orgs(feideorgs, feidesubs)
    else:
        syncer.load_orgs(feideorgs, feidesubs)
    log.info("Sync done")

if __name__ == "__main__":
    main()
