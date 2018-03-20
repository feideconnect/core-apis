from collections import defaultdict, deque
import datetime
from email.mime.text import MIMEText
import email.utils
import functools
from functools import wraps
import hashlib
import json
import logging
from queue import Queue, Empty
import re
import smtplib
import threading
from threading import Lock
import time
import traceback
import unicodedata
from urllib.parse import urlparse
import uuid
import ssl

import blist
import cassandra.util
from cassandra.auth import PlainTextAuthProvider
import statsd
import pytz
from aniso8601 import parse_datetime
from pyramid.httpexceptions import HTTPBadRequest, HTTPNotModified

__local = threading.local()


PRIV_PLATFORM_ADMIN = "priv_platform_admin"


def init_request_id():
    __local.log_request_id = uuid.uuid4()


def request_id():
    if hasattr(__local, 'log_request_id'):
        return __local.log_request_id
    return None


def set_request_id(new):
    __local.log_request_id = new


def now():
    return datetime.datetime.now(tz=pytz.UTC)


def timestamp_adapter(d):
    if isinstance(d, datetime.datetime):
        return d
    return parse_datetime(d)


def format_datetime(dt):
    dt = dt.astimezone(pytz.UTC).replace(tzinfo=None)
    dt = dt.replace(microsecond=0)
    return dt.isoformat() + 'Z'


class CustomEncoder(json.JSONEncoder):
    def default(self, obj): # pylint: disable=method-hidden
        if isinstance(obj, datetime.datetime):
            return format_datetime(obj)
        if isinstance(obj, uuid.UUID):
            return str(obj)
        if isinstance(obj, blist.sortedset):
            return list(obj)
        if isinstance(obj, cassandra.util.SortedSet):
            return list(obj)
        if isinstance(obj, set):
            return list(obj)
        if isinstance(obj, Exception):
            return str(obj)
        # Let the base class default method raise the TypeError
        return json.JSONEncoder.default(self, obj)


class LogMessage(object):
    def __init__(self, message, _base, **kwargs):
        self.message = message
        args = _base.copy()
        args.update(kwargs)
        self.args = args
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
        return '"message": "{}"'.format(self.message)


class LogWrapper(object):
    clsbase = {}

    def __init__(self, name, **base):
        self._base = base
        self.l = logging.getLogger(name)

    @property
    def base(self):
        base = LogWrapper.clsbase.copy()
        base.update(self._base)
        return base

    @classmethod
    def add_defaults(cls, **kwargs):
        cls.clsbase.update(kwargs)

    def debug(self, msg, **kwargs):
        self.l.debug(LogMessage(msg, self.base, **kwargs))

    def warn(self, msg, **kwargs):
        self.l.warning(LogMessage(msg, self.base, **kwargs))

    def error(self, msg, **kwargs):
        self.l.error(LogMessage(msg, self.base, **kwargs))

    def info(self, msg, **kwargs):
        self.l.info(LogMessage(msg, self.base, **kwargs))

    def exception(self, msg, **kwargs):
        exception = traceback.format_exc()
        self.error(msg, exception=exception, **kwargs)


class DebugLogFormatter(logging.Formatter):
    def format(self, record):
        t = record.created
        secs = int(t)
        msecs = int((t - secs) * 1000)
        ts = time.strftime('%Y-%m-%dT%H:%M:%S', time.gmtime(secs)) + '.%03dZ' % msecs
        if not isinstance(record.msg, LogMessage):
            record.msg = LogMessage(record.msg % record.args, LogWrapper.clsbase)

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

        def __exit__(self, exc_type, exc_value, exc_traceback):
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
        self.log = LogWrapper('dataporten.ratelimit')
        self.nwatched = int(1./maxshare + 0.5)
        self.recents = deque([None] * self.nwatched)
        self.counts = defaultdict(lambda: 0)
        self.buckets = defaultdict(lambda: LeakyBucket(capacity, rate))

    def check_rate(self, remote_addr):
        client = remote_addr
        accepted = not self.buckets[client].full()
        self.log.debug("check_rate", src_ip=client, accepted=accepted)
        if accepted:
            self.buckets[client].add()
            oldclient = self.recents.popleft()
            if oldclient:
                self.counts[oldclient] -= 1
                if self.counts[oldclient] <= 0:
                    self.log.debug("bucket deleted",
                                   src_ip=oldclient,
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


def www_authenticate(realm, error=None, description=None, authtype="Bearer"):
    if error is not None:
        template = '{} realm="{}", error="{}", error_description="{}"'
        return template.format(authtype, realm, error, description)
    return '{} realm="{}"'.format(authtype, realm)


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


def get_token(request):
    return request.environ.get('FC_TOKEN', None)


def get_userid(request):
    try:
        return request.environ['FC_USER']['userid']
    except (KeyError, TypeError):
        return None


def get_user(request):
    return request.environ.get('FC_USER', None)


def get_feideids(user):
    return set((id.split(':', 1)[1]
                for id in user['userid_sec']
                if id.startswith('feide:') and '@' in id))


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


def get_logo_bytes(request):
    if 'logo' in request.POST:
        input_file = request.POST['logo'].file
    else:
        input_file = request.body_file_seekable
    input_file.seek(0)
    return input_file.read()


def get_max_replies(request):
    max_replies = request.params.get('max_replies', None)
    if max_replies is not None:
        try:
            max_replies = int(max_replies)
        except ValueError:
            raise HTTPBadRequest()
    return max_replies


def public_userinfo(user):
    userid = None
    for sec in user['userid_sec']:
        if sec.startswith('p:'):
            userid = sec
    try:
        name = user['name'][user['selectedsource']]
    except (KeyError, TypeError):
        name = 'Unknown user'
    return {
        'id': userid,
        'name': name
    }


def preferred_email(user):
    pairs = user.get('email', {})
    if not pairs:
        return None
    try:
        addr = pairs[user['selectedsource']]
    except KeyError:
        addr = None
    if not addr:
        try:
            addrs = [val for val in pairs.values() if val]
            addr = addrs[0]
        except IndexError:
            addr = None
    return addr


def public_orginfo(org):
    return {
        'id': org['id'],
        'name': org['name'],
    }


def json_normalize(data):
    return json.loads(json.dumps(data, cls=CustomEncoder))


def userinfo_for_log(user):
    return {
        'name': user.get('name', {}).get(user['selectedsource'], "User without name"),
        'userid': user['userid'],
    }


# Raises exception if filename is given, but open fails
def json_load(filename, fallback):
    if filename:
        with open(filename) as fh:
            return json.load(fh)
    else:
        return fallback


def get_platform_admins(filename):
    contents = json_load(filename, fallback={"platformadmins": []})
    return contents.get('platformadmins', [])


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

        def __exit__(self, exc_type, exc_value, exc_traceback):
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
    if isinstance(data, dict):
        res = {}
        for key, value in data.items():
            res[key] = pick_lang(chooser, value)
        return res
    if isinstance(data, list):
        return [pick_lang(chooser, v) for v in data]
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
        except Exception as ex: # pylint: disable=broad-except
            LogWrapper('coreapis.utils.failsafe').warn('suppressed error', exception=ex,
                                                       exception_class=ex.__class__.__name__)
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


class EmailNotifier(object):
    def __init__(self, settings):
        self.sender = settings.get('sender', None)
        self.mta = settings.get('mta', None)
        self.enabled = False
        self.log = LogWrapper('coreapis.emailnotifier')
        if settings.get('enabled', '') == 'true':
            if self.sender and self.mta:
                self.enabled = True
            else:
                self.log.debug('Insufficient email settings', sender=self.sender, mta=self.mta)

    def notify(self, recipient, subject, text):
        if not self.enabled:
            self.log.debug('Email notifications not enabled',
                           recipient=recipient, subject=subject, text=text)
            return
        msg = MIMEText(text)
        msg['Subject'] = subject
        msg['From'] = self.sender
        msg['To'] = recipient
        msg['Date'] = email.utils.formatdate(localtime=True)
        msg['Message-ID'] = email.utils.make_msgid()
        smtp = smtplib.SMTP(self.mta)
        smtp.sendmail(self.sender, [recipient], msg.as_string())
        smtp.quit()
        self.log.debug('Email notification sent',
                       recipient=recipient, subject=subject, text=text)


def log_token(token):
    if isinstance(token, uuid.UUID):
        token = str(token)
    if isinstance(token, str):
        data = token.encode('UTF-8')
    else:
        data = token
    return hashlib.md5(data).hexdigest()


def valid_url(value):
    url = urlparse(value)
    if url.scheme not in ('http', 'https'):
        return None
    if url.netloc == '':
        return None
    if url.username or url.password:
        return None
    return url


def is_valid_char(c, valid_categories):
    category = unicodedata.category(c)
    if category not in valid_categories:
        return False
    if category == 'Zs' and c != " ":
        return False
    if category == 'Cc' and c != "\n":
        return False
    if c == '<' or c == '>':
        return False
    return True


def valid_string(value, allow_newline, minlength, maxlength):
    if not isinstance(value, str):
        raise ValueError()
    value = value.strip()
    normalized = unicodedata.normalize("NFKC", value)
    valid_categories = {
        'LC', 'Ll', 'Lm', 'Lo', 'Lt', 'Lu',  # Letters
        'Nd', 'Nl', 'No',  # Numbers
        'Pd', 'Pe', 'Pf', 'Pi', 'Po', 'Ps',  # Punctuation
        'Sc', 'Sk', 'Sm', 'So',  # Symbols
        'Zs',  # Space
    }
    if allow_newline:
        valid_categories.add('Cc')
    value = ''.join([c for c in normalized if is_valid_char(c, valid_categories)])
    value = re.sub(r'  +', ' ', value)
    if allow_newline:
        value = re.sub(r' ?\n ?', '\n', value)
        value = re.sub(r'\n\n\n+', '\n\n', value)
    l = len(value)
    if l < minlength or l > maxlength:
        raise ValueError()
    return value


def valid_name(value):
    return valid_string(value, False, 3, 90)


def valid_description(value):
    return valid_string(value, True, 0, 5000)


def get_cassandra_authz(config):
    authkeys = ['cassandra_username', 'cassandra_password', 'cassandra_cacerts']
    authz = {key: config[key] for key in authkeys if key in config}
    if len(authz) == len(authkeys):
        return authz
    elif authz:
        missing_authz = set(authkeys) - set(authz.keys())
        raise ValidationError('Missing ' + ', '.join(missing_authz))
    else:
        return None


def get_cassandra_cluster_args(contact_points, connection_class, authz):
    cluster_args = dict(contact_points=contact_points,
                        connection_class=connection_class)
    if authz:
        username = authz['cassandra_username']
        password = authz['cassandra_password']
        ca_certs = authz['cassandra_cacerts']
        cluster_args.update(
            ssl_options=dict(ca_certs=ca_certs, cert_reqs=ssl.CERT_REQUIRED,
                             ssl_version=ssl.PROTOCOL_TLSv1),
            auth_provider=PlainTextAuthProvider(username=username, password=password)
        )
    return cluster_args
