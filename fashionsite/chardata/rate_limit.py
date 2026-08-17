# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Counters for the limits that have to hold across the whole site.

Failed logins and password reset mails were counted in the cache. The cache here
is local memory, one per gunicorn worker, so a pool of four multiplied every
ceiling by four and a reload forgot the counts. These live in one row per key
instead, which every worker reads and writes.

    if hits('login-fail-user:bob', 900) >= 10:  ...
    note_hit('login-fail-user:bob', 900)
    clear_hits('login-fail-user:bob')

A window is the number of seconds a count is worth: a row older than that starts
again from zero rather than being pruned on a schedule nobody runs.
"""
import datetime

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

# Rows nobody has touched for a day are dead weight, whatever their window was.
STALE_AFTER = datetime.timedelta(days=1)


def _fresh(row, window):
    return timezone.now() - row.window_start < datetime.timedelta(seconds=window)


def hits(key, window):
    """How many times this key was noted inside its window."""
    from chardata.models import RateCounter
    row = RateCounter.objects.filter(key=key[:190]).first()
    if row is None or not _fresh(row, window):
        return 0
    return row.count


def note_hit(key, window):
    """Count one more, and answer the count including it."""
    from chardata.models import RateCounter
    key = key[:190]
    now = timezone.now()
    row = RateCounter.objects.filter(key=key).first()
    if row is None:
        try:
            with transaction.atomic():
                RateCounter.objects.create(key=key, window_start=now, count=1)
            _prune()
            return 1
        except IntegrityError:
            # Another worker created the same key between the read and the
            # write; fall through and increment what it created.
            row = RateCounter.objects.filter(key=key).first()
            if row is None:
                return 1
    if not _fresh(row, window):
        RateCounter.objects.filter(pk=row.pk).update(window_start=now, count=1)
        return 1
    RateCounter.objects.filter(pk=row.pk).update(count=F('count') + 1)
    return row.count + 1


def clear_hits(key):
    from chardata.models import RateCounter
    RateCounter.objects.filter(key=key[:190]).delete()


def _prune():
    """Drop what no window can still cover. Called when a key appears for the
    first time, which is rare enough to carry it and often enough to keep the
    table from growing."""
    from chardata.models import RateCounter
    RateCounter.objects.filter(
        window_start__lt=timezone.now() - STALE_AFTER).delete()
