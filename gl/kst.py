"""Fixed Korea Standard Time (UTC+9, no DST since 1988) helpers.

The original Linux runs used the OS local zone Asia/Seoul via time.localtime().
To make results identical on any OS / any local timezone, every KST conversion in
this package goes through these helpers, and engine28's module-level `time`
reference is replaced by KSTTime (see install_engine_time_shim)."""
import time as _time
import calendar as _calendar

KST_OFFSET_S = 9 * 3600


def localtime(secs=None):
    if secs is None:
        secs = _time.time()
    return _time.gmtime(secs + KST_OFFSET_S)


def fmt(ms, f='%Y-%m-%d %H:%M'):
    """epoch milliseconds -> KST string."""
    return _time.strftime(f, localtime(ms / 1000))


def parse(s):
    """'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM' (KST) -> epoch ms."""
    s = s.strip()
    for f in ('%Y-%m-%d %H:%M', '%Y-%m-%d'):
        try:
            st = _time.strptime(s, f)
            return int(_calendar.timegm(st) * 1000 - KST_OFFSET_S * 1000)
        except ValueError:
            pass
    raise ValueError('bad KST datetime %r (use YYYY-MM-DD or YYYY-MM-DD HH:MM)' % s)


class _KSTTimeModule:
    """Drop-in for the `time` module where localtime() means KST."""
    def __getattr__(self, name):
        return getattr(_time, name)

    @staticmethod
    def localtime(secs=None):
        return localtime(secs)


KSTTime = _KSTTimeModule()


def install_engine_time_shim():
    """engine28 computes month buckets with time.localtime(); force KST."""
    import engine28
    engine28.time = KSTTime
