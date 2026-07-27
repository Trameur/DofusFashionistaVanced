# -*- coding: utf-8 -*-
"""Stats for the admin dashboard, and the SVG charts that draw them."""
import datetime
from collections import Counter, OrderedDict

from django.contrib.auth.models import User
from django.core.cache import cache
from django.db.models import Count, Sum
from django.utils import timezone

from chardata.context_processors import ACTIVE_GAME_VERSIONS
from chardata.encoded_char_id import encode_char_id
from chardata.models import (BuildComment, BuildVote, Char, PageHit,
                             SolutionMemoryHits, UserAlias)

CACHE_KEY = 'admin_dashboard_v1'
CACHE_SECONDS = 300
WEEKS = 20
VERSIONS = [slug for slug, _label in ACTIVE_GAME_VERSIONS]
VERSION_LABELS = dict(ACTIVE_GAME_VERSIONS)


def _week_starts(count=WEEKS):
    today = timezone.localdate()
    monday = today - datetime.timedelta(days=today.weekday())
    return [monday - datetime.timedelta(weeks=i) for i in range(count - 1, -1, -1)]


def _by_week(queryset, field):
    """{week start: count}. Grouped in Python: sqlite and mysql truncate dates differently."""
    weeks = Counter()
    for value in queryset.values_list(field, flat=True):
        if value is None:
            continue
        day = timezone.localtime(value).date() if hasattr(value, 'hour') else value
        weeks[day - datetime.timedelta(days=day.weekday())] += 1
    return weeks


def _series(weeks, counts):
    return [(w.strftime('%d/%m'), counts.get(w, 0)) for w in weeks]


def _change(recent, previous):
    if not previous:
        return None
    return round((recent - previous) * 100.0 / previous)


def _window_counts(model, field, extra=None):
    now = timezone.now()
    base = model.objects.filter(**(extra or {}))
    recent = base.filter(**{field + '__gte': now - datetime.timedelta(days=30)}).count()
    previous = base.filter(**{field + '__gte': now - datetime.timedelta(days=60),
                              field + '__lt': now - datetime.timedelta(days=30)}).count()
    return {'recent': recent, 'previous': previous, 'change': _change(recent, previous)}


def overview():
    weeks = _week_starts()
    first = weeks[0]
    accounts = _by_week(User.objects.filter(date_joined__date__gte=first), 'date_joined')
    builds = Char.objects.filter(deleted=False, created_time__date__gte=first)
    per_version = OrderedDict()
    for slug in VERSIONS:
        per_version[slug] = _series(weeks, _by_week(builds.filter(game_version=slug),
                                                    'created_time'))
    return {
        'accounts': _series(weeks, accounts),
        'builds_by_version': per_version,
        'tiles': [
            ('New accounts', _window_counts(User, 'date_joined')),
            ('Builds created', _window_counts(Char, 'created_time', {'deleted': False})),
            ('Comments', _window_counts(BuildComment, 'created_time', {'deleted': False})),
            ('Votes', _window_counts(BuildVote, 'created_time')),
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


def versions():
    now = timezone.now()
    month = now - datetime.timedelta(days=30)
    rows = []
    for slug in VERSIONS:
        alive = Char.objects.filter(game_version=slug, deleted=False)
        total = alive.count()
        shared = alive.filter(link_shared=True).count()
        rows.append({
            'slug': slug,
            'label': VERSION_LABELS.get(slug, slug),
            'total': total,
            'new_30d': alive.filter(created_time__gte=month).count(),
            'shared': shared,
            'share_rate': round(shared * 100.0 / total) if total >= 20 else None,
            'comments_30d': BuildComment.objects.filter(
                deleted=False, created_time__gte=month, build__game_version=slug).count(),
        })
    return {'rows': rows, 'classes': _classes(), 'levels': _levels()}


def _classes():
    counts = Counter()
    for row in (Char.objects.filter(deleted=False)
                .values('game_version', 'char_class').annotate(n=Count('id'))):
        counts[(row['game_version'], row['char_class'])] = row['n']
    per_version = OrderedDict()
    for slug in VERSIONS:
        rows = [(cls, n) for (v, cls), n in counts.items() if v == slug and cls]
        total = sum(n for _c, n in rows) or 1
        per_version[slug] = [(cls, n, round(n * 100.0 / total))
                             for cls, n in sorted(rows, key=lambda r: -r[1])[:8]]
    return per_version


LEVEL_BANDS = ((1, 20), (21, 50), (51, 100), (101, 150), (151, 199), (200, 200))


def _levels():
    per_version = OrderedDict()
    for slug in VERSIONS:
        levels = list(Char.objects.filter(deleted=False, game_version=slug)
                      .values_list('level', flat=True))
        bands = []
        for low, high in LEVEL_BANDS:
            label = str(low) if low == high else '%d-%d' % (low, high)
            bands.append((label, sum(1 for l in levels if l is not None and low <= l <= high)))
        per_version[slug] = bands
    return per_version


def community():
    weeks = _week_starts()
    first = weeks[0]
    comments = _by_week(BuildComment.objects.filter(deleted=False,
                                                    created_time__date__gte=first),
                        'created_time')
    votes = _by_week(BuildVote.objects.filter(created_time__date__gte=first), 'created_time')
    top = []
    for build in (Char.objects.filter(link_shared=True, deleted=False)
                  .order_by('-view_count')[:20]):
        top.append({
            'name': build.name or build.char_name or '-',
            'version': VERSION_LABELS.get(build.game_version, build.game_version),
            'views': build.view_count,
            'comments': BuildComment.objects.filter(build=build, deleted=False).count(),
            'votes': BuildVote.objects.filter(build=build).count(),
            'url': '/s/%s/%s/' % (build.char_name or 'shared', encode_char_id(int(build.id))),
        })
    return {'comments': _series(weeks, comments), 'votes': _series(weeks, votes),
            'top_builds': top, 'engagement': _engagement()}


ENGAGEMENT_BANDS = (('0', 0, 0), ('1-2', 1, 2), ('3-5', 3, 5), ('6-10', 6, 10), ('11+', 11, 10 ** 9))


def _engagement():
    """Shared builds bucketed by how many comments and votes they got."""
    shared = list(Char.objects.filter(link_shared=True, deleted=False).values_list('id', flat=True))
    if not shared:
        return []
    counts = Counter()
    for row in (BuildComment.objects.filter(deleted=False, build_id__in=shared)
                .values('build_id').annotate(n=Count('id'))):
        counts[row['build_id']] += row['n']
    for row in (BuildVote.objects.filter(build_id__in=shared)
                .values('build_id').annotate(n=Count('id'))):
        counts[row['build_id']] += row['n']
    bands = []
    for label, low, high in ENGAGEMENT_BANDS:
        bands.append((label, sum(1 for b in shared if low <= counts.get(b, 0) <= high)))
    return bands


def pages():
    now = timezone.localdate()
    month = now - datetime.timedelta(days=30)
    rows = (PageHit.objects.filter(day__gte=month).values('path')
            .annotate(n=Sum('count')).order_by('-n')[:30])
    per_version = (PageHit.objects.filter(day__gte=month).values('game_version')
                   .annotate(n=Sum('count')).order_by('-n'))
    weeks = _week_starts()
    daily = Counter()
    for row in PageHit.objects.filter(day__gte=weeks[0]).values('day').annotate(n=Sum('count')):
        day = row['day']
        daily[day - datetime.timedelta(days=day.weekday())] += row['n']
    return {
        'top': [(r['path'], r['n']) for r in rows],
        'by_version': [(VERSION_LABELS.get(r['game_version'], r['game_version']), r['n'])
                       for r in per_version],
        'per_week': _series(weeks, daily),
        'collecting_since': PageHit.objects.order_by('day').values_list('day', flat=True).first(),
    }


def solver():
    weeks = _week_starts()
    hits = {r['day']: r for r in SolutionMemoryHits.objects.filter(day__gte=weeks[0]).values()}
    per_week_hit, per_week_miss = Counter(), Counter()
    for day, row in hits.items():
        start = day - datetime.timedelta(days=day.weekday())
        per_week_hit[start] += row['count_hit']
        per_week_miss[start] += row['count_miss']
    total_hit = SolutionMemoryHits.objects.aggregate(n=Sum('count_hit'))['n'] or 0
    total_miss = SolutionMemoryHits.objects.aggregate(n=Sum('count_miss'))['n'] or 0
    return {
        'hits': _series(weeks, per_week_hit),
        'misses': _series(weeks, per_week_miss),
        'hit_rate': round(total_hit * 100.0 / (total_hit + total_miss)) if (total_hit + total_miss) else None,
        'no_solution': [
            (VERSION_LABELS.get(slug, slug),
             Char.objects.filter(deleted=False, game_version=slug, minimal_solution=b'').count())
            for slug in VERSIONS],
    }


def dashboard(refresh=False):
    if not refresh:
        cached = cache.get(CACHE_KEY)
        if cached:
            return cached
    data = {'overview': overview(), 'versions': versions(), 'community': community(),
            'pages': pages(), 'solver': solver(),
            'generated': timezone.localtime().strftime('%d/%m %H:%M')}
    cache.set(CACHE_KEY, data, CACHE_SECONDS)
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
