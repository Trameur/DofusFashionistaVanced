# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The site history shown to staff: a stored snapshot plus the live figures counted after it.

The snapshot lives in SiteSetting under KEY and is written only by the
load_site_history command. Nothing here raises on a missing or damaged snapshot.
"""
import copy
import datetime
import json
import logging
import math
import re
from collections import Counter

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Sum
from django.utils import timezone

from chardata import admin_stats
from chardata.models import (BuildComment, BuildTag, BuildVote, Char, ExportHit,
                             ImportSourceHit, InventoryFolder, InventoryItem,
                             PageHit, SiteSetting, SolutionMemoryHits,
                             SupportClick, WorkshopItem)

logger = logging.getLogger(__name__)

KEY = 'site_history'
SCHEMA = 1
MAX_BYTES = 2 * 1024 * 1024
MAX_PROBLEMS = 40
STATUSES = ('M', 'C', 'E', 'G')
SNAPSHOT_KEY = 'site_history_snapshot_v1'
PAYLOAD_KEY = 'site_history_payload_v1'
CACHE_SECONDS = 600

LIVE_VERSIONS = ('dofus2', 'dofus3', 'beta', 'retro', 'touch')
LIVE_METRICS = (
    ('builds_real', 'builds_robots')
    + tuple('v_' + slug for slug in LIVE_VERSIONS)
    + ('accounts_raw', 'accounts_real', 'solver', 'shared', 'votes', 'comments',
       'tags', 'inventory', 'folders', 'workshop', 'support', 'imports',
       'imports_ok', 'exports', 'exports_counted', 'pages_real'))
#: Months of visits per page read, taken from the last complete months of the snapshot
RATIO_MONTHS = 3
RANGE_SPREAD = 0.4

MONTH_RE = re.compile(r'^\d{4}-(0[1-9]|1[0-2])$')
LIST_FIELDS = {
    'eras': ('id', 'name', 'from', 'story'),
    'milestones': ('id', 'date', 'month', 'shown', 'lane', 'lane_name', 'major',
                   'title', 'detail'),
    'methods': ('id', 'metric', 'period', 'status', 'confidence', 'method'),
    'classes': ('year', 'class', 'builds', 'share'),
    'levels': ('year', 'builds', 'low', 'mid', 'high', 'top'),
}
NUMBER_FIELDS = {'classes': ('builds', 'share'),
                 'levels': ('builds', 'low', 'mid', 'high', 'top')}
BOOLEAN_FIELDS = {'milestones': ('major',)}
ANY_SCALAR_FIELDS = {'eras': ('id',), 'milestones': ('id',), 'methods': ('id',)}


def _is_number(value):
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _is_day(value):
    try:
        datetime.datetime.strptime(value, '%Y-%m-%d')
    except (TypeError, ValueError):
        return False
    return True


def _check_series(series, bad):
    if not isinstance(series, dict) or not series:
        bad('series is missing or empty')
        return
    if not isinstance(series.get('builds_real'), list):
        bad('series has no builds_real')
    for metric, rows in series.items():
        if not isinstance(metric, str) or not isinstance(rows, list):
            bad('series %r is not a list' % (metric,))
            continue
        previous = ''
        for index, row in enumerate(rows):
            where = 'series %s row %d' % (metric, index)
            if not isinstance(row, (list, tuple)) or len(row) != 5:
                bad('%s is not [month, value, status, low, high]' % where)
                break
            month, value, status, low, high = row
            if not isinstance(month, str) or not MONTH_RE.match(month):
                bad('%s has a bad month' % where)
                break
            if month <= previous:
                bad('%s: months are not strictly increasing' % where)
                break
            previous = month
            if not _is_number(value):
                bad('%s has a bad value' % where)
                break
            if status not in STATUSES:
                bad('%s has a bad status' % where)
                break
            if any(bound is not None and not _is_number(bound) for bound in (low, high)):
                bad('%s has a bad range' % where)
                break


def _check_list(snapshot, name, bad):
    rows = snapshot.get(name)
    if not isinstance(rows, list):
        bad('%s is missing or not a list' % name)
        return
    for index, row in enumerate(rows):
        where = '%s %d' % (name, index)
        if not isinstance(row, dict):
            bad('%s is not an object' % where)
            return
        for field in LIST_FIELDS[name]:
            value = row.get(field)
            if field in NUMBER_FIELDS.get(name, ()):
                good = _is_number(value)
            elif field in BOOLEAN_FIELDS.get(name, ()):
                good = isinstance(value, bool)
            elif field in ANY_SCALAR_FIELDS.get(name, ()):
                good = isinstance(value, (str, int)) and not isinstance(value, bool)
            else:
                good = isinstance(value, str)
            if not good:
                bad('%s has a bad %s' % (where, field))
                return
        if name == 'eras':
            end = row.get('to')
            if end is not None and not (isinstance(end, str) and MONTH_RE.match(end)):
                bad('%s has a bad to' % where)
                return
            if not MONTH_RE.match(row.get('from', '')):
                bad('%s has a bad from' % where)
                return
        if name == 'milestones' and not MONTH_RE.match(row.get('month', '')):
            bad('%s has a bad month' % where)
            return


def validate(snapshot):
    """The problems found in a snapshot, empty when it is usable."""
    problems = []

    def bad(text):
        if len(problems) < MAX_PROBLEMS:
            problems.append(text)

    if not isinstance(snapshot, dict):
        return ['the snapshot is not an object']
    if snapshot.get('schema') != SCHEMA:
        bad('schema must be %d' % SCHEMA)
    if not _is_day(snapshot.get('as_of')):
        bad('as_of must be a YYYY-MM-DD date')
    elif not (admin_stats.EARLIEST.isoformat() <= snapshot['as_of']
              <= (timezone.localdate() + datetime.timedelta(days=1)).isoformat()):
        bad('as_of is out of range')
    floor = snapshot.get('char_id_floor')
    if floor is not None and (not isinstance(floor, int) or isinstance(floor, bool) or floor < 0):
        bad('char_id_floor must be a whole number or absent')
    _check_series(snapshot.get('series'), bad)
    for name in LIST_FIELDS:
        _check_list(snapshot, name, bad)
    return problems


def _decode(text):
    try:
        if text is None or len(text) > MAX_BYTES:
            return None
        snapshot = json.loads(text)
    except (TypeError, ValueError, RecursionError):
        return None
    return snapshot if not validate(snapshot) else None


def load(refresh=False):
    """The stored snapshot, or None when absent, unreadable or invalid. Never raises."""
    try:
        if not refresh:
            cached = cache.get(SNAPSHOT_KEY)
            if cached:
                return cached
        row = SiteSetting.objects.filter(key=KEY).first()
        snapshot = _decode(row.value) if row else None
        if snapshot is not None:
            cache.set(SNAPSHOT_KEY, snapshot, CACHE_SECONDS)
        return snapshot
    except Exception:
        logger.warning('the site history snapshot could not be read', exc_info=True)
        return None


def is_loaded():
    """Cheap check that a snapshot row exists, without reading it."""
    try:
        return SiteSetting.objects.filter(key=KEY).exclude(value='').exists()
    except Exception:
        return False


def forget():
    cache.delete_many([SNAPSHOT_KEY, PAYLOAD_KEY])


def _month(value):
    if isinstance(value, datetime.datetime):
        value = timezone.localtime(value) if timezone.is_aware(value) else value
    return value.strftime('%Y-%m')


def _months_between(first, last):
    """Every 'YYYY-MM' from first to last, both included."""
    year, month = int(first[:4]), int(first[5:7])
    months = []
    while '%04d-%02d' % (year, month) <= last:
        months.append('%04d-%02d' % (year, month))
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def _datetime_months(model, field, start):
    counts = Counter()
    rows = model.objects.filter(**{field + '__gte': start}).values_list(field, flat=True)
    for value in rows:
        if value is not None:
            counts[_month(value)] += 1
    return counts


def _day_months(model, field, since):
    counts = Counter()
    rows = (model.objects.filter(day__gt=since).values('day')
            .annotate(n=Sum(field)))
    for row in rows:
        counts[_month(row['day'])] += row['n'] or 0
    return counts


def _builds_counts(counts, start, floor):
    rows = Char.objects.filter(created_time__isnull=False)
    rows = rows.filter(pk__gt=floor) if floor else rows.filter(created_time__gte=start)
    copies = set(rows.filter(admin_stats.untouched_copy_q(), deleted=False)
                 .values_list('pk', flat=True))
    spans = {}
    for pk, created, version, shared in rows.values_list(
            'pk', 'created_time', 'game_version', 'link_shared'):
        month = _month(created)
        low, high, n = spans.get(month, (pk, pk, 0))
        spans[month] = (min(low, pk), max(high, pk), n + 1)
        if shared:
            counts['shared'][month] += 1
        if pk in copies:
            counts['builds_robots'][month] += 1
            continue
        counts['builds_real'][month] += 1
        if version in LIVE_VERSIONS:
            counts['v_' + version][month] += 1
    if floor and spans:
        first = min(spans, key=lambda m: spans[m][0])
        low, high, n = spans[first]
        spans[first] = (floor + 1, high, n)
    for month, (low, high, n) in spans.items():
        holes = high - low + 1 - n
        if holes:
            counts['builds_robots'][month] += holes


def _live_counts(since, floor=None):
    """{metric: {'YYYY-MM': n}} for everything dated after the day since."""
    start = timezone.make_aware(
        datetime.datetime.combine(since + datetime.timedelta(days=1), datetime.time.min))
    counts = {metric: Counter() for metric in LIVE_METRICS}
    _builds_counts(counts, start, floor)
    users = _datetime_months(User, 'date_joined', start)
    counts['accounts_raw'].update(users)
    counts['accounts_real'].update(users)
    for metric, model, field in (
            ('votes', BuildVote, 'created_time'),
            ('comments', BuildComment, 'created_time'),
            ('tags', BuildTag, 'created_time'),
            ('inventory', InventoryItem, 'added_time'),
            ('folders', InventoryFolder, 'created_time'),
            ('workshop', WorkshopItem, 'added_time')):
        counts[metric].update(_datetime_months(model, field, start))
    by_table = {}
    for metric, model, field in (
            ('solver', SolutionMemoryHits, 'count_hit'),
            ('solver', SolutionMemoryHits, 'count_miss'),
            ('support', SupportClick, 'count'),
            ('imports', ImportSourceHit, 'attempts'),
            ('imports_ok', ImportSourceHit, 'imported'),
            ('exports', ExportHit, 'count'),
            ('exports_counted', ExportHit, 'count'),
            ('pages_real', PageHit, 'count')):
        if (model, field) not in by_table:
            by_table[(model, field)] = _day_months(model, field, since)
        counts[metric].update(by_table[(model, field)])
    return {metric: dict(by_month) for metric, by_month in counts.items()}


def live_counts(snapshot):
    """Per metric and month, everything strictly after the snapshot's as_of day."""
    since = datetime.datetime.strptime(snapshot['as_of'], '%Y-%m-%d').date()
    return _live_counts(since, snapshot.get('char_id_floor'))


def _shift(row, delta, spread=None):
    row[1] = row[1] + delta
    for index, factor in ((3, 1 - spread if spread is not None else 1),
                          (4, 1 + spread if spread is not None else 1)):
        if row[index] is not None:
            row[index] = row[index] + delta * factor


def _visits_per_page(series, as_of):
    """Visits per page read over the last complete months of the snapshot, or None."""
    complete_through = _month(as_of)
    if (as_of + datetime.timedelta(days=1)).month == as_of.month:
        complete_through = _months_before(complete_through)
    visits = {row[0]: row[1] for row in series.get('visits', ())}
    pages = {row[0]: row[1] for row in series.get('pages_real', ())}
    months = sorted(m for m in visits if m in pages and m <= complete_through and pages[m] > 0)
    months = months[-RATIO_MONTHS:]
    total_pages = sum(pages[m] for m in months)
    if not months or total_pages <= 0:
        return None
    return sum(visits[m] for m in months) / float(total_pages)


def _months_before(month):
    year, number = int(month[:4]), int(month[5:7])
    return '%04d-%02d' % ((year - 1, 12) if number == 1 else (year, number - 1))


def merged(snapshot, now=None):
    """The series of the snapshot with the live figures added after its as_of."""
    now = now or timezone.now()
    now_month = _month(now)
    series = {metric: [list(row) for row in rows]
              for metric, rows in snapshot['series'].items()}
    as_of = datetime.datetime.strptime(snapshot['as_of'], '%Y-%m-%d').date()
    as_month = _month(as_of)
    live = live_counts(snapshot)
    later = _months_between(as_month, now_month)[1:] if now_month > as_month else []
    ratio = _visits_per_page(series, as_of)

    for metric in LIVE_METRICS:
        _apply(series.setdefault(metric, []), live.get(metric, {}), as_month, later,
               zero_row=True)
    if ratio:
        pages = live.get('pages_real', {})
        derived = {m: pages.get(m, 0) * ratio for m in [as_month] + later}
        _apply(series.setdefault('visits', []), derived, as_month, later,
               status='E', spread=RANGE_SPREAD, whole=True)
    return {metric: rows for metric, rows in series.items() if rows or metric in LIVE_METRICS}


def _apply(rows, counts, as_month, later, status='M', spread=None, whole=False, zero_row=False):
    by_month = {row[0]: row for row in rows}
    delta = counts.get(as_month, 0)
    if whole:
        delta = int(round(delta))
    if delta or (zero_row and status == 'M' and as_month not in by_month):
        if as_month in by_month:
            _shift(by_month[as_month], delta, spread)
            if whole:
                for index in (3, 4):
                    if by_month[as_month][index] is not None:
                        by_month[as_month][index] = int(round(by_month[as_month][index]))
        else:
            rows.append([as_month, delta, status, None, None])
    for month in later:
        if month in by_month:
            continue
        value = counts.get(month, 0)
        if whole:
            value = int(round(value))
        low = high = None
        if spread is not None:
            low, high = int(round(value * (1 - spread))), int(round(value * (1 + spread)))
        rows.append([month, value, status, low, high])
    rows.sort(key=lambda row: row[0])


def payload(refresh=False):
    """What the history page draws from.

    Only a complete answer is cached: a missing snapshot or a failed read must not
    keep saying so after the cause is gone, and each worker has its own cache.
    """
    if not refresh:
        cached = cache.get(PAYLOAD_KEY)
        if cached:
            return cached
    now = timezone.now()
    snapshot = load(True)
    series = {}
    complete = snapshot is not None
    if snapshot:
        try:
            series = merged(snapshot, now)
        except Exception:
            logger.warning('the live figures could not be added to the history', exc_info=True)
            series = copy.deepcopy(snapshot['series'])
            complete = False
    data = {
        'loaded': snapshot is not None,
        'as_of': snapshot['as_of'] if snapshot else None,
        'now_month': _month(now),
        'live': list(LIVE_METRICS) + ['visits'],
        'series': series,
        'eras': snapshot['eras'] if snapshot else [],
        'milestones': snapshot['milestones'] if snapshot else [],
        'methods': snapshot['methods'] if snapshot else [],
        'classes': snapshot['classes'] if snapshot else [],
        'levels': snapshot['levels'] if snapshot else [],
        'generated': timezone.localtime(now).strftime('%Y-%m-%d %H:%M'),
    }
    if complete:
        cache.set(PAYLOAD_KEY, data, CACHE_SECONDS)
    return data


def estimated_before(metric, first_month):
    """The snapshot rows older than first_month that are not measured."""
    snapshot = load()
    if not snapshot:
        return []
    return [tuple(row) for row in snapshot['series'].get(metric, ())
            if row[0] < first_month and row[2] != 'M']
