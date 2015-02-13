import logging
import json
import datetime
import uuid
import blist
import statsd
import time
import pytz
from collections import defaultdict, deque
import threading
from aniso8601 import parse_datetime
from queue import Queue, Empty
from threading import Lock

__local = threading.local()


def init_request_id():
    __local.log_request_id = uuid.uuid4()


def request_id():
    if hasattr(__local, 'log_request_id'):
        return __local.log_request_id


def now():
    return datetime.datetime.now(tz=pytz.UTC)


def ts(d):
    if type(d) == datetime.datetime:
        return d
    else:
        return parse_datetime(d)


def format_datetime(dt):
    dt = dt.astimezone(pytz.UTC).replace(tzinfo=None)
    dt = dt.replace(microsecond=0)
    return dt.isoformat() + 'Z'


class CustomEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return format_datetime(obj)
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
        request = request_id()
        if request:
            self.args['request'] = request

    def __str__(self):
        rest = json.dumps(self.args, cls=CustomEncoder)
        rest = rest[1:-1]
        rest = rest.strip()
        if rest:
            return '"message": "{}", {}'.format(self.message, rest)
        else:
            return '"message": "{}"'.format(self.message)


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
            record.msg = LogMessage(record.msg)
        return super(DebugLogFormatter, self).format(record)


class Timer(object):
    def __init__(self, server, port, prefix, log_results):
        self.client = statsd.StatsClient(server, port, prefix=prefix)
        self.log_results = log_results

    class Context(object):
        def __init__(self, client, name, log_results):
            self.client = client
            self.name = name
            self.log_results = log_results

        def __enter__(self):
            self.t0 = time.time()

        def __exit__(self, type, value, traceback):
            duration = (time.time() - self.t0) * 1000
            if self.log_results:
                logging.debug('Timed {} to {} ms'.format(self.name, duration))
            self.client.timing(self.name, duration)

    def time(self, name):
        return self.Context(self.client, name, self.log_results)


class RateLimiter(object):
    # Requests are let through if client is not among last 1/maxshare
    # clients served, or if there is still room in the client's token bucket.
    def __init__(self, maxshare, capacity, rate):
        self.log = LogWrapper('feideconnect.ratelimit')
        self.nwatched = int(1./maxshare + 0.5)
        self.recents = deque([None] * self.nwatched)
        self.counts = defaultdict(lambda: 0)
        self.buckets = defaultdict(lambda: LeakyBucket(capacity, rate))

    def check_rate(self, remote_addr):
        client = remote_addr
        accepted = not self.buckets[client].full()
        self.log.debug("check_rate", client=client, accepted=accepted)
        if accepted:
            self.buckets[client].add()
            oldclient = self.recents.popleft()
            if oldclient:
                self.counts[oldclient] -= 1
                if self.counts[oldclient] <= 0:
                    self.log.debug("bucket deleted",
                                   client=oldclient,
                                   contents=self.buckets[oldclient].contents)
                    del self.buckets[oldclient]
                    del self.counts[oldclient]
            self.recents.append(client)
            self.counts[client] += 1
        return accepted


class LeakyBucket(object):
    def __init__(self, capacity, leak_rate):
        self.capacity = capacity
        self.leak_rate = leak_rate
        self.contents = 0
        self.ts = now()

    def add(self):
        self.contents += 1

    def full(self):
        self._update()
        return self.contents >= self.capacity

    def _update(self):
        newts = now()
        gap = newts - self.ts
        leakage = self.leak_rate * gap.total_seconds()
        self.ts = newts
        self.contents = max(0, self.contents - leakage)


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
        duration = (t1 - t0) * 1000
        if self.registry.settings.log_timings:
            logging.debug("Timed %s to %f ms", timername, duration)
        self.timer.client.timing(timername, duration)
        return response


def www_authenticate(realm, error=None, description=None):
    if error is not None:
        template = 'Bearer realm="{}", error="{}", error_description="{}"'
        return template.format(realm, error, description)
    else:
        return 'Bearer realm="{}"'.format(realm)


class ValidationError(RuntimeError):
    def __init__(self, message):
        super(ValidationError, self).__init__(message)
        self.message = message


class AlreadyExistsError(RuntimeError):
    def __init__(self, message):
        super(AlreadyExistsError, self).__init__(message)
        self.message = message


class UnauthorizedError(RuntimeError):
    def __init__(self, message):
        super(UnauthorizedError, self).__init__(message)
        self.message = message


def get_userid(request):
    try:
        return request.environ['FC_USER']['userid']
    except:
        return None


def get_user(request):
    return request.environ.get('FC_USER', None)


def public_userinfo(user):
    userid = None
    for sec in user['userid_sec']:
        if sec.startswith('p:'):
            userid = sec
    name = user['name'][user['selectedsource']]
    return {
        'id': userid,
        'name': name
    }


def json_normalize(data):
    return json.loads(json.dumps(data, cls=CustomEncoder))


class ResourcePool(object):
    def __init__(self, min_size=0, max_size=4, order_as_stack=False, create=None):
        self.create = create
        self.min_size = min_size
        self.max_size = max_size
        self.q = Queue(max_size)
        self.count = 0
        self.lock = Lock()

    def get(self):
        try:
            i = self.q.get(False)
            return i
        except Empty:
            pass
        create = False
        with self.lock:
            if self.count < self.max_size:
                self.count += 1
                create = True
        if create:
            return self.create()
        return self.q.get(True)

    def put(self, item):
        self.q.put(item)

    class Context(object):
        def __init__(self, pool):
            self.pool = pool

        def __enter__(self):
            self.item = self.pool.get()
            return self.item

        def __exit__(self, type, value, traceback):
            self.pool.put(self.item)

    def item(self):
        return self.Context(self)
