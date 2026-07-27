# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Staff-only dashboard with lightweight moderation and site tools.

Distinct from Django's /admin/: this is a quick, task-focused page for the
day-to-day (review reported comments, glance at site activity) without the
model-form overhead. Every entry point is gated to admins only; a non-admin
gets a plain 404 so the page's existence is not revealed.
"""
from collections import defaultdict
from datetime import timedelta

from django.http import Http404, JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_POST

from django.contrib.auth.models import User

from chardata import admin_stats
from chardata.encoded_char_id import encode_char_id
from chardata.models import BuildComment, Char, CommentReport
from chardata.util import set_response, request_by_super_user


def _is_admin(request):
    """Admin = the app's configured super-user email OR a Django superuser.
    Accepting either avoids locking the owner out if only one is set up."""
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

    data = admin_stats.dashboard(refresh=request.GET.get('refresh') == '1')

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
    })


VERSION_COLOURS = {'dofus3': '#c8a05a', 'beta': '#7aa6c2', 'dofus2': '#8fae7a',
                   'touch': '#b98a9e', 'retro': '#9c8ab9'}


def _charts(data):
    """SVG built server side: the page pulls in no charting library."""
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
