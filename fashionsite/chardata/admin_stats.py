# -*- coding: utf-8 -*-
"""Stats for the admin dashboard, and the SVG charts that draw them."""
import datetime
from collections import Counter, OrderedDict

from django.contrib.auth.models import User
from chardata.util import shared_build_path
from django.core.cache import cache
from django.db.models import Count, F, Min, Q, Sum
from django.utils import timezone
from django.utils.html import escape

from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.encoded_char_id import encode_char_id

from chardata.models import (BuildComment, BuildVote, Char, ExportHit,
                             ImportSourceHit, PageHit, SolutionMemoryHits,
                             UserAlias)

CACHE_KEY = 'admin_dashboard_v5'
CACHE_SECONDS = 300
SECTION_KEY = 'admin_section_v1'
SECTION_SECONDS = 900
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
        self.approximate = False
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


def _first_day_on_record(scan=True):
    """Char.created_time carries no index, so this is a table scan. Without scan, None when not cached."""
    known = cache.get(FIRST_DAY_KEY)
    if known:
        return known
    if not scan:
        return None
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


def resolve_period(key=None, start=None, end=None, scan=True):
    """A custom start and end wins over the preset key. Bad input falls back.

    Without scan, the all time preset never reads the tables: its start is the
    cached first day, else the earliest date, and the period is flagged approximate.
    """
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
    approximate = False
    if length is None:
        begin = _first_day_on_record(scan)
        if begin is None:
            begin, approximate = EARLIEST, True
    else:
        begin = today - datetime.timedelta(days=length - 1)
    period = Period(key, begin, today)
    period.approximate = approximate
    return period


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


COPY_SAVE_TOLERANCE = datetime.timedelta(seconds=60)
COPY_RUN_TOLERANCE = datetime.timedelta(seconds=1)


def untouched_copy_q():
    """An anonymous copy nobody touched: following a copy link makes one, and crawlers follow links.

    A batch save moves modified_time, so an untouched copy it reached still counts.
    """
    created = F('created_time')
    return (
        Q(owner__isnull=True, name__endswith=' copy', link_shared=False,
          created_time__isnull=False,
          modified_time__lte=created + COPY_SAVE_TOLERANCE)
        & (Q(solved_time__isnull=True) | Q(solved_time__lte=created + COPY_RUN_TOLERANCE))
        & (Q(stuff_time__isnull=True) | Q(stuff_time__lte=created + COPY_RUN_TOLERANCE)))


def _builds_in_use():
    """Alive builds, without the anonymous copies nobody touched."""
    return Char.objects.filter(deleted=False).exclude(untouched_copy_q())


def overview(period, version):
    builds = _for_version(_builds_in_use(), version)
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
        alive = _builds_in_use().filter(game_version=slug)
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
    for row in (_builds_in_use()
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
        counts = _builds_in_use().filter(game_version=slug).aggregate(
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
            'url': shared_build_path(build),
        })
    return {
        'comments': period.series(_by_bucket(_within(comments, 'created_time', period),
                                             'created_time', period)),
        'votes': period.series(_by_bucket(_within(votes, 'created_time', period),
                                          'created_time', period)),
        'top_builds': top,
        'engagement': _engagement(shared),
        'real_browsers_since': REAL_BROWSERS_SINCE,
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


#: The day pages started counting once a browser shows them. Older page reads and
#: direct arrivals also hold crawlers posing as browsers, and cannot be corrected:
#: the user agent was never stored.
REAL_BROWSERS_SINCE = datetime.date(2026, 11, 8)


def pages(period, version):
    # Older rows are hundreds of times larger: drawn together, today's bars vanish
    shown = period
    if period.start < REAL_BROWSERS_SINCE:
        shown = Period('custom', REAL_BROWSERS_SINCE,
                       max(period.end, REAL_BROWSERS_SINCE), custom=True)
    in_range = PageHit.objects.filter(day__gte=shown.start, day__lte=period.end)
    hits = _for_version(in_range, version)
    rows = hits.values('path').annotate(n=Sum('count')).order_by('-n')[:ROW_CAP]
    per_version = in_range.values('game_version').annotate(n=Sum('count')).order_by('-n')
    buckets = Counter()
    for row in hits.values('day').annotate(n=Sum('count')):
        buckets[shown.bucket_of(row['day'])] += row['n']
    return {
        'top': [(r['path'], r['n']) for r in rows],
        'by_version': [(VERSION_LABELS.get(r['game_version'], r['game_version']), r['n'])
                       for r in per_version],
        'per_week': shown.series(buckets),
        'unit_word': UNIT_WORD[shown.unit],
        'collecting_since': PageHit.objects.order_by('day').values_list('day', flat=True).first(),
        'real_browsers_since': REAL_BROWSERS_SINCE,
        'hides_older_days': period.start < REAL_BROWSERS_SINCE,
    }


IMPORT_SOURCES_READ = ('link', 'link_failed')
IMPORT_SOURCES = IMPORT_SOURCES_READ + ('text', 'screenshot', 'link_unknown')
UNNAMED_SITE = 'Other addresses'
SENT_SOURCE = 'api'
UNNAMED_SENDER = 'No source named'


def _percent(part, whole):
    """part of whole in percent to one decimal, halves rounded up; None when whole is 0."""
    if not whole:
        return None
    return (part * 2000 + whole) // (2 * whole) / 10.0


def _shares(counts):
    """Each count's percent of their sum to one decimal, adding up to exactly 100.0 (largest remainders)."""
    total = sum(counts)
    if not total:
        return [0.0] * len(counts)
    tenths = [count * 1000 // total for count in counts]
    by_remainder = sorted(range(len(counts)), key=lambda i: -(counts[i] * 1000 % total))
    for i in by_remainder[:1000 - sum(tenths)]:
        tenths[i] += 1
    return [tenth / 10.0 for tenth in tenths]


def imports(period, version):
    """Where pasted builds come from: each site we read, pasted text, screenshots, sites we cannot read yet."""
    from chardata.text_build_view import UNKNOWN_SITES_PER_DAY
    hits = _for_version(ImportSourceHit.objects.filter(
        day__gte=period.start, day__lte=period.end,
        source__in=IMPORT_SOURCES), version)
    sums = {'attempts_sum': Sum('attempts'), 'imported_sum': Sum('imported')}
    read = (hits.filter(source__in=IMPORT_SOURCES_READ).values('host')
            .annotate(**sums).order_by('-attempts_sum', 'host'))
    by_source = {row['source']: row for row in hits.values('source').annotate(**sums)}
    nothing = {'attempts_sum': 0, 'imported_sum': 0}
    text = by_source.get('text', nothing)
    shots = by_source.get('screenshot', nothing)
    unknown = by_source.get('link_unknown', nothing)
    lines = ([(row['host'], row['attempts_sum'], row['imported_sum']) for row in read]
             + [('Pasted text', text['attempts_sum'], text['imported_sum']),
                ('Screenshots', shots['attempts_sum'], shots['imported_sum']),
                ('Sites we cannot read yet', unknown['attempts_sum'], None)])
    total = sum(attempts for _label, attempts, _imported in lines)
    rows = [{'label': label, 'attempts': attempts, 'imported': imported,
             'share': share,
             'rate': None if imported is None else _percent(imported, attempts)}
            for (label, attempts, imported), share
            in zip(lines, _shares([attempts for _l, attempts, _i in lines]))]

    unknown_hits = hits.filter(source='link_unknown')
    unknown_rows = [{'label': row['host'] or UNNAMED_SITE,
                     'attempts': row['attempts_sum'],
                     'share': _percent(row['attempts_sum'], total)}
                    for row in unknown_hits.values('host')
                    .annotate(attempts_sum=Sum('attempts'))
                    .order_by('-attempts_sum', 'host')[:ROW_CAP]]

    sent = _for_version(ImportSourceHit.objects.filter(
        day__gte=period.start, day__lte=period.end, source=SENT_SOURCE), version)
    sent_rows = [{'label': row['host'] or UNNAMED_SENDER,
                  'attempts': row['attempts_sum'],
                  'imported': row['imported_sum'],
                  'rate': _percent(row['imported_sum'], row['attempts_sum'])}
                 for row in sent.values('host').annotate(**sums)
                 .order_by('-attempts_sum', 'host')[:ROW_CAP]]

    buckets = Counter()
    for row in hits.values('day').annotate(n=Sum('attempts')):
        buckets[period.bucket_of(row['day'])] += row['n']
    return {
        'rows': rows,
        'sent': sent_rows,
        'unknown': unknown_rows,
        'unknown_not_listed': max(0, unknown_hits.values('host').distinct().count()
                                  - len(unknown_rows)),
        'total': total,
        'per_bucket': period.series(buckets),
        'collecting_since': (ImportSourceHit.objects.order_by('day')
                             .values_list('day', flat=True).first()),
        'unknown_sites_per_day': UNKNOWN_SITES_PER_DAY,
    }


EXPORT_DESTINATIONS = (('dofusbook', 'DofusBook'), ('json', 'JSON file'),
                       ('api', 'Other sites through the API'))
UNNAMED_PULLER = 'No site named'


def exports(period, version):
    """Where builds go: DofusBook, the JSON file, other sites through the API."""
    from chardata.text_build_view import UNKNOWN_SITES_PER_DAY
    hits = _for_version(ExportHit.objects.filter(
        day__gte=period.start, day__lte=period.end,
        destination__in=[key for key, _label in EXPORT_DESTINATIONS]), version)
    by_destination = {row['destination']: row['n'] for row
                      in hits.values('destination').annotate(n=Sum('count'))}
    counts = [by_destination.get(key, 0) for key, _label in EXPORT_DESTINATIONS]
    rows = [{'label': label, 'count': count, 'share': share}
            for (_key, label), count, share
            in zip(EXPORT_DESTINATIONS, counts, _shares(counts))]

    pulls = hits.filter(destination='api')
    pulled = by_destination.get('api', 0)
    sites = [{'label': row['host'] or UNNAMED_PULLER, 'count': row['n'],
              'share': _percent(row['n'], pulled)}
             for row in pulls.values('host').annotate(n=Sum('count'))
             .order_by('-n', 'host')[:ROW_CAP]]

    buckets = Counter()
    for row in hits.values('day').annotate(n=Sum('count')):
        buckets[period.bucket_of(row['day'])] += row['n']
    return {
        'rows': rows,
        'sites': sites,
        'sites_not_listed': max(0, pulls.values('host').distinct().count()
                                - len(sites)),
        'total': sum(counts),
        'pulled': pulled,
        'per_bucket': period.series(buckets),
        'collecting_since': (ExportHit.objects.order_by('day')
                             .values_list('day', flat=True).first()),
        'sites_per_day': UNKNOWN_SITES_PER_DAY,
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
    unsolved = _for_version(_builds_in_use().filter(minimal_solution=b''), version)
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


def _url(period_key=None, start=None, end=None, version=None, tab=None):
    parts = []
    if start and end:
        parts.append('from=%s&to=%s' % (start, end))
    elif period_key:
        parts.append('period=%s' % period_key)
    if version:
        parts.append('version=%s' % version)
    if tab:
        parts.append('tab=%s' % tab)
    return '?' + '&'.join(parts) if parts else '?'


def filters(period, version, tab=None):
    """What the toolbar needs to draw itself, links included."""
    start, end = period.start.strftime('%Y-%m-%d'), period.end.strftime('%Y-%m-%d')
    keep = (start, end) if period.custom else (None, None)
    if period.approximate:
        start = ''
    return {
        'periods': [{'key': key, 'label': label, 'on': not period.custom and key == period.key,
                     'url': _url(period_key=key, version=version, tab=tab)}
                    for key, (label, _d) in PERIODS.items()],
        'period_key': period.key,
        'period_label': period.label,
        'start': start,
        'end': end,
        'unit': period.unit,
        'unit_word': UNIT_WORD[period.unit],
        'custom': period.custom,
        'versions': [{'slug': None, 'label': 'All versions', 'on': not version,
                      'url': _url(period.key, keep[0], keep[1], None, tab)}] +
                    [{'slug': slug, 'label': VERSION_LABELS.get(slug, slug),
                      'on': slug == version,
                      'url': _url(period.key, keep[0], keep[1], slug, tab)}
                     for slug in VERSIONS],
        'version': version,
        'version_label': VERSION_LABELS.get(version, 'All versions'),
        'previous_label': period.previous_label,
        'today': timezone.localdate().strftime('%Y-%m-%d'),
        'refresh_url': (_url(period.key, keep[0], keep[1], version) + '&refresh=1'
                        + ('&tab=%s' % tab if tab else '')),
        'tab': tab,
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
            'imports': imports(period, version),
            'exports': exports(period, version),
            'solver': solver(period, version), 'filters': filters(period, version),
            'generated': timezone.localtime().strftime('%d/%m %H:%M')}
    if key:
        cache.set(key, data, CACHE_SECONDS)
    return data


SECTIONS = OrderedDict([
    ('overview', overview), ('versions', versions), ('community', community),
    ('pages', pages), ('imports', imports), ('exports', exports), ('solver', solver),
])


def section(name, period, version, refresh=False):
    """One section of the dashboard as (data, generated), cached on its own.

    Only presets are cached, like dashboard(): a custom range mints a key per date pair.
    """
    key = (None if period.custom or period.approximate
           else '%s:%s:%s:%s' % (SECTION_KEY, name, period.key, version or 'all'))
    if key and not refresh:
        cached = cache.get(key)
        if cached:
            return cached['data'], cached['generated']
    data = SECTIONS[name](period, version)
    generated = timezone.localtime().strftime('%d/%m %H:%M')
    if key:
        cache.set(key, {'data': data, 'generated': generated}, SECTION_SECONDS)
    return data, generated


# --- charts ---------------------------------------------------------------

# One day of data must not fill the whole chart
WIDEST_BAR = 40


def bar_chart(series, width=560, height=150, colour='var(--ad-s1)'):
    """series is [(label, value)]."""
    if not series:
        return ''
    top = max(v for _l, v in series) or 1
    step = width / float(len(series))
    bar = min(max(step * 0.6, 2), WIDEST_BAR)
    parts = ['<svg viewBox="0 0 %d %d" class="admin-chart" role="img" aria-label="Bar chart" tabindex="0">'
             % (width, height + 18)]
    for i, (label, value) in enumerate(series):
        tall = (value / float(top)) * height
        x = i * step + (step - bar) / 2
        parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" data-tip="%s" data-v="%d"/>'
                     % (x, height - tall, bar, tall, colour, escape(label), value))
    every = max(1, len(series) // 8)
    for i, (label, _v) in enumerate(series):
        if i % every == 0:
            parts.append('<text x="%.1f" y="%d" class="admin-chart-label">%s</text>'
                         % (i * step + step / 2, height + 14, label))
    parts.append('</svg>')
    return ''.join(parts)


def _legend(keys, colours, hatched):
    items = []
    for k in keys:
        colour = colours.get(k, '#888')
        items.append('<span><i class="ah-sw%s" style="--ad-c:%s;background-color:%s"></i>%s</span>'
                     % (' ah-sw-e' if k in hatched else '', colour, colour, escape(k)))
    return '<div class="ah-legend">%s</div>' % ''.join(items)


def stacked_chart(series_by_key, colours, width=560, height=150, hatched=(), pattern_id='est'):
    """{key: [(label, value)]}, every series with the same labels in the same order.

    The keys in hatched are drawn with a hatch pattern instead of a flat fill.
    """
    keys = [k for k in series_by_key if series_by_key[k]]
    if not keys:
        return ''
    length = len(series_by_key[keys[0]])
    totals = [sum(series_by_key[k][i][1] for k in keys) for i in range(length)]
    top = max(totals) or 1
    step = width / float(length)
    bar = min(max(step * 0.6, 2), WIDEST_BAR)
    parts = ['<svg viewBox="0 0 %d %d" class="admin-chart" role="img" aria-label="Stacked bar chart" tabindex="0">'
             % (width, height + 18)]
    fills = {}
    for k in keys:
        if k in hatched:
            colour = colours.get(k, '#888')
            fills[k] = 'url(#%s-%d)' % (pattern_id, len(fills))
            parts.append('<defs><pattern id="%s-%d" width="9" height="9" patternUnits="userSpaceOnUse" '
                         'patternTransform="rotate(45)"><rect width="9" height="9" fill="%s" fill-opacity="0.36"/>'
                         '<rect width="1.4" height="9" fill="%s" fill-opacity="0.55"/></pattern></defs>'
                         % (pattern_id, len(fills) - 1, colour, colour))
    for i in range(length):
        bottom = height
        for k in keys:
            value = series_by_key[k][i][1]
            if not value:
                continue
            tall = (value / float(top)) * height
            bottom -= tall
            parts.append('<rect x="%.1f" y="%.1f" width="%.1f" height="%.1f" fill="%s" '
                         'data-tip="%s" data-s="%s" data-v="%d"/>'
                         % (i * step + (step - bar) / 2, bottom, bar, tall,
                            fills.get(k) or colours.get(k, '#888'),
                            escape(series_by_key[keys[0]][i][0]), escape(k), value))
    every = max(1, length // 8)
    for i in range(length):
        if i % every == 0:
            parts.append('<text x="%.1f" y="%d" class="admin-chart-label">%s</text>'
                         % (i * step + step / 2, height + 14, series_by_key[keys[0]][i][0]))
    parts.append('</svg>')
    parts.append(_legend(keys, colours, hatched))
    return ''.join(parts)
