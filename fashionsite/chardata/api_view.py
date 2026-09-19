# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Public read-only REST API, no auth, open CORS."""

from django.db.models import Count, Case, When, F, IntegerField, Value
from chardata.build_name import display_name
from chardata.data_versions import patch_of
from chardata.util import shared_build_path
from django.db.models.functions import Least
from django.http import HttpResponse, JsonResponse
from django.views.decorators.cache import cache_page
from functools import wraps

from chardata.encoded_char_id import encode_char_id, decode_char_id
from chardata.models import BuildComment, BuildTag, Char, UserAlias
from chardata.url_language import SITE_URL

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


def _api_endpoint(view):
    """GET and OPTIONS with CORS on every answer; keep it above cache_page."""
    @wraps(view)
    def enveloppe(request, *args, **kwargs):
        if request.method == 'OPTIONS':
            return _add_cors(HttpResponse(status=204))
        if request.method not in ('GET', 'HEAD'):
            refus = _json({'error': 'method not allowed',
                           'allowed': ['GET', 'OPTIONS']}, status=405)
            refus['Allow'] = 'GET, OPTIONS'
            return refus
        return view(request, *args, **kwargs)
    return enveloppe


def _absent(quoi):
    """JSON 404 with CORS headers."""
    return _json({'error': 'not found', 'resource': quoi}, status=404)


def _creator(char, alias_map):
    if not char.owner_id:
        return None
    return alias_map.get(char.owner_id) or (char.owner.username if char.owner else None)


def _build_payload(char, alias_map, tags_by_char=None, include_tags=True):
    """One shared build, as all three endpoints render it."""
    encoded = encode_char_id(int(char.id))
    payload = {
        'id': encoded,
        # Never empty, consumers print it as is
        'name': display_name(char),
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
        'created_version': char.created_version or None,
        'solved_version': char.solved_version or None,
        'solved_patch': patch_of(char.solved_version),
    }
    # Canonical address, not the request host
    payload['url'] = SITE_URL + shared_build_path(char)
    if include_tags:
        if tags_by_char is None:
            tags = list(BuildTag.objects.filter(char=char).order_by('created_time')
                        .values_list('display_name', flat=True))
        else:
            tags = [t['display_name'] for t in tags_by_char.get(char.id, [])]
        payload['tags'] = tags
    return payload


@_api_endpoint
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


# Past any real gallery, small enough for a SQL OFFSET
MAX_PAGE = 100000


@_api_endpoint
@cache_page(60)
def api_shared_builds(request):
    game_version = request.GET.get('game_version', 'dofus3')
    try:
        page = max(1, min(int(request.GET.get('page', 1)), MAX_PAGE))
    except (TypeError, ValueError):
        page = 1
    try:
        page_size = int(request.GET.get('page_size', DEFAULT_PAGE_SIZE))
    except (TypeError, ValueError):
        page_size = DEFAULT_PAGE_SIZE
    page_size = max(1, min(page_size, MAX_PAGE_SIZE))

    # No stored solution means no /s/ page
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


@_api_endpoint
@cache_page(60)
def api_shared_build_detail(request, encoded_id):
    try:
        char_id = decode_char_id(encoded_id)
    except Exception:
        return _absent('shared build')
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
        return _absent('shared build')

    alias_map = {}
    if char.owner_id:
        ua = UserAlias.objects.filter(user_id=char.owner_id).first()
        if ua and ua.alias:
            alias_map[char.owner_id] = ua.alias

    payload = _build_payload(char, alias_map)
    payload['comment_count'] = BuildComment.objects.filter(build=char, deleted=False).count()
    # proven is None for solutions stored before it was recorded
    from chardata.solution import get_solver_facts
    from fashionistapulp.lpproblem import TIME_LIMIT_SECONDS
    proven, seconds, _pool = get_solver_facts(char.minimal_solution)
    payload['solver'] = {
        'proven': proven,
        'seconds': None if seconds is None else round(seconds, 1),
        'time_limit_seconds': TIME_LIMIT_SECONDS,
    }
    return _json(payload)


@_api_endpoint
@cache_page(60)
def api_tier_list(request):
    game_version = request.GET.get('game_version', 'dofus3')
    char_class = request.GET.get('char_class')
    try:
        top_n = max(1, min(int(request.GET.get('top', 5)), 20))
    except (TypeError, ValueError):
        top_n = 5

    # No stored solution means no /s/ page
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

    # Load only the top few per class, a Char row carries pickled columns
    counts = {row['char_class'] or 'Unknown': row['n']
              for row in qs.values('char_class').annotate(n=Count('id', distinct=True))}
    ranked = (qs
              .annotate(score=(F('like_count') * 3 + F('favorite_count') * 5
                               + Least(F('view_count'), Value(50))))
              # owner__username or each creator costs a query
              .only('id', 'name', 'char_name', 'char_class', 'level',
                    'game_version', 'view_count', 'created_time',
                    'modified_time', 'created_version', 'solved_version',
                    'owner', 'owner__username')
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
