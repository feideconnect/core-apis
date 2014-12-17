import logging
import json
import datetime
import uuid
import blist
import statsd
import time
import pytz


def now():
    return datetime.datetime.now(tz=pytz.UTC)


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


class Timer(object):
    def __init__(self, server, port, prefix):
        self.client = statsd.StatsClient(server, port, prefix=prefix)

    class Context(object):
        def __init__(self, client, name):
            self.client = client
            self.name = name

        def __enter__(self):
            self.t0 = time.time()

        def __exit__(self, type, value, traceback):
            self.client.timing(self.name, (time.time() - self.t0) * 1000)

    def time(self, name):
        return self.Context(self.client, name)


class RequestTimingTween(object):
    def __init__(self, handler, registry):
        self.handler = handler
        self.registry = registry
        self.timer = registry.settings.timer

    def __call__(self, request):
        t0 = time.time()
        response = self.handler(request)
        t1 = time.time()
        route = request.matched_route
        if route:
            routename = route.name
        else:
            routename = '__unknown__'
        timername = 'request.{}.{}'.format(routename, request.method)
        logging.debug("Sending stats for %s", timername)
        self.timer.client.timing(timername, (t1 - t0) * 1000)
        return response