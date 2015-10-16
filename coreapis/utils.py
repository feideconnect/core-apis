import logging
import json
import datetime
import uuid
import blist
import statsd
import time
import pytz
import functools
from functools import wraps
from collections import defaultdict, deque
import threading
from aniso8601 import parse_datetime
from queue import Queue, Empty
from threading import Lock
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotModified
from urllib.parse import urlparse
import hashlib

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

    def rest(self):
        rest = json.dumps(self.args, cls=CustomEncoder)
        rest = rest[1:-1]
        return rest.strip()

    def __str__(self):
        rest = self.rest()
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
        t = record.created
        secs = int(t)
        msecs = int((t - secs) * 1000)
        ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(secs)) + '.%03dZ' % msecs
        if type(record.msg) != LogMessage:
            record.msg = LogMessage(record.msg)

        obj = {
            'time': ts,
            'loglevel': record.levelname,
            'logger': record.name,
            'message': "{} {}".format(record.msg.message, record.msg.rest()),
        }
        obj.update(record.msg.args)
        return json.dumps(obj, cls=CustomEncoder)


class Timer(object):
    def __init__(self, server, port, prefix, log_results, pool):
        self.pool = pool(create=lambda: statsd.StatsClient(server, port, prefix=prefix))
        self.log_results = log_results
        if self.log_results:
            self.log = LogWrapper('coreapis.timers')

    class Context(object):
        def __init__(self, parent, name, log_results):
            self.parent = parent
            self.name = name
            self.log_results = log_results

        def __enter__(self):
            self.t0 = time.time()

        def __exit__(self, type, value, traceback):
            duration = (time.time() - self.t0) * 1000
            self.parent.register(self.name, duration)

    def time(self, name):
        return self.Context(self, name, self.log_results)

    def register(self, name, duration):
        if self.log_results:
            self.log.debug('Timed {} to {} ms'.format(name, duration),
                           counter=name, timing_ms=duration)
        with self.pool.item() as client:
            client.timing(name, duration)


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
        self.log = LogWrapper('coreapis.timers')

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
        self.timer.register(timername, duration)
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


class ForbiddenError(RuntimeError):
    def __init__(self, message):
        super(ForbiddenError, self).__init__(message)
        self.message = message


class ResourceError(RuntimeError):
    def __init__(self, message):
        super(ResourceError, self).__init__(message)
        self.message = message


def get_userid(request):
    try:
        return request.environ['FC_USER']['userid']
    except:
        return None


def get_user(request):
    return request.environ.get('FC_USER', None)


def get_feideids(user):
    return set((id.split(':', 1)[1] for id in user['userid_sec'] if id.startswith('feide:') and '@' in id))


def get_feideid(user):
    feideids = get_feideids(user)
    if not feideids:
        raise RuntimeError('could not find feide id')
    feideid = feideids.pop()
    return feideid


def get_payload(request):
    try:
        return request.json_body
    except ValueError:
        raise HTTPBadRequest('missing or malformed json body')


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


def public_orginfo(org):
    return {
        'id': org['id'],
        'name': org['name'],
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


class translatable(dict):
    def pick_lang(self, chooser):
        """Returns a translated string from a dict of lang -> string mappings
        based on the accept_language headers of the request. If there is
        no accept-language header or there is no overlap between accepted
        and available language returns an arbitary language

        """
        lang = chooser(self.keys())
        if not lang:
            for a in ('nb', 'nn', 'en', 'se'):
                if a in self:
                    lang = a
                    break
        if not lang:
            lang = list(self.keys())[0]
        return self[lang]


def pick_lang(chooser, data):
    if isinstance(data, translatable):
        return data.pick_lang(chooser)
    elif isinstance(data, dict):
        res = {}
        for key, value in data.items():
            res[key] = pick_lang(chooser, value)
        return res
    elif isinstance(data, list):
        return [pick_lang(chooser, v) for v in data]
    else:
        return data


def accept_language_matcher(request, data):
    lang = None
    if request.accept_language:
        lang = request.accept_language.best_match(data)
    return lang


def translation(func):
    @wraps(func)
    def wrapper(request):
        data = func(request)
        if request.params.get('translate', 'true') == 'false':
            return data
        chooser = lambda data: accept_language_matcher(request, data)
        return pick_lang(chooser, data)
    return wrapper


def failsafe(func):
    @wraps(func)
    def wrapped(func, *args, **kwargs):
        try:
            return func(*args, **kwargs)
        except:
            logging.warn('suppressed error')
            return None
    return functools.partial(wrapped, func)


class LogoRenderer(object):
    def __init__(self, info):
        self.info = info

    def __call__(self, value, system):
        request = system['request']
        logo, updated, fallback_file = value[:3]
        content_type = 'image/png'
        if len(value) > 3:
            content_type = value[3]
        if logo is None:
            with open(fallback_file, 'rb') as fh:
                logo = fh.read()
        updated = updated.replace(microsecond=0)
        if request.if_modified_since and request.if_modified_since >= updated:
            raise HTTPNotModified
        response = request.response
        response.charset = None
        response.content_type = content_type
        response.cache_control = 'public, max-age=3600'
        response.last_modified = updated
        return logo


def log_token(token):
    if isinstance(token, uuid.UUID):
        data = token.bytes
    elif isinstance(token, str):
        data = token.encode('UTF-8')
    else:
        data = token
    return hashlib.md5(data).hexdigest()


def valid_url(value):
    url = urlparse(value)
    if url.scheme not in ('http', 'https'):
        return False
    if url.netloc == '':
        return False
    if url.username or url.password:
        return False
    return True
