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

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.contrib.auth.models import User

from chardata import admin_stats
from chardata.encoded_char_id import encode_char_id
from chardata.models import BuildComment, Char, CommentReport, SiteSetting
from chardata.util import set_response, request_by_super_user


def _is_admin(request):
    """Admin = the app's configured super-user email OR a Django superuser."""
    user = request.user
    if user.is_anonymous:
        return False
    return request_by_super_user(request) or user.is_superuser


def _require_admin(request):
    if not _is_admin(request):
        raise Http404


def _reason_label(reason):
    return dict(CommentReport.REASON_CHOICES).get(reason, reason)


def _build_url(build):
    """Public shared-build URL, or None if the build isn't shared anymore."""
    if not build or not build.link_shared or build.deleted:
        return None
    return '/s/%s/%s/' % (build.char_name or 'shared', encode_char_id(int(build.id)))


def admin_tools(request, char_id=0):
    _require_admin(request)

    now = timezone.now()
    week_ago = now - timedelta(days=7)

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

    data = admin_stats.dashboard(refresh=request.GET.get('refresh') == '1',
                                 period_key=request.GET.get('period'),
                                 version=request.GET.get('version'),
                                 start=request.GET.get('from'),
                                 end=request.GET.get('to'))

    return set_response(request, 'chardata/admin_tools.html', {
        'request': request,
        'user': request.user,
        'char_id': char_id,
        'noindex': True,
        'stats': stats,
        'reported_comments': reported,
        'recent_comments': recent_comments,
        'dash': data,
        'charts': _charts(data),
        'ad_config': _ad_form(),
        'preview_cache': _preview_cache(),
    })


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
            'slots': [{'name': name, 'value': slots.get(name, '')}
                      for name in AD_SLOTS]}


VERSION_COLOURS = {'dofus3': '#c8a05a', 'beta': '#7aa6c2', 'dofus2': '#8fae7a',
                   'touch': '#b98a9e', 'retro': '#9c8ab9'}


def _charts(data):
    versions = {admin_stats.VERSION_LABELS.get(slug, slug): series
                for slug, series in data['overview']['builds_by_version'].items()}
    colours = {admin_stats.VERSION_LABELS.get(slug, slug): colour
               for slug, colour in VERSION_COLOURS.items()}
    charts = {
        'accounts': admin_stats.bar_chart(data['overview']['accounts']),
        'builds': admin_stats.stacked_chart(versions, colours),
        'comments': admin_stats.bar_chart(data['community']['comments']),
        'votes': admin_stats.bar_chart(data['community']['votes'], colour='#7aa6c2'),
        'engagement': admin_stats.bar_chart(data['community']['engagement']),
        'pages_per_week': admin_stats.bar_chart(data['pages']['per_week']),
        'solver_hits': admin_stats.stacked_chart(
            {'cache hit': data['solver']['hits'], 'cache miss': data['solver']['misses']},
            {'cache hit': '#8fae7a', 'cache miss': '#c0764a'}),
    }
    charts['levels'] = {
        admin_stats.VERSION_LABELS.get(slug, slug): admin_stats.bar_chart(bands, height=90)
        for slug, bands in data['versions']['levels'].items()}
    return charts


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

    def over(days):
        since = today - timedelta(days=days - 1)
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
                  .filter(day__gte=today - timedelta(days=29))
                  .exclude(country='')
                  .values('country').annotate(visits=Sum('count'))
                  .order_by('-visits')[:12])
    by_language = (VisitSource.objects
                   .filter(day__gte=today - timedelta(days=29))
                   .exclude(language='')
                   .values('language').annotate(visits=Sum('count'))
                   .order_by('-visits')[:8])

    return render(request, 'chardata/provenance.html', {
        'periods': [over(7), over(30)],
        'by_country': list(by_country),
        'by_language': list(by_language),
        'first_day': (VisitSource.objects.order_by('day')
                      .values_list('day', flat=True).first()),
        'today': today,
    })
