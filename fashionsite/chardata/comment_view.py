# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Comments on shared builds. Mirrors the BuildVote pattern.

Includes content moderation (chardata.moderation), opt-out email notifications
to the build owner, and a community report endpoint that mails admins (and
auto-hides a comment once it has 3 distinct reports).
"""

import logging

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.db import IntegrityError
from django.http import JsonResponse
from django.template.loader import render_to_string
from django.utils.translation import gettext as _, override as translation_override
from django.views.decorators.http import require_POST

from chardata.encoded_char_id import encode_char_id
from chardata.models import BuildComment, Char, CommentReport, UserAlias
from chardata.moderation import validate_comment


logger = logging.getLogger(__name__)

MAX_CONTENT_LENGTH = 2000
MIN_CONTENT_LENGTH = 1
AUTO_HIDE_REPORT_THRESHOLD = 3
NOTIFY_EXTRACT_LENGTH = 200


def _serialize_comment(comment, request_user):
    display_name = comment.user.username
    try:
        alias = comment.user.useralias.alias
        if alias:
            display_name = alias
    except UserAlias.DoesNotExist:
        pass

    can_delete = bool(
        request_user.is_authenticated
        and (request_user.id == comment.user_id or request_user.is_superuser)
    )
    can_report = bool(
        request_user.is_authenticated
        and request_user.id != comment.user_id
    )
    return {
        'id': comment.id,
        'content': comment.content,
        'created_time': comment.created_time.isoformat() if comment.created_time else '',
        'author': display_name,
        'can_delete': can_delete,
        'can_report': can_report,
    }


def get_comments_for_build(build, request_user):
    """Return active comments (oldest first) ready for the template."""
    comments = (BuildComment.objects
                .filter(build=build, deleted=False)
                .select_related('user', 'user__useralias')
                .order_by('created_time'))
    return [_serialize_comment(c, request_user) for c in comments]


def _build_share_url(request, build):
    encoded = encode_char_id(int(build.id))
    name = build.char_name or 'shared'
    prefix = ''
    game_version = getattr(request, 'game_version', 'dofus3')
    if game_version != 'dofus3':
        prefix = '/' + game_version
    return request.build_absolute_uri(f'{prefix}/s/{name}/{encoded}/')


def _author_language(owner):
    """Best-effort language of the build owner. Falls back to LANGUAGE_CODE."""
    try:
        if owner.useralias and owner.useralias.language:
            return owner.useralias.language
    except UserAlias.DoesNotExist:
        pass
    return getattr(settings, 'LANGUAGE_CODE', 'en')


def _notify_build_owner(request, build, comment):
    """Email the build owner when someone else comments on their build.

    Silent on failure, a SMTP hiccup must not break the comment POST.
    """
    owner = build.owner
    if owner is None or not owner.email:
        return
    if owner.id == comment.user_id:
        return  # don't notify self-comments

    # Opt-out check
    try:
        if owner.useralias and not owner.useralias.notify_comments:
            return
    except UserAlias.DoesNotExist:
        pass

    try:
        commenter_name = comment.user.username
        try:
            if comment.user.useralias and comment.user.useralias.alias:
                commenter_name = comment.user.useralias.alias
        except UserAlias.DoesNotExist:
            pass

        extract = comment.content
        if len(extract) > NOTIFY_EXTRACT_LENGTH:
            extract = extract[:NOTIFY_EXTRACT_LENGTH].rstrip() + '…'

        ctx = {
            'build_name': build.name or build.char_name or 'your build',
            'commenter_name': commenter_name,
            'extract': extract,
            'build_url': _build_share_url(request, build),
            'site_name': 'Dofus Fashionista',
        }

        with translation_override(_author_language(owner)):
            subject = _('New comment on your build "%(build_name)s"') % {'build_name': ctx['build_name']}
            text_body = render_to_string('chardata/emails/new_comment.txt', ctx)
            html_body = render_to_string('chardata/emails/new_comment.html', ctx)

        send_mail(
            subject=subject,
            message=text_body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner.email],
            html_message=html_body,
            fail_silently=True,
        )
    except Exception:
        logger.exception('Failed to send new-comment notification',
                         extra={'build_id': build.id, 'comment_id': comment.id})


@login_required
@require_POST
def post_comment(request, build_id):
    content = (request.POST.get('content') or '').strip()
    if len(content) < MIN_CONTENT_LENGTH:
        return JsonResponse({'error': _('Comment is empty')}, status=400)
    if len(content) > MAX_CONTENT_LENGTH:
        return JsonResponse({'error': _('Comment is too long')}, status=400)

    is_clean, error_message = validate_comment(content)
    if not is_clean:
        return JsonResponse({'error': str(error_message)}, status=400)

    try:
        build = Char.objects.select_related('owner', 'owner__useralias').get(
            id=build_id, link_shared=True, deleted=False)
    except Char.DoesNotExist:
        return JsonResponse({'error': _('Build not found')}, status=404)

    comment = BuildComment.objects.create(user=request.user, build=build, content=content)
    _notify_build_owner(request, build, comment)

    return JsonResponse({'success': True, 'comment': _serialize_comment(comment, request.user)})


@login_required
@require_POST
def delete_comment(request, comment_id):
    try:
        comment = BuildComment.objects.get(id=comment_id, deleted=False)
    except BuildComment.DoesNotExist:
        return JsonResponse({'error': _('Comment not found')}, status=404)

    if comment.user_id != request.user.id and not request.user.is_superuser:
        return JsonResponse({'error': _('Not allowed')}, status=403)

    comment.deleted = True
    comment.save(update_fields=['deleted'])
    return JsonResponse({'success': True, 'comment_id': comment.id})


@login_required
@require_POST
def report_comment(request, comment_id):
    try:
        comment = BuildComment.objects.select_related('user', 'build').get(
            id=comment_id, deleted=False)
    except BuildComment.DoesNotExist:
        return JsonResponse({'error': _('Comment not found')}, status=404)

    if comment.user_id == request.user.id:
        return JsonResponse({'error': _('You cannot report your own comment')}, status=400)

    reason = request.POST.get('reason', 'other')
    if reason not in dict(CommentReport.REASON_CHOICES):
        reason = 'other'

    try:
        CommentReport.objects.create(user=request.user, comment=comment, reason=reason)
    except IntegrityError:
        return JsonResponse({'error': _('You already reported this comment')}, status=400)

    # Notify admins (routed through the django.request mail_admins handler via
    # logger.error). The T3 rate-limit filter will dedupe bursts on the same
    # comment_id since the signature is built from the log location.
    logger.error(
        'Comment %s reported by user %s (reason=%s, build=%s, author=%s): %r',
        comment.id, request.user.id, reason, comment.build_id, comment.user_id,
        comment.content[:200],
    )

    # Auto-hide once enough distinct users have reported it.
    distinct_reports = (CommentReport.objects
                        .filter(comment=comment)
                        .values_list('user_id', flat=True)
                        .distinct()
                        .count())
    auto_hidden = False
    if distinct_reports >= AUTO_HIDE_REPORT_THRESHOLD:
        comment.deleted = True
        comment.save(update_fields=['deleted'])
        auto_hidden = True

    return JsonResponse({
        'success': True,
        'comment_id': comment.id,
        'auto_hidden': auto_hidden,
        'distinct_reports': distinct_reports,
    })
