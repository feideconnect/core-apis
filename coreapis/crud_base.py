from coreapis.utils import now, ValidationError, AlreadyExistsError, LogWrapper, get_feideid
import uuid
import valideer as V
import io
from PIL import Image

LOGO_SIZE = 128, 128


class CrudControllerBase(object):
    schema = {}

    def __init__(self, maxrows):
        self.maxrows = maxrows
        self.log = LogWrapper('crud_base')

    def validate(self, item):
        validator = V.parse(self.schema, additional_properties=False)
        try:
            adapted = validator.validate(item)
        except V.ValidationError as ex:
            raise ValidationError(str(ex))
        for key in self.schema.keys():
            if not key.startswith('+') and key not in adapted:
                adapted[key] = None
        return adapted

    def exists(self, itemid):
        try:
            self.get(itemid)
            return True
        except KeyError:
            return False

    def get_owner(self, itemid):
        try:
            item = self.get(itemid)
            return item['owner']
        except:
            return None

    def add(self, item, userid):
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
        self._insert(item)
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

    def update(self, itemid, attrs):
        self.log.debug('update item', itemid=itemid)
        item = self.validate_update(itemid, attrs)
        self._insert(item)
        return item

    def update_logo(self, itemid, data):
        fake_file = io.BytesIO(data)
        try:
            image = Image.open(fake_file)
        except OSError:
            raise ValidationError('image format not supported')
        image.thumbnail(LOGO_SIZE)
        fake_output = io.BytesIO()
        image.save(fake_output, format='PNG')
        updated = now()
        self._save_logo(itemid, fake_output.getbuffer(), updated)

    def is_org_admin(self, user, org):
        feideid = get_feideid(user)
        return self.session.is_org_admin(feideid, org)
