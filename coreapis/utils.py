import logging
import json
import datetime
import uuid
import blist


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, blist.sortedset):
            return list(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class LogWrapper(object):
    def __init__(self, name):
        self.l = logging.getLogger(name)

    def msg(self, msg, **kwargs):
        msg = {'message': msg}
        msg.update(kwargs)
        return json.dumps(msg, cls=CustomEncoder)

    def debug(self, msg, **kwargs):
        self.l.debug(self.msg(msg, **kwargs))

    def warn(self, msg, **kwargs):
        self.l.warn(self.msg(msg, **kwargs))

    def error(self, msg, **kwargs):
        self.l.error(self.msg(msg, **kwargs))

    def info(self, msg, **kwargs):
        self.l.info(self.msg(msg, **kwargs))
