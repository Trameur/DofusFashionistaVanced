# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Staff-only dashboard with lightweight moderation and site tools.

A non-admin gets a plain 404 on every entry point, not a 403.
"""
from collections import defaultdict
from datetime import timedelta

from django.core.cache import cache
from django.http import Http404, HttpResponse, JsonResponse
from django.template.loader import render_to_string
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.contrib.auth.models import User

from chardata import admin_history, admin_stats
from chardata.encoded_char_id import encode_char_id
from chardata.models import BuildComment, Char, CommentReport, SiteSetting
from chardata.util import set_response, request_by_super_user
from chardata.util import shared_build_path


def _is_admin(request):
    """Admin = a signed-in Django superuser."""
    return request_by_super_user(request)


def _require_admin(request):
    if not _is_admin(request):
        raise Http404


def _reason_label(reason):
    return dict(CommentReport.REASON_CHOICES).get(reason, reason)


def _build_url(build):
    """Public shared-build URL, or None if the build isn't shared anymore."""
    if not build or not build.link_shared or build.deleted:
        return None
    return shared_build_path(build)


TABS = (('history', 'History'), ('overview', 'Overview'),
        ('versions', 'Game versions'), ('community', 'Community'),
        ('pages', 'Pages'), ('imports', 'Import and export'),
        ('solver', 'Solver'), ('moderation', 'Moderation'), ('ads', 'Ads'))
DEFAULT_TAB = 'history'
#: The sections each tab computes, and only those
TAB_SECTIONS = {'overview': ('overview',), 'versions': ('versions',),
                'community': ('community',), 'pages': ('pages',),
                'imports': ('imports', 'exports'), 'solver': ('solver',)}


def _pending_report_count():
    return (CommentReport.objects.filter(processed=False)
            .values('comment_id').distinct().count())


def _moderation(week_ago):
    """The reported comments, the recent feed and the at-a-glance numbers."""
    # --- Reported comments still awaiting a decision -------------------------
    pending_comment_ids = list(
        CommentReport.objects.filter(processed=False)
        .values_list('comment_id', flat=True).distinct())

    reports_by_comment = defaultdict(list)
    if pending_comment_ids:
        for rep in (CommentReport.objects
                    .filter(comment_id__in=pending_comment_ids)
                    .select_related('user', 'user__useralias')):
            reports_by_comment[rep.comment_id].append(rep)

    reported = []
    if pending_comment_ids:
        comments = (BuildComment.objects
                    .filter(id__in=pending_comment_ids)
                    .select_related('user', 'user__useralias', 'build')
                    .order_by('-created_time'))
        for c in comments:
            reps = reports_by_comment.get(c.id, [])
            reasons = sorted({_reason_label(r.reason) for r in reps})
            reported.append({
                'comment': c,
                'author': _display_name(c.user),
                'report_count': len({r.user_id for r in reps}),
                'reasons': ', '.join(reasons),
                'build_name': c.build.name or c.build.char_name or '-',
                'build_url': _build_url(c.build),
            })

    # --- Recent comments (moderation feed) ----------------------------------
    recent_comments = []
    for c in (BuildComment.objects
              .select_related('user', 'user__useralias', 'build')
              .order_by('-created_time')[:50]):
        recent_comments.append({
            'comment': c,
            'author': _display_name(c.user),
            'build_name': c.build.name or c.build.char_name or '-',
            'build_url': _build_url(c.build),
        })

    # --- At-a-glance stats --------------------------------------------------
    stats = {
        'users_total': User.objects.count(),
        'users_new_7d': User.objects.filter(date_joined__gte=week_ago).count(),
        'shared_builds': Char.objects.filter(link_shared=True, deleted=False).count(),
        'comments_visible': BuildComment.objects.filter(deleted=False).count(),
        'comments_deleted': BuildComment.objects.filter(deleted=True).count(),
        'comments_new_7d': BuildComment.objects.filter(created_time__gte=week_ago).count(),
        'reports_pending': len(pending_comment_ids),
    }
    return {'stats': stats, 'reported_comments': reported,
            'recent_comments': recent_comments}


def admin_tools(request, char_id=0):
    """The shell with the active tab in place, or with fragment=1 only that tab's panel."""
    _require_admin(request)

    tab = request.GET.get('tab')
    if tab not in dict(TABS):
        tab = DEFAULT_TAB
    refresh = request.GET.get('refresh') == '1'
    now = timezone.now()

    if refresh:
        cache.delete(admin_stats.FIRST_DAY_KEY)
    period = admin_stats.resolve_period(
        request.GET.get('period'), request.GET.get('from'), request.GET.get('to'),
        scan=tab in TAB_SECTIONS)
    version = admin_stats.resolve_version(request.GET.get('version'))

    dash = {'filters': admin_stats.filters(period, version, tab)}
    generated = None
    for name in TAB_SECTIONS.get(tab, ()):
        dash[name], made = admin_stats.section(name, period, version, refresh)
        generated = generated or made
    dash['generated'] = generated or timezone.localtime(now).strftime('%d/%m %H:%M')

    context = {
        'request': request,
        'user': request.user,
        'char_id': char_id,
        'noindex': True,
        'dash': dash,
        'tab': tab,
        'filters_apply': tab in TAB_SECTIONS,
    }
    if tab == 'history':
        context['history_loaded'] = admin_history.is_loaded()
    elif tab == 'overview':
        context['preview_cache'] = _preview_cache()
        fill = _estimated_months(period, version)
        context['charts'] = _charts(tab, dash, fill)
        context['estimates_note'] = bool(fill)
    elif tab in TAB_SECTIONS:
        context['charts'] = _charts(tab, dash)
    elif tab == 'moderation':
        context.update(_moderation(now - timedelta(days=7)))
    elif tab == 'ads':
        context['ad_config'] = _ad_form()

    pending = (context['stats']['reports_pending'] if tab == 'moderation'
               else _pending_report_count())
    context['tabs'] = [{'name': name, 'label': label, 'active': name == tab,
                        'template': 'chardata/admin/panel_%s.html' % name,
                        'badge': pending if name == 'moderation' else 0}
                       for name, label in TABS]

    if request.GET.get('fragment') == '1':
        response = HttpResponse(render_to_string(
            'chardata/admin/panel_%s.html' % tab, context))
        response['Cache-Control'] = 'private, no-store'
        response['X-Robots-Tag'] = 'noindex'
        # The minifier would wrap a fragment in html, head and body
        response.minify_response = False
        return response
    return set_response(request, 'chardata/admin_tools.html', context)


def admin_history_json(request):
    """The merged history as JSON, for the History tab."""
    _require_admin(request)
    response = JsonResponse(admin_history.payload(
        refresh=request.GET.get('refresh') == '1'))
    response['Cache-Control'] = 'private, no-store'
    return response


def _preview_cache():
    from chardata.character_assets import cache_report
    try:
        report = cache_report()
    except Exception:
        return None
    report['ok'] = not report.get('missing_total')
    return report


def _ad_form():
    from chardata.context_processors import ad_config
    config = ad_config()
    slots = config.get('slots') or {}
    return {'enabled': config.get('enabled', True),
            'auto': config.get('auto', True),
            'read_failed': config.get('read_failed', False),
            'slots': [{'name': name, 'value': slots.get(name, '')}
                      for name in AD_SLOTS]}


VERSION_COLOURS = {'dofus3': 'var(--ad-s1)', 'beta': 'var(--ad-s5)', 'dofus2': 'var(--ad-s2)',
                   'touch': 'var(--ad-s3)', 'retro': 'var(--ad-s4)'}


ESTIMATE_COLOUR = 'var(--ad-est)'
ESTIMATE_NAME = 'estimated or corrected'
#: Overview metrics that have estimated months before the first record
FILLED_CHARTS = (('accounts', 'accounts_real'), ('builds', 'builds_real'))


def _month_label(month):
    return '%s/%s' % (month[5:7], month[2:4])


def _estimated_months(period, version):
    """{chart: [(label, value)]} of the estimated months before the first record, when they apply."""
    if period.key != 'all' or period.custom or period.approximate or version or period.unit != 'month':
        return {}
    first_month = period.buckets[0].strftime('%Y-%m')
    fill = {}
    for chart, metric in FILLED_CHARTS:
        rows = admin_history.estimated_before(metric, first_month)
        if rows:
            fill[chart] = [(_month_label(row[0]), int(round(row[1]))) for row in rows]
    return fill


def _with_estimates(series, estimates):
    """Pad a series with zero bars where the estimates are, and the estimates with zero bars where it is."""
    return ([(label, 0) for label, _v in estimates] + list(series),
            list(estimates) + [(label, 0) for label, _v in series])


def _charts(tab, data, fill=None):
    fill = fill or {}
    if tab == 'overview':
        versions = {admin_stats.VERSION_LABELS.get(slug, slug): series
                    for slug, series in data['overview']['builds_by_version'].items()}
        colours = {admin_stats.VERSION_LABELS.get(slug, slug): colour
                   for slug, colour in VERSION_COLOURS.items()}
        accounts = admin_stats.bar_chart(data['overview']['accounts'])
        if 'accounts' in fill:
            measured, estimated = _with_estimates(data['overview']['accounts'],
                                                  fill['accounts'])
            accounts = admin_stats.stacked_chart(
                {'measured': measured, ESTIMATE_NAME: estimated},
                {'measured': 'var(--ad-s1)', ESTIMATE_NAME: ESTIMATE_COLOUR},
                hatched=(ESTIMATE_NAME,), pattern_id='est-accounts')
        hatched = ()
        if 'builds' in fill:
            padded = {}
            for label, series in versions.items():
                padded[label], estimated = _with_estimates(series, fill['builds'])
            padded[ESTIMATE_NAME] = estimated
            versions = padded
            colours = dict(colours, **{ESTIMATE_NAME: ESTIMATE_COLOUR})
            hatched = (ESTIMATE_NAME,)
        return {'accounts': accounts,
                'builds': admin_stats.stacked_chart(
                    versions, colours, hatched=hatched, pattern_id='est-builds')}
    if tab == 'versions':
        return {'levels': {
            admin_stats.VERSION_LABELS.get(slug, slug): admin_stats.bar_chart(bands, height=90)
            for slug, bands in data['versions']['levels'].items()}}
    if tab == 'community':
        return {
            'comments': admin_stats.bar_chart(data['community']['comments']),
            'votes': admin_stats.bar_chart(data['community']['votes'], colour='var(--ad-s2)'),
            'engagement': admin_stats.bar_chart(data['community']['engagement']),
        }
    if tab == 'pages':
        return {'pages_per_week': admin_stats.bar_chart(data['pages']['per_week'])}
    if tab == 'imports':
        return {
            'imports_per_bucket': admin_stats.bar_chart(data['imports']['per_bucket']),
            'exports_per_bucket': admin_stats.bar_chart(data['exports']['per_bucket']),
        }
    if tab == 'solver':
        return {'solver_hits': admin_stats.stacked_chart(
            {'cache hit': data['solver']['hits'], 'cache miss': data['solver']['misses']},
            {'cache hit': 'var(--ad-s3)', 'cache miss': 'var(--ad-s2)'})}
    return {}


def _display_name(user):
    if user is None:
        return '-'
    try:
        if user.useralias and user.useralias.alias:
            return user.useralias.alias
    except Exception:
        pass
    return user.username


AD_SLOTS = ('home_top', 'footer', 'encyclopedia_inline', 'guide_inline',
            'shared_inline', 'solution', 'list_inline', 'content_top', 'rail')


@require_POST
def admin_ads_action(request):
    """Turn the ads on or off and set the slot ids."""
    _require_admin(request)
    import json
    from django.core.cache import cache
    from chardata.context_processors import AD_SETTING_KEY

    slots = {}
    for name in AD_SLOTS:
        value = (request.POST.get('slot_' + name) or '').strip()
        if value and not value.isdigit():
            return JsonResponse(
                {'error': 'Slot ids are digits only: %s' % name}, status=400)
        if value:
            slots[name] = value
    stored = {'enabled': request.POST.get('enabled') == '1',
              'auto': request.POST.get('auto') == '1', 'slots': slots}
    SiteSetting.objects.update_or_create(
        key=AD_SETTING_KEY, defaults={'value': json.dumps(stored)})
    cache.delete(AD_SETTING_KEY)
    return JsonResponse({'success': True, 'enabled': stored['enabled'],
                         'slots': slots})


@require_POST
def admin_comment_action(request):
    """Moderate a comment. action = delete | restore | dismiss_reports."""
    _require_admin(request)

    try:
        comment = BuildComment.objects.get(id=request.POST.get('comment_id'))
    except (BuildComment.DoesNotExist, ValueError, TypeError):
        return JsonResponse({'error': 'Comment not found'}, status=404)

    action = request.POST.get('action')
    if action == 'delete':
        comment.deleted = True
        comment.save(update_fields=['deleted'])
        CommentReport.objects.filter(comment=comment, processed=False).update(processed=True)
    elif action == 'restore':
        comment.deleted = False
        comment.save(update_fields=['deleted'])
    elif action == 'dismiss_reports':
        CommentReport.objects.filter(comment=comment, processed=False).update(processed=True)
    else:
        return JsonResponse({'error': 'Unknown action'}, status=400)

    return JsonResponse({'success': True, 'comment_id': comment.id,
                         'deleted': comment.deleted, 'action': action})


def provenance(request):
    """Where the readers of the last 7 and 30 days came from.

    The site has always known how many people come and nothing at all about how
    they found it -- and 77 % of its search clicks are people typing its own
    name, so "how they found it" is the only question that matters for growth.
    This reads the table VisitSourceMiddleware fills, which holds a count per
    day and per provenance and nothing about any person.

    Admin-only, like every other page here: it is an instrument for the owner,
    not a public dashboard.
    """
    _require_admin(request)

    from django.db.models import Sum
    from chardata.models import SupportClick, VisitSource

    today = timezone.localdate()

    def from_day(days):
        return max(today - timedelta(days=days - 1), admin_stats.REAL_BROWSERS_SINCE)

    def over(days):
        since = from_day(days)
        rows = (VisitSource.objects.filter(day__gte=since)
                .values('source', 'medium')
                .annotate(visits=Sum('count')).order_by('-visits'))
        rows = list(rows)
        total = sum(r['visits'] for r in rows) or 0
        for r in rows:
            r['share'] = round(100.0 * r['visits'] / total, 1) if total else 0.0
        clicks = (SupportClick.objects.filter(day__gte=since)
                  .aggregate(n=Sum('count'))['n']) or 0
        return {
            'days': days,
            'since': since,
            'rows': rows[:40],
            'hidden': max(0, len(rows) - 40),
            'total': total,
            'support_clicks': clicks,
            # The number the whole instrument exists to produce. Below the
            # threshold written down in advance, courting content creators is
            # not worth the evenings it would cost.
            'support_rate': round(100.0 * clicks / total, 3) if total else None,
        }

    by_country = (VisitSource.objects
                  .filter(day__gte=from_day(30))
                  .exclude(country='')
                  .values('country').annotate(visits=Sum('count'))
                  .order_by('-visits')[:12])
    by_language = (VisitSource.objects
                   .filter(day__gte=from_day(30))
                   .exclude(language='')
                   .values('language').annotate(visits=Sum('count'))
                   .order_by('-visits')[:8])

    return set_response(request, 'chardata/provenance.html', {
        'periods': [over(7), over(30)],
        'by_country': list(by_country),
        'by_language': list(by_language),
        'first_day': (VisitSource.objects.order_by('day')
                      .values_list('day', flat=True).first()),
        'real_browsers_since': admin_stats.REAL_BROWSERS_SINCE,
        'today': today,
    })
