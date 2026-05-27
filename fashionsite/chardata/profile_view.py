# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Public user profile page + follow / unfollow endpoints."""

import logging

from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.db import IntegrityError
from django.db.models import Count, Case, When, IntegerField, Sum
from django.http import JsonResponse, Http404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST

from chardata.encoded_char_id import encode_char_id
from chardata.models import BuildVote, Char, UserAlias, UserFollow
from chardata.shared_builds_view import translate_build_name
from chardata.util import set_response, version_reverse


logger = logging.getLogger(__name__)
PROFILE_BUILDS_PAGE_SIZE = 20


def _resolve_user(alias_or_username):
    """Find a user by their alias (case-insensitive) first, then by username."""
    by_alias = (UserAlias.objects
                .filter(alias__iexact=alias_or_username)
                .select_related('user').first())
    if by_alias and by_alias.alias:
        return by_alias.user
    try:
        return User.objects.get(username__iexact=alias_or_username)
    except User.DoesNotExist:
        return None


def _display_name(user):
    try:
        if user.useralias and user.useralias.alias:
            return user.useralias.alias
    except UserAlias.DoesNotExist:
        pass
    return user.username


def user_profile(request, alias):
    target = _resolve_user(alias)
    if target is None:
        raise Http404

    game_version = getattr(request, 'game_version', 'dofus3')
    builds_qs = (Char.objects
                 .filter(owner=target, link_shared=True, deleted=False,
                         game_version=game_version)
                 .annotate(
                     like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                           output_field=IntegerField())),
                     favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                               output_field=IntegerField())),
                 )
                 .order_by('-modified_time')[:PROFILE_BUILDS_PAGE_SIZE])

    builds = []
    for b in builds_qs:
        encoded = encode_char_id(int(b.id))
        char_name = b.char_name or 'shared'
        builds.append({
            'char': b,
            'link': request.build_absolute_uri(
                version_reverse(request, 'solution_linked', char_name, encoded)),
            'like_count': b.like_count or 0,
            'favorite_count': b.favorite_count or 0,
            'view_count': b.view_count or 0,
            'build_name_translated': translate_build_name(b.char_build or ''),
        })

    total_likes_received = (BuildVote.objects
                            .filter(build__owner=target, build__link_shared=True,
                                    build__deleted=False, vote_type='like')
                            .count())
    total_favorites_received = (BuildVote.objects
                                .filter(build__owner=target, build__link_shared=True,
                                        build__deleted=False, vote_type='favorite')
                                .count())
    total_views = (Char.objects
                   .filter(owner=target, link_shared=True, deleted=False)
                   .aggregate(t=Sum('view_count'))['t']) or 0
    follower_count = UserFollow.objects.filter(followed=target).count()
    following_count = UserFollow.objects.filter(follower=target).count()

    is_following = False
    is_self = False
    if request.user.is_authenticated:
        is_self = (request.user.id == target.id)
        if not is_self:
            is_following = UserFollow.objects.filter(
                follower=request.user, followed=target).exists()

    return set_response(request, 'chardata/user_profile.html', {
        'profile_user': target,
        'profile_display_name': _display_name(target),
        'builds': builds,
        'total_likes_received': total_likes_received,
        'total_favorites_received': total_favorites_received,
        'total_views': total_views,
        'follower_count': follower_count,
        'following_count': following_count,
        'is_following': is_following,
        'is_self': is_self,
    })


@login_required
@require_POST
def follow_user(request, user_id):
    if int(user_id) == request.user.id:
        return JsonResponse({'error': _('You cannot follow yourself')}, status=400)
    try:
        target = User.objects.get(id=user_id)
    except User.DoesNotExist:
        return JsonResponse({'error': _('User not found')}, status=404)
    try:
        UserFollow.objects.create(follower=request.user, followed=target)
        created = True
    except IntegrityError:
        created = False
    follower_count = UserFollow.objects.filter(followed=target).count()
    return JsonResponse({'success': True, 'created': created,
                         'follower_count': follower_count})


@login_required
@require_POST
def unfollow_user(request, user_id):
    deleted, _details = UserFollow.objects.filter(
        follower=request.user, followed_id=user_id).delete()
    target_id = int(user_id)
    follower_count = UserFollow.objects.filter(followed_id=target_id).count()
    return JsonResponse({'success': True, 'removed': bool(deleted),
                         'follower_count': follower_count})
