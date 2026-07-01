# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Public, read-only REST API.

Goal: let other tools (Twitch overlays, Discord bots, fan sites) read what
the community has shared on dofusfashionista. No auth, no DRF. CORS open
because the data is already public. Cached for 60 s to absorb bursts.
"""

from django.db.models import Count, Case, When, IntegerField
from django.http import JsonResponse, Http404
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_GET

from chardata.encoded_char_id import encode_char_id, decode_char_id
from chardata.models import BuildComment, BuildTag, Char, UserAlias

API_VERSION = 'v1'
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20


def _add_cors(response):
    response['Access-Control-Allow-Origin'] = '*'
    response['Access-Control-Allow-Methods'] = 'GET, OPTIONS'
    response['Access-Control-Allow-Headers'] = 'Content-Type'
    return response


def _json(data, status=200):
    return _add_cors(JsonResponse(data, status=status, json_dumps_params={'ensure_ascii': False}))


def _creator(char, alias_map):
    if not char.owner_id:
        return None
    return alias_map.get(char.owner_id) or (char.owner.username if char.owner else None)


def _build_payload(char, alias_map, tags_by_char=None, include_tags=True):
    encoded = encode_char_id(int(char.id))
    payload = {
        'id': encoded,
        'name': char.name,
        'char_name': char.char_name,
        'char_class': char.char_class,
        'level': char.level,
        'game_version': char.game_version,
        'creator': _creator(char, alias_map),
        'like_count': getattr(char, 'like_count', None) or 0,
        'favorite_count': getattr(char, 'favorite_count', None) or 0,
        'view_count': char.view_count,
        'created_at': char.created_time.isoformat() if char.created_time else None,
        'modified_at': char.modified_time.isoformat() if char.modified_time else None,
    }
    if include_tags:
        if tags_by_char is None:
            tags = list(BuildTag.objects.filter(char=char).order_by('created_time')
                        .values_list('display_name', flat=True))
        else:
            tags = [t['display_name'] for t in tags_by_char.get(char.id, [])]
        payload['tags'] = tags
    return payload


@require_GET
def api_meta(request):
    return _json({
        'api_version': API_VERSION,
        'endpoints': [
            'GET /api/v1/shared-builds/?game_version=dofus3&page=1&page_size=20',
            'GET /api/v1/shared-builds/<encoded_id>/',
            'GET /api/v1/tier-list/?game_version=dofus3&char_class=Iop',
        ],
        'docs': 'https://dofusfashionista.gg/about/',
    })


@require_GET
@cache_page(60)
def api_shared_builds(request):
    game_version = request.GET.get('game_version', 'dofus3')
    try:
        page = max(1, int(request.GET.get('page', 1)))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    qs = (Char.objects
          .filter(link_shared=True, deleted=False, game_version=game_version)
          .select_related('owner')
          .annotate(
              like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                    output_field=IntegerField())),
              favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                        output_field=IntegerField())),
          )
          .order_by('-modified_time'))

    total = qs.count()
    start = (page - 1) * page_size
    rows = list(qs[start:start + page_size])

    owner_ids = [r.owner_id for r in rows if r.owner_id]
    alias_map = {a.user_id: a.alias
                 for a in UserAlias.objects.filter(user_id__in=owner_ids) if a.alias}

    tags_by_char = {}
    if rows:
        for t in BuildTag.objects.filter(char_id__in=[r.id for r in rows]).order_by('created_time'):
            tags_by_char.setdefault(t.char_id, []).append({'display_name': t.display_name})

    return _json({
        'page': page,
        'page_size': page_size,
        'total': total,
        'results': [_build_payload(r, alias_map, tags_by_char) for r in rows],
    })


@require_GET
@cache_page(60)
def api_shared_build_detail(request, encoded_id):
    try:
        char_id = decode_char_id(encoded_id)
    except Exception:
        raise Http404
    try:
        char = (Char.objects
                .select_related('owner')
                .annotate(
                    like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                          output_field=IntegerField())),
                    favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                              output_field=IntegerField())),
                )
                .get(id=char_id, link_shared=True, deleted=False))
    except Char.DoesNotExist:
        raise Http404

    alias_map = {}
    if char.owner_id:
        ua = UserAlias.objects.filter(user_id=char.owner_id).first()
        if ua and ua.alias:
            alias_map[char.owner_id] = ua.alias

    payload = _build_payload(char, alias_map)
    payload['comment_count'] = BuildComment.objects.filter(build=char, deleted=False).count()
    payload['url'] = request.build_absolute_uri('/s/%s/%s/' % (char.char_name or 'shared', encoded_id))
    return _json(payload)


@require_GET
@cache_page(60)
def api_tier_list(request):
    game_version = request.GET.get('game_version', 'dofus3')
    char_class = request.GET.get('char_class')
    try:
        top_n = max(1, min(int(request.GET.get('top', 5)), 20))
    except (TypeError, ValueError):
        top_n = 5

    qs = (Char.objects
          .filter(link_shared=True, deleted=False, game_version=game_version)
          .select_related('owner')
          .annotate(
              like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                    output_field=IntegerField())),
              favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                        output_field=IntegerField())),
          ))
    if char_class:
        qs = qs.filter(char_class=char_class)
    rows = list(qs)
    owner_ids = [r.owner_id for r in rows if r.owner_id]
    alias_map = {a.user_id: a.alias
                 for a in UserAlias.objects.filter(user_id__in=owner_ids) if a.alias}

    by_class = {}
    for r in rows:
        score = (r.like_count or 0) * 3 + (r.favorite_count or 0) * 5 + min(50, r.view_count or 0)
        payload = _build_payload(r, alias_map, include_tags=False)
        payload['score'] = score
        by_class.setdefault(r.char_class or 'Unknown', []).append(payload)

    sections = []
    for cls, builds in by_class.items():
        builds.sort(key=lambda b: b['score'], reverse=True)
        sections.append({'char_class': cls, 'count': len(builds), 'top': builds[:top_n]})
    sections.sort(key=lambda s: s['count'], reverse=True)

    return _json({'game_version': game_version, 'sections': sections})
