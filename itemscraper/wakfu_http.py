"""Pages of the Wakfu encyclopedia, with a cookie jar and retries on transient errors."""

from __future__ import annotations

import http.client
import http.cookiejar
import socket
import time
import urllib.error
import urllib.request

BROWSER = ('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
           ' (KHTML, like Gecko) Chrome/120 Safari/537.36')
RETRY_WAITS = (5, 15, 45)
DNS_WAITS = (5, 15, 45, 120, 300)
RETRY_CODES = frozenset((403, 408, 429, 500, 502, 503, 504))


def opener():
    """Opener with a cookie jar, the site redirects in a loop without one."""
    jar = http.cookiejar.CookieJar()
    built = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    built.addheaders = [('User-Agent', BROWSER)]
    return built


def retry_wait(error, used, waits=RETRY_WAITS, codes=RETRY_CODES):
    """Seconds to wait before retrying, None when the error is final or its waits ran out."""
    if isinstance(error, urllib.error.HTTPError):
        if error.code not in codes:
            return None
        kind, ladder = 'other', waits
    elif isinstance(error, urllib.error.URLError) and isinstance(error.reason, socket.gaierror):
        kind, ladder = 'dns', DNS_WAITS
    elif isinstance(error, (urllib.error.URLError, socket.timeout, ConnectionError,
                            http.client.HTTPException)):
        kind, ladder = 'other', waits
    else:
        return None
    count = used.get(kind, 0)
    if count >= len(ladder):
        return None
    used[kind] = count + 1
    return ladder[count]


def read_page(reader, url, timeout=60, waits=RETRY_WAITS):
    """The page as text, None on a 404; transient failures are retried, then raised."""
    used = {}
    while True:
        try:
            return reader.open(url, timeout=timeout).read().decode('utf-8', 'replace')
        except (urllib.error.URLError, socket.timeout, ConnectionError,
                http.client.HTTPException) as error:
            if isinstance(error, urllib.error.HTTPError) and error.code == 404:
                return None
            wait = retry_wait(error, used, waits)
            if wait is None:
                raise
            if isinstance(error, urllib.error.HTTPError):
                problem = 'HTTP %d' % error.code
            else:
                problem = str(error) or error.__class__.__name__
        print('  %s: %s, retry in %d s' % (url, problem, wait), flush=True)
        time.sleep(wait)
