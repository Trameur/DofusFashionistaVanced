"""Logging filters for fashionsite."""

import hashlib
import logging

from django.core.cache import cache


class RateLimitedErrorFilter(logging.Filter):
    """Pass each unique error signature at most once per RATE_LIMIT_SECONDS.

    Attached to the `mail_admins` handler so we don't flood the inbox when the
    same exception fires hundreds of times. Signature is derived from the
    exception class and the bottom frame (file:lineno), same bug = same
    signature regardless of incidental data (user id, URL params, etc.).
    """

    RATE_LIMIT_SECONDS = 3600

    def filter(self, record):
        try:
            signature = self._signature(record)
            cache_key = f'error_email_sent:{signature}'
            if cache.get(cache_key):
                return False
            cache.set(cache_key, True, self.RATE_LIMIT_SECONDS)
        except Exception:
            # The rate-limiter must never swallow an error email: a cache hiccup
            # (or a malformed record) should make us send, not go blind to a
            # production error. Fail open.
            return True
        return True

    def _signature(self, record):
        if record.exc_info:
            exc_type, _exc_value, tb = record.exc_info
            while tb and tb.tb_next:
                tb = tb.tb_next
            if tb is not None:
                sig_str = (
                    f"{exc_type.__name__}:"
                    f"{tb.tb_frame.f_code.co_filename}:{tb.tb_lineno}"
                )
            else:
                sig_str = exc_type.__name__
        else:
            sig_str = record.getMessage()
        return hashlib.md5(sig_str.encode('utf-8', errors='replace')).hexdigest()
