# -*- coding: utf-8 -*-
"""Stats for the admin dashboard, and the SVG charts that draw them."""
import datetime
from collections import Counter, OrderedDict

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Min, Q, Sum
from django.utils import timezone

from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.encoded_char_id import encode_char_id

from chardata.models import (BuildComment, BuildVote, Char, PageHit,
                             SolutionMemoryHits, UserAlias)

CACHE_KEY = 'admin_dashboard_v2'
CACHE_SECONDS = 300
VERSIONS = [slug for slug, _label in ACTIVE_GAME_VERSIONS]
VERSION_LABELS = dict(ACTIVE_GAME_VERSIONS)

# key -> (label, length in days). None means back to the first row there is.
PERIODS = OrderedDict([
    ('7d', ('7 days', 7)),
    ('30d', ('30 days', 30)),
    ('90d', ('90 days', 90)),
    ('6m', ('6 months', 182)),
    ('12m', ('12 months', 365)),
    ('all', ('All time', None)),
])
DEFAULT_PERIOD = '6m'

# How many rows a table holds.
ROW_CAP = 100
CLASS_CAP = 20


# Floor for every date: keeps date subtraction inside what datetime can hold.
EARLIEST = datetime.date(2000, 1, 1)


class Period(object):
    """A date range, the range just before it, and the buckets to draw it in."""

    def __init__(self, key, start, end, custom=False):
        self.key = key
        self.custom = custom
        self.end = min(max(end, EARLIEST), timezone.localdate())
        self.start = min(max(start, EARLIEST), self.end)
        self.unit = _unit_for((self.end - self.start).days + 1)
        if not custom:
            self.start = max(_bucket_start(self.start, self.unit), EARLIEST)
        self.days = (self.end - self.start).days + 1
        self.previous_end = self.start - datetime.timedelta(days=1)
        self.previous_start = max(
            self.previous_end - datetime.timedelta(days=self.days - 1), datetime.date.min)
        self.buckets = _bucket_starts(self.start, self.end, self.unit)

    @property
    def label(self):
        if self.custom:
            return '%s to %s' % (self.start.strftime('%d/%m/%Y'), self.end.strftime('%d/%m/%Y'))
        return PERIODS[self.key][0]

    @property
    def previous_label(self):
        return '%s to %s' % (self.previous_start.strftime('%d/%m/%Y'),
                             self.previous_end.strftime('%d/%m/%Y'))

    def bucket_of(self, day):
        return _bucket_start(day, self.unit)

    def series(self, counts):
        return [(_bucket_label(b, self.unit), counts.get(b, 0)) for b in self.buckets]


def _unit_for(days):
    if days <= 31:
        return 'day'
    if days <= 200:
        return 'week'
    return 'month'


def _bucket_start(day, unit):
    if unit == 'day':
        return day
    if unit == 'week':
        return day - datetime.timedelta(days=day.weekday())
    return day.replace(day=1)


def _bucket_starts(start, end, unit):
    out = []
    current = _bucket_start(start, unit)
    while current <= end:
        out.append(current)
        if unit == 'day':
            current += datetime.timedelta(days=1)
        elif unit == 'week':
            current += datetime.timedelta(days=7)
        else:
            current = (current.replace(day=28) + datetime.timedelta(days=4)).replace(day=1)
    return out


def _bucket_label(bucket, unit):
    return bucket.strftime('%m/%y') if unit == 'month' else bucket.strftime('%d/%m')


FIRST_DAY_KEY = 'admin_dashboard_first_day'
FIRST_DAY_SECONDS = 3600


def _first_day_on_record():
    """Char.created_time carries no index, so this is a table scan."""
    known = cache.get(FIRST_DAY_KEY)
    if known:
        return known
    days = [User.objects.aggregate(d=Min('date_joined'))['d'],
            Char.objects.aggregate(d=Min('created_time'))['d']]
    days = [timezone.localtime(d).date() if d and hasattr(d, 'hour') else d
            for d in days if d]
    first = min(days) if days else timezone.localdate()
    cache.set(FIRST_DAY_KEY, first, FIRST_DAY_SECONDS)
    return first


def _parse_day(text):
    try:
        day = datetime.datetime.strptime(text, '%Y-%m-%d').date()
    except (TypeError, ValueError):
        return None
    return min(max(day, EARLIEST), timezone.localdate())


def resolve_period(key=None, start=None, end=None):
    """A custom start and end wins over the preset key. Bad input falls back."""
    today = timezone.localdate()
    first, last = _parse_day(start), _parse_day(end)
    if first or last:
        first = first or EARLIEST
        last = last or today
        if first > last:
            first, last = last, first
        return Period('custom', first, last, custom=True)
    if key not in PERIODS:
        key = DEFAULT_PERIOD
    length = PERIODS[key][1]
    begin = (_first_day_on_record() if length is None
             else today - datetime.timedelta(days=length - 1))
    return Period(key, begin, today)


def resolve_version(slug):
    return slug if slug in VERSIONS else None


def _within(queryset, field, period):
    return queryset.filter(**{field + '__date__gte': period.start,
                              field + '__date__lte': period.end})


def _for_version(queryset, version, field='game_version'):
    return queryset.filter(**{field: version}) if version else queryset


def _by_bucket(queryset, field, period):
    """{bucket start: count}. Grouped in Python: sqlite and mysql truncate dates differently."""
    buckets = Counter()
    for value in queryset.values_list(field, flat=True):
        if value is None:
            continue
        day = timezone.localtime(value).date() if hasattr(value, 'hour') else value
        buckets[period.bucket_of(day)] += 1
    return buckets


def _change(recent, previous):
    if not previous:
        return None
    return round((recent - previous) * 100.0 / previous)


def _period_counts(queryset, field, period):
    recent = queryset.filter(**{field + '__date__gte': period.start,
                                field + '__date__lte': period.end}).count()
    previous = queryset.filter(**{field + '__date__gte': period.previous_start,
                                  field + '__date__lte': period.previous_end}).count()
    return {'recent': recent, 'previous': previous, 'change': _change(recent, previous)}


def overview(period, version):
    builds = _for_version(Char.objects.filter(deleted=False), version)
    comments = _for_version(BuildComment.objects.filter(deleted=False), version,
                            'build__game_version')
    votes = _for_version(BuildVote.objects.all(), version, 'build__game_version')

    accounts = _by_bucket(_within(User.objects.all(), 'date_joined', period),
                          'date_joined', period)
    in_period = _within(builds, 'created_time', period)
    per_version = OrderedDict()
    for slug in (VERSIONS if not version else [version]):
        per_version[slug] = period.series(
            _by_bucket(in_period.filter(game_version=slug), 'created_time', period))
    return {
        'accounts': period.series(accounts),
        'builds_by_version': per_version,
        'tiles': [
            ('New accounts', _period_counts(User.objects.all(), 'date_joined', period)),
            ('Builds created', _period_counts(builds, 'created_time', period)),
            ('Comments', _period_counts(comments, 'created_time', period)),
            ('Votes', _period_counts(votes, 'created_time', period)),
        ],
        'signup_methods': _signup_methods(),
        'languages': _languages(),
    }


def _signup_methods():
    try:
        from social_django.models import UserSocialAuth
    except ImportError:
        return []
    social = list(UserSocialAuth.objects.values('provider')
                  .annotate(n=Count('user_id', distinct=True)).order_by('-n'))
    social_ids = set(UserSocialAuth.objects.values_list('user_id', flat=True))
    rows = [(row['provider'], row['n']) for row in social]
    rows.append(('email', User.objects.exclude(id__in=social_ids).count()))
    return sorted(rows, key=lambda r: -r[1])


def _languages():
    rows = Counter()
    for language in UserAlias.objects.values_list('language', flat=True):
        rows[language or 'unknown'] += 1
    known = sum(rows.values())
    rows['no profile'] = max(User.objects.count() - known, 0)
    return sorted(rows.items(), key=lambda r: -r[1])


def versions(period, version):
    rows = []
    for slug in VERSIONS:
        alive = Char.objects.filter(game_version=slug, deleted=False)
        total = alive.count()
        shared = alive.filter(link_shared=True).count()
        rows.append({
            'slug': slug,
            'label': VERSION_LABELS.get(slug, slug),
            'selected': slug == version,
            'total': total,
            'new_in_period': alive.filter(created_time__date__gte=period.start,
                                          created_time__date__lte=period.end).count(),
            'shared': shared,
            'share_rate': round(shared * 100.0 / total) if total >= 20 else None,
            'comments_in_period': BuildComment.objects.filter(
                deleted=False, build__game_version=slug,
                created_time__date__gte=period.start,
                created_time__date__lte=period.end).count(),
        })
    shown = [version] if version else VERSIONS
    return {'rows': rows, 'classes': _classes(shown), 'levels': _levels(shown)}


def _classes(shown):
    counts = Counter()
    for row in (Char.objects.filter(deleted=False)
                .values('game_version', 'char_class').annotate(n=Count('id'))):
        counts[(row['game_version'], row['char_class'])] = row['n']
    per_version = OrderedDict()
    for slug in shown:
        rows = [(cls, n) for (v, cls), n in counts.items() if v == slug and cls]
        total = sum(n for _c, n in rows) or 1
        per_version[slug] = [(cls, n, round(n * 100.0 / total))
                             for cls, n in sorted(rows, key=lambda r: -r[1])[:CLASS_CAP]]
    return per_version


LEVEL_BANDS = ((1, 20), (21, 50), (51, 100), (101, 150), (151, 199), (200, 200))


def _levels(shown):
    per_version = OrderedDict()
    for slug in shown:
        counts = Char.objects.filter(deleted=False, game_version=slug).aggregate(
            **{'band%d' % i: Count('id', filter=Q(level__gte=low, level__lte=high))
               for i, (low, high) in enumerate(LEVEL_BANDS)})
        bands = []
        for i, (low, high) in enumerate(LEVEL_BANDS):
            label = str(low) if low == high else '%d-%d' % (low, high)
            bands.append((label, counts['band%d' % i] or 0))
        per_version[slug] = bands
    return per_version


def community(period, version):
    comments = _for_version(BuildComment.objects.filter(deleted=False), version,
                            'build__game_version')
    votes = _for_version(BuildVote.objects.all(), version, 'build__game_version')
    shared = _for_version(Char.objects.filter(link_shared=True, deleted=False), version)

    top = []
    counted = shared.annotate(
        n_comments=Count('buildcomment', filter=Q(buildcomment__deleted=False), distinct=True),
        n_votes=Count('buildvote', distinct=True))
    for build in counted.order_by('-view_count')[:ROW_CAP]:
        top.append({
            'name': build.name or build.char_name or '-',
            'version': VERSION_LABELS.get(build.game_version, build.game_version),
            'views': build.view_count,
            'comments': build.n_comments,
            'votes': build.n_votes,
            'url': '/s/%s/%s/' % (build.char_name or 'shared', encode_char_id(int(build.id))),
        })
    return {
        'comments': period.series(_by_bucket(_within(comments, 'created_time', period),
                                             'created_time', period)),
        'votes': period.series(_by_bucket(_within(votes, 'created_time', period),
                                          'created_time', period)),
        'top_builds': top,
        'engagement': _engagement(shared),
    }


ENGAGEMENT_BANDS = (('0', 0, 0), ('1-2', 1, 2), ('3-5', 3, 5), ('6-10', 6, 10), ('11+', 11, 10 ** 9))


def _engagement(shared):
    """Shared builds bucketed by how many comments and votes they got."""
    ids = list(shared.values_list('id', flat=True))
    if not ids:
        return []
    counts = Counter()
    for row in (BuildComment.objects.filter(deleted=False, build_id__in=ids)
                .values('build_id').annotate(n=Count('id'))):
        counts[row['build_id']] += row['n']
    for row in (BuildVote.objects.filter(build_id__in=ids)
                .values('build_id').annotate(n=Count('id'))):
        counts[row['build_id']] += row['n']
    bands = []
    for label, low, high in ENGAGEMENT_BANDS:
        bands.append((label, sum(1 for b in ids if low <= counts.get(b, 0) <= high)))
    return bands


#: The day PageHitMiddleware started skipping crawlers. Everything counted
#: before is inflated -- a crawler was counted exactly like a reader, and the
#: user agent was never stored, so the old rows cannot be corrected. Naming the
#: date lets the page say which of its numbers can be trusted instead of
#: presenting two different things as one.
ROBOTS_EXCLUDED_SINCE = datetime.date(2026, 8, 24)


def pages(period, version):
    hits = PageHit.objects.filter(day__gte=period.start, day__lte=period.end)
    hits = _for_version(hits, version)
    rows = hits.values('path').annotate(n=Sum('count')).order_by('-n')[:ROW_CAP]
    per_version = (PageHit.objects.filter(day__gte=period.start, day__lte=period.end)
                   .values('game_version').annotate(n=Sum('count')).order_by('-n'))
    buckets = Counter()
    for row in hits.values('day').annotate(n=Sum('count')):
        buckets[period.bucket_of(row['day'])] += row['n']
    return {
        'top': [(r['path'], r['n']) for r in rows],
        'by_version': [(VERSION_LABELS.get(r['game_version'], r['game_version']), r['n'])
                       for r in per_version],
        'per_week': period.series(buckets),
        'collecting_since': PageHit.objects.order_by('day').values_list('day', flat=True).first(),
        'robots_excluded_since': ROBOTS_EXCLUDED_SINCE,
        'includes_robots': period.start < ROBOTS_EXCLUDED_SINCE,
    }


def solver(period, version):
    in_period = SolutionMemoryHits.objects.filter(day__gte=period.start, day__lte=period.end)
    per_bucket_hit, per_bucket_miss = Counter(), Counter()
    for row in in_period.values('day', 'count_hit', 'count_miss'):
        start = period.bucket_of(row['day'])
        per_bucket_hit[start] += row['count_hit']
        per_bucket_miss[start] += row['count_miss']
    totals = in_period.aggregate(hit=Sum('count_hit'), miss=Sum('count_miss'))
    total_hit, total_miss = totals['hit'] or 0, totals['miss'] or 0
    unsolved = _for_version(Char.objects.filter(deleted=False, minimal_solution=b''), version)
    return {
        'hits': period.series(per_bucket_hit),
        'misses': period.series(per_bucket_miss),
        'hit_rate': (round(total_hit * 100.0 / (total_hit + total_miss))
                     if (total_hit + total_miss) else None),
        'no_solution': [(VERSION_LABELS.get(slug, slug),
                         unsolved.filter(game_version=slug).count())
                        for slug in (VERSIONS if not version else [version])],
    }


UNIT_WORD = {'day': 'per day', 'week': 'per week', 'month': 'per month'}


def _url(period_key=None, start=None, end=None, version=None):
    parts = []
    if start and end:
        parts.append('from=%s&to=%s' % (start, end))
    elif period_key:
        parts.append('period=%s' % period_key)
    if version:
        parts.append('version=%s' % version)
    return '?' + '&'.join(parts) if parts else '?'


def filters(period, version):
    """What the toolbar needs to draw itself, links included."""
    start, end = period.start.strftime('%Y-%m-%d'), period.end.strftime('%Y-%m-%d')
    keep = (start, end) if period.custom else (None, None)
    return {
        'periods': [{'key': key, 'label': label, 'on': not period.custom and key == period.key,
                     'url': _url(period_key=key, version=version)}
                    for key, (label, _d) in PERIODS.items()],
        'period_key': period.key,
        'period_label': period.label,
        'start': start,
        'end': end,
        'unit': period.unit,
        'unit_word': UNIT_WORD[period.unit],
        'custom': period.custom,
        'versions': [{'slug': None, 'label': 'All versions', 'on': not version,
                      'url': _url(period.key, keep[0], keep[1], None)}] +
                    [{'slug': slug, 'label': VERSION_LABELS.get(slug, slug),
                      'on': slug == version,
                      'url': _url(period.key, keep[0], keep[1], slug)}
                     for slug in VERSIONS],
        'version': version,
        'version_label': VERSION_LABELS.get(version, 'All versions'),
        'previous_label': period.previous_label,
        'today': timezone.localdate().strftime('%Y-%m-%d'),
        'refresh_url': _url(period.key, keep[0], keep[1], version) + '&refresh=1',
    }


def dashboard(refresh=False, period_key=None, version=None, start=None, end=None):
    if refresh:
        cache.delete(FIRST_DAY_KEY)
    period = resolve_period(period_key, start, end)
    version = resolve_version(version)
    # Only presets are cached: a custom range mints a key per date pair, in a
    # cache the whole site shares.
    key = None if period.custom else '%s:%s:%s' % (CACHE_KEY, period.key, version or 'all')
    if key and not refresh:
        cached = cache.get(key)
        if cached:
            return cached
    data = {'overview': overview(period, version), 'versions': versions(period, version),
            'community': community(period, version), 'pages': pages(period, version),
            'solver': solver(period, version), 'filters': filters(period, version),
            'generated': timezone.localtime().strftime('%d/%m %H:%M')}
    if key:
        cache.set(key, data, CACHE_SECONDS)
    return data


# --- charts ---------------------------------------------------------------

def bar_chart(series, width=560, height=150, colour='var(--fm-accent, #c8a05a)'):
    """series is [(label, value)]."""
    if not series:
        return ''
    top = max(v for _l, v in series) or 1
    step = width / float(len(series))
    bar = max(step * 0.6, 2)
    parts = ['<svg viewBox="0 0 %d %d" class="admin-chart" preserveAspectRatio="none">'
             % (width, height + 18)]
    for i, (label, value) in enumerate(series):
        tall = (value / float(top)) * height
        x = i * step + (step - bar) / 2
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s"><title>%s: %d</title></rect>'
                     % (x, height - tall, bar, tall, colour, label, value))
    every = max(1, len(series) // 8)
    for i, (label, _v) in enumerate(series):
        if i % every == 0:
            parts.append('<text x="%.1f" y="%d" class="admin-chart-label">%s</text>'
                         % (i * step + step / 2, height + 14, label))
    parts.append('</svg>')
    return ''.join(parts)


def stacked_chart(series_by_key, colours, width=560, height=150):
    """{key: [(label, value)]}, every series with the same labels in the same order."""
    keys = [k for k in series_by_key if series_by_key[k]]
    if not keys:
        return ''
    length = len(series_by_key[keys[0]])
    totals = [sum(series_by_key[k][i][1] for k in keys) for i in range(length)]
    top = max(totals) or 1
    step = width / float(length)
    bar = max(step * 0.6, 2)
    parts = ['<svg viewBox="0 0 %d %d" class="admin-chart" preserveAspectRatio="none">'
             % (width, height + 18)]
    for i in range(length):
        bottom = height
        for k in keys:
            value = series_by_key[k][i][1]
            if not value:
                continue
            tall = (value / float(top)) * height
            bottom -= tall
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s">'
                         '<title>%s %s: %d</title></rect>'
                         % (i * step + (step - bar) / 2, bottom, bar, tall,
                            colours.get(k, '#888'), k, series_by_key[keys[0]][i][0], value))
    every = max(1, length // 8)
    for i in range(length):
        if i % every == 0:
            parts.append('<text x="%.1f" y="%d" class="admin-chart-label">%s</text>'
                         % (i * step + step / 2, height + 14, series_by_key[keys[0]][i][0]))
    parts.append('</svg>')
    return ''.join(parts)
