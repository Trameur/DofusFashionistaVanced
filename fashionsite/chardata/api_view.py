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

from django.db.models import Count, Case, When, F, IntegerField, Value
from django.db.models.functions import Least
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
@cache_page(300)
def api_meta(request):
    return _json({
        'api_version': API_VERSION,
        'endpoints': [
            'GET /api/v1/shared-builds/?game_version=dofus3&page=1&page_size=20',
            'GET /api/v1/shared-builds/<encoded_id>/',
            'GET /api/v1/tier-list/?game_version=dofus3&char_class=Iop',
        ],
        'docs': 'https://dofusfashionista.gg/about/#api',
    })


# Far past any real gallery, and small enough to stay a valid OFFSET.
MAX_PAGE = 100000


@require_GET
@cache_page(60)
def api_shared_builds(request):
    game_version = request.GET.get('game_version', 'dofus3')
    try:
        # A ceiling as well as a floor: the value becomes a literal SQL OFFSET
        # and a big enough one is not an integer the database will take.
        page = max(1, min(int(request.GET.get('page', 1)), MAX_PAGE))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    # A build whose solution was never stored has no /s/ page: the gallery and
    # the sitemap both skip it, and a consumer turning this id into a url would
    # land on a 404.
    qs = (Char.objects
          .filter(link_shared=True, deleted=False, game_version=game_version)
          .exclude(minimal_solution=b'')
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

    # A build whose solution was never stored has no /s/ page: the gallery and
    # the sitemap both skip it, and a consumer turning this id into a url would
    # land on a 404.
    qs = (Char.objects
          .filter(link_shared=True, deleted=False, game_version=game_version)
          .exclude(minimal_solution=b'')
          .select_related('owner')
          .annotate(
              like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                    output_field=IntegerField())),
              favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                        output_field=IntegerField())),
          ))
    if char_class:
        qs = qs.filter(char_class=char_class)

    # Only the top few builds of each class are returned, so nothing else has to
    # be built or even loaded. This used to read every shared build of the
    # version into memory, and a Char row carries nine pickled columns including
    # the stored solution.
    counts = {row['char_class'] or 'Unknown': row['n']
              for row in qs.values('char_class').annotate(n=Count('id', distinct=True))}
    ranked = (qs
              .annotate(score=(F('like_count') * 3 + F('favorite_count') * 5
                               + Least(F('view_count'), Value(50))))
              # owner__username by name, so the creator line does not become a
              # query per row against the deferred owner.
              .only('id', 'name', 'char_name', 'char_class', 'level',
                    'game_version', 'view_count', 'created_time',
                    'modified_time', 'owner', 'owner__username')
              .order_by('-score', '-id'))

    wanted = {cls: min(top_n, n) for cls, n in counts.items()}
    picked = {}
    aliases_needed = set()
    for row in ranked.iterator(chunk_size=100):
        cls = row.char_class or 'Unknown'
        bucket = picked.setdefault(cls, [])
        if len(bucket) >= wanted.get(cls, top_n):
            if all(len(picked.get(c, [])) >= w for c, w in wanted.items()):
                break
            continue
        bucket.append(row)
        if row.owner_id:
            aliases_needed.add(row.owner_id)

    alias_map = {a.user_id: a.alias
                 for a in UserAlias.objects.filter(user_id__in=aliases_needed)
                 if a.alias}

    sections = []
    for cls, rows in picked.items():
        top = []
        for row in rows:
            payload = _build_payload(row, alias_map, include_tags=False)
            payload['score'] = row.score
            top.append(payload)
        sections.append({'char_class': cls, 'count': counts.get(cls, len(rows)),
                         'top': top})
    sections.sort(key=lambda s: s['count'], reverse=True)

    return _json({'game_version': game_version, 'sections': sections})
