import logging
import json
import datetime
import uuid
import blist
import statsd
import time
import pytz
from collections import deque


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


class LogMessage(object):
    def __init__(self, message, **kwargs):
        self.message = message
        self.args = kwargs

    def __str__(self):
        rest = json.dumps(self.args, cls=CustomEncoder)
        rest = rest[1:-1]
        return '"message": "{}", {}'.format(self.message, rest)


class LogWrapper(object):
    def __init__(self, name):
        self.l = logging.getLogger(name)

    def debug(self, msg, **kwargs):
        self.l.debug(LogMessage(msg, **kwargs))

    def warn(self, msg, **kwargs):
        self.l.warn(LogMessage(msg, **kwargs))

    def error(self, msg, **kwargs):
        self.l.error(LogMessage(msg, **kwargs))

    def info(self, msg, **kwargs):
        self.l.info(LogMessage(msg, **kwargs))


class DebugLogFormatter(logging.Formatter):
    def format(self, record):
        if type(record.msg) != LogMessage:
            record.msg = '"message": "{}"'.format(str(record.msg))
        return super(DebugLogFormatter, self).format(record)


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


class RateLimiter(object):
    # Requests are let through if client is not among last 1/maxshare
    # clients served, or if at least mingap ms have passed since last time.
    # If necessary, we can add a token bucket to accomodate bursts.
    def __init__(self, maxshare, mingap):
        self.log = LogWrapper('feideconnect.ratelimit')
        self.nwatched = int (1./maxshare + 0.5)
        self.mingap = datetime.timedelta(milliseconds=mingap)
        self.recents = deque([ (None, None) ] * self.nwatched)

    def check_rate(self, remote_addr):
        client = remote_addr
        ts = now()
        found = False
        for recent in self.recents:
            if recent[0] == client:
                found = True
        if found:
            gap = ts - recent[1]
            accepted = (gap > self.mingap)
            self.log.debug("%s in recents, gap: %s, accepted: %s" % (client, gap, accepted))
        else:
            accepted = True
            self.log.debug("%s not in recents, accepted: %s" % (client, accepted))
        if accepted:
            self.recents.popleft()
            self.recents.append((client, ts))
        return accepted


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


def www_authenticate(realm, error=None, description=None):
    if error is not None:
        template = 'Bearer realm="{}", error="{}", error_description="{}"'
        return template.format(realm, error, description)
    else:
        return 'Bearer realm="{}"'.format(realm)
