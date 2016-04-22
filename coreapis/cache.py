import time
from coreapis.utils import LogWrapper


class Cache(object):
    def __init__(self, expiry, logname):
        self.log = LogWrapper(logname)
        self.data = dict()
        self.expiry = expiry

    def _set(self, key, value):
        self.data[key] = (time.time(), value)
        return value

    def _update(self, key, getter):
        return self._set(key, getter())

    def get(self, key, getter):
        if key not in self.data:
            self.log.debug('cache miss', key=key)
            return self._update(key, getter)
        ts, cached = self.data.get(key)
        if ts + self.expiry < time.time():
            self.log.debug('cache expired', key=key)
            return self._update(key, getter)
        return cached
