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
RETRY_CODES = frozenset((403, 408, 429, 500, 502, 503, 504))


def opener():
    """Opener with a cookie jar, the site redirects in a loop without one."""
    jar = http.cookiejar.CookieJar()
    built = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
    built.addheaders = [('User-Agent', BROWSER)]
    return built


def read_page(reader, url, timeout=60, waits=RETRY_WAITS):
    """The page as text, None on a 404; transient failures are retried, then raised."""
    for attempt in range(len(waits) + 1):
        try:
            return reader.open(url, timeout=timeout).read().decode('utf-8', 'replace')
        except urllib.error.HTTPError as error:
            if error.code == 404:
                return None
            if error.code not in RETRY_CODES or attempt == len(waits):
                raise
            problem = 'HTTP %d' % error.code
        except (urllib.error.URLError, socket.timeout, ConnectionError,
                http.client.HTTPException) as error:
            if attempt == len(waits):
                raise
            problem = str(error) or error.__class__.__name__
        print('  %s: %s, retry in %d s' % (url, problem, waits[attempt]), flush=True)
        time.sleep(waits[attempt])
    return None
