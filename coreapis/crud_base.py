import io
import uuid
import warnings

import requests
from PIL import Image
import valideer as V

from coreapis.utils import (
    now, ValidationError, AlreadyExistsError, LogWrapper, get_feideids, public_userinfo,
    public_orginfo, preferred_email, PRIV_PLATFORM_ADMIN)

LOGO_SIZE = 128, 128
warnings.simplefilter('error', Image.DecompressionBombWarning)


def cache(data, key, fetch):
    if key in data:
        return data[key]
    value = fetch(key)
    data[key] = value
    return value


class CrudControllerBase(object):
    schema = {}
    platformadmins = []
    platformadmin_attrs = []
    platformadmin_attrs_update = []
    protected_attrs = []
    protected_attrs_update = []
    public_attrs = []

    def __init__(self, maxrows, objtype="target"):
        self.maxrows = maxrows
        self.log = LogWrapper('crud_base')
        self.objtype = objtype
        self.groupengine_base_url = None
        self.session = None

    def allowed_attrs(self, attrs, operation, privileges):
        protected_attrs = list(self.protected_attrs)
        if PRIV_PLATFORM_ADMIN not in privileges:
            protected_attrs += self.platformadmin_attrs
        if operation != 'add':
            protected_attrs += self.protected_attrs_update
            if PRIV_PLATFORM_ADMIN not in privileges:
                protected_attrs += self.platformadmin_attrs_update
        try:
            return {key: val for key, val in attrs.items() if key not in protected_attrs}
        except AttributeError:
            raise ValidationError('payload must be a json object')

    def validate(self, item):
        validator = V.parse(self.schema, additional_properties=False)
        try:
            adapted = validator.validate(item)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for key in self.schema:
            if not key.startswith('+') and key not in adapted:
                adapted[key] = None
        return adapted

    def get(self, objid):
        raise NotImplementedError

    def exists(self, itemid):
        try:
            self.get(itemid)
            return True
        except KeyError:
            return False

    def get_my_groups(self, token):
        headers = {'Authorization': 'Bearer {}'.format(token)}
        url = '{}/groups/me/groups'.format(self.groupengine_base_url)
        self.log.debug('get_my_groups', url=url)
        response = requests.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    def get_my_groupids(self, token):
        if not token:
            return []
        return (group['id'] for group in self.get_my_groups(token))

    def get_owner(self, itemid):
        try:
            item = self.get(itemid)
            return item['owner']
        except KeyError:
            return None

    def _insert(self, objid, privileges):
        raise NotImplementedError

    def add(self, item, user, privileges):
        userid = user['userid']
        self.log.debug('add item', userid=userid)
        try:
            item = self.validate(item)
        except V.ValidationError as ex:
            self.log.debug('item is invalid: {}'.format(ex))
            raise ValidationError(ex)
        self.log.debug('item is ok')
        if item['id'] is not None:
            itemid = item['id']
            if self.exists(itemid):
                self.log.debug('item already exists', itemid=itemid)
                raise AlreadyExistsError('item already exists')
        else:
            item['id'] = uuid.uuid4()
        if item['owner'] is None:
            item['owner'] = userid
        ts_now = now()
        item['created'] = ts_now
        item['updated'] = ts_now
        self._insert(item, privileges)
        return item

    def validate_update(self, itemid, attrs):
        self.log.debug('validate update item', itemid=itemid)
        try:
            item = self.get(itemid)
            for k, v in attrs.items():
                if k not in ['created', 'updated']:
                    item[k] = v
            item = self.validate(item)
        except V.ValidationError as ex:
            self.log.debug('item is invalid: {}'.format(ex))
            raise ValidationError(ex)
        item['updated'] = now()
        return item

    def update(self, itemid, attrs, user, privileges):
        self.log.debug('update item', itemid=itemid)
        item = self.validate_update(itemid, attrs)
        self._insert(item, privileges)
        return item

    def _save_logo(self, objid, data, updated):
        raise NotImplementedError

    def update_logo(self, itemid, data):
        fake_file = io.BytesIO(data)
        try:
            image = Image.open(fake_file)
        except OSError:
            raise ValidationError('image format not supported')
        except (Image.DecompressionBombWarning,
                Image.DecompressionBombError):
            raise ValidationError('Bad image')
        image.thumbnail(LOGO_SIZE)
        fake_output = io.BytesIO()
        image.save(fake_output, format='PNG')
        updated = now()
        self._save_logo(itemid, fake_output.getbuffer(), updated)

    def is_platform_admin(self, user):
        if user is None:
            return False
        for feideid in get_feideids(user):
            if feideid in self.platformadmins:
                return True
        return False

    def is_org_admin(self, user, org):
        if user is None:
            return False
        for identity in user['userid_sec']:
            if identity.startswith('feide:'):
                identity = identity.lower()
            if self.session.is_org_admin(identity, org):
                return True
        return False

    def is_admin(self, user, org):
        return self.is_platform_admin(user) or self.is_org_admin(user, org)

    def get_privileges(self, user):
        privileges = list()
        if self.is_platform_admin(user):
            privileges.append(PRIV_PLATFORM_ADMIN)
        return privileges

    def get_public_info(self, target, users=None, orgs=None):
        if users is None:
            users = {}
        if orgs is None:
            orgs = {}
        pubtarget = {attr: target[attr] for attr in self.public_attrs}
        try:
            def get_user(userid):
                return public_userinfo(self.session.get_user_by_id(userid))

            def get_org(orgid):
                return public_orginfo(self.session.get_org(orgid))
            pubtarget['owner'] = cache(users, target['owner'], get_user)
            org = target.get('organization', None)
            if org:
                pubtarget['organization'] = cache(orgs, org, get_org)
        except KeyError:
            logdata = dict(userid=target['owner'])
            logdata[self.objtype + 'id'] = target['id']
            self.log.warn('{} owner does not exist in users table'.format(self.objtype), **logdata)
            pubtarget['owner'] = {
                'id': '',
                'name': 'Unknown user',
            }
        return pubtarget

    def get_admin_contact(self, target):
        contact = target.get('admin_contact', '')
        if contact:
            return contact
        try:
            owner_uuid = target.get('owner')
            contact = preferred_email(self.session.get_user_by_id(owner_uuid))
        except KeyError:
            logdata = dict(userid=target['owner'])
            logdata[self.objtype + 'id'] = target['id']
            self.log.warn('{} owner does not exist in users table'.format(self.objtype), **logdata)
        return contact
