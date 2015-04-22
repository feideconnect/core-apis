#!/usr/bin/env python
import argparse
import json
import logging
import re
import requests
import sys
import valideer as V
from cassandra.cluster import Cluster
from configparser import SafeConfigParser
from coreapis.utils import LogWrapper

DESCRIPTION = """Sync organizations from Feide API to Connect.
Input can be from a file or a URL. One of these must be given.

cassandra_contact_points, cassandra_keyspace and feideapi_token_secret are
taken from config file.
"""
URL = 'https://api.feide.no/2/org/all/full'


class CassandraClient(object):
    def __init__(self, log, contact_points, keyspace, use_eventlets=False):
        self.log = log
        connection_class = None
        if use_eventlets:
            from cassandra.io.eventletreactor import EventletConnection
            connection_class = EventletConnection
            log.debug("Using eventlet based cassandra connection")
        cluster = Cluster(
            contact_points=contact_points,
            connection_class=connection_class,
        )
        self.session = cluster.connect(keyspace)
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


def make_orgid(kindorg):
    suffix = 'kind-{}'.format(kindorg['id'])
    realm = kindorg.get('realm')
    if realm:
        suffix = realm
    else:
        orgno = kindorg.get('organization_number')
        if orgno:
            suffix = 'org-{}'.format(orgno)
    return 'fc:org:{}'.format(suffix)


def make_org(kindorg, orgid):
    return {
        'id': orgid,
        'kindid': int(kindorg['id']),
        'realm': kindorg['realm'],
        'type': set(kindorg['type']),
        'organization_number': kindorg['organization_number'],
        'name': kindorg['name']
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


class Syncer(object):
    def __init__(self, log, client):
        self.log = log
        self.client = client
        ko_schema = {
            '+id': V.AdaptTo(int),
            'realm': V.Nullable('string'),
            '+type': ['string'],
            'organization_number': V.AdaptBy(adapt_orgno),
            '+name': V.Object(),
            'contacts_admin': [V.Object()],
            'contacts_technical': [V.Object()],
            'contacts_mercantile': [V.Object()],
            # Not used in connect
            'support_email': V.Nullable('string'),
            'support_phone': V.Nullable('string'),
            'support_web': V.Nullable('string'),
        }
        kor_schema = {
            '+eduPersonPrincipalName': 'string',
            # Not used in connect
            'id': V.AdaptTo(int),
            'name': V.Nullable('string'),
            'email': V.Nullable('string'),
        }
        with V.parsing(additional_properties=False):
            self.ko_validator = V.parse(ko_schema)
            self.kor_validator = V.parse(kor_schema)

    def roles_from_api(self, kindorg, orgid):
        rolenames = {
            'contacts_admin': 'admin',
            'contacts_technical': 'technical',
            'contacts_mercantile': 'mercantile'
        }
        contacts = {}
        for kindrole, apirole in rolenames.items():
            members = kindorg.get(kindrole, [])
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
                'feideid': feideid,
                'orgid': orgid,
                'role': roles
            }

    def roles_from_db(self, rows):
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

    def drop_org(self, orgid):
        self.drop_roles(orgid)
        self.client.delete_organization(orgid)

    def drop_orgs(self, dropped_kindids):
        for kindid in dropped_kindids:
            orgs = self.client.get_orgs_by_kindid(kindid)
            if len(orgs) > 0:
                orgid = orgs[0][0]
                self.log.info("Dropping org", orgid=orgid)
                self.drop_org(orgid)

    def load_orgs(self, kindorgs):
        for kindorg in kindorgs:
            try:
                ko_cooked = self.ko_validator.validate(kindorg)
                oldorgs = self.client.get_orgs_by_kindid(int(kindorg['id']))
                oldroles = []
                if len(oldorgs) > 0:
                    orgid = oldorgs[0][0]
                    rows = self.client.get_roles_by_orgid(orgid)
                    oldroles = list(self.roles_from_db(rows))
                else:
                    orgid = make_orgid(ko_cooked)
                org = make_org(ko_cooked, orgid)
            except V.ValidationError:
                self.log.warning("Failed org validation", id=kindorg['id'],
                                 organization_number=kindorg['organization_number'],
                                 realm=kindorg['realm'], name=kindorg['name'])
                continue
            roles = list(self.roles_from_api(ko_cooked, org['id']))
            try:
                self.client.insert_org(org)
            except TypeError as ex:
                self.log.error("Exception inserting org", exception=ex, org=org)
                continue
            for role in roles:
                self.client.insert_role(role)
            self.prune_roles(roles, oldroles)

    def sync_orgs(self, kindorgs):
        known_kindids = {org[1] for org in self.client.get_orgs()}
        kindids = {int(kindorg['id']) for kindorg in kindorgs}
        dropped_kindids = known_kindids.difference(kindids)
        self.load_orgs(kindorgs)
        self.drop_orgs(dropped_kindids)


class ApiError(requests.exceptions.RequestException):
    def __init__(self, message):
        super(requests.exceptions.RequestException, self).__init__(message)
        self.message = message


def get_orgs_from_url(url, token):
    headers = {
        'Authorization': 'Bearer {}'.format(token),
        'Accept-Encoding': 'gzip, deflate',
        'Accept': 'application/json',
    }
    r = requests.get(url, headers=headers)
    if r.status_code != 200:
        r.raise_for_status()
    content_type = r.headers['content-type']
    if content_type != 'application/json':
        raise ApiError("Wrong content type: {}".format(content_type))
    return r.json()


def parse_config(filename):
    parser = SafeConfigParser()
    parser.read(filename)
    return {
        'contact_points': parser['DEFAULT']['cassandra_contact_points'].split(', '),
        'keyspace': parser['DEFAULT']['cassandra_keyspace'],
        'token': parser['DEFAULT']['feideapi_token_secret'],
    }


def parse_args():
    parser = argparse.ArgumentParser(formatter_class=argparse.RawDescriptionHelpFormatter,
                                     description=DESCRIPTION)
    parser.add_argument('-c', '--config', default="production.ini",
                        help="Config file to use")
    parser.add_argument('-u', '--url', default=URL,
                        help='Feide API URL')
    parser.add_argument('-i', '--infile', type=argparse.FileType('r'),
                        help='Input file with organization data')
    parser.add_argument('-d', '--delete-missing', action='store_true',
                        help='Delete organizations from Connect when missing from Feide API')
    parser.add_argument("-v", "--verbose", help="increase output verbosity",
                        action="store_true")
    return parser.parse_args()


def fail(message):
    print(message)
    sys.exit(2)


def main():
    log = LogWrapper('sync_orgs')
    args = parse_args()
    config = parse_config(args.config)
    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    session = CassandraClient(log, config['contact_points'], config['keyspace'])
    syncer = Syncer(log, session)
    if args.infile:
        kindorgs = json.load(args.infile)
    elif args.url:
        if config['token']:
            kindorgs = get_orgs_from_url(args.url, config['token'])
        else:
            fail('Feide API token must be given in config file')
    else:
        fail("One of INFILE or URL/TOKEN must be given")
    if args.delete_missing:
        syncer.sync_orgs(kindorgs)
    else:
        syncer.load_orgs(kindorgs)

if __name__ == "__main__":
    main()
