# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Community Tier List — top shared builds aggregated by class.

100% derived data: uses Char + BuildVote + BuildView that already exist.
No model, no migration, just a read-only page that surfaces what the
community is already voting up. Cached for 30 min since it crunches across
every shared build.
"""

from django.core.cache import cache
from django.db.models import Count, Case, When, IntegerField, F
from django.utils.translation import gettext as _

from chardata.encoded_char_id import encode_char_id
from chardata.models import Char, UserAlias
from chardata.shared_builds_view import translate_build_name, _get_shared_build_meta
from chardata.util import set_response, version_reverse


TIERLIST_TOP_PER_CLASS = 5
TIERLIST_CACHE_SECONDS = 30 * 60


def _cache_key(game_version, char_class_filter, level_bucket):
    return 'tierlist:%s:%s:%s' % (game_version, char_class_filter or '_', level_bucket or '_')


def _level_to_bucket(level):
    if level is None:
        return None
    if level <= 50:
        return '1-50'
    if level <= 100:
        return '51-100'
    if level <= 150:
        return '101-150'
    if level <= 199:
        return '151-199'
    return '200+'


LEVEL_BUCKETS = ['1-50', '51-100', '101-150', '151-199', '200+']


def _aliases_for(owner_ids):
    return {
        a.user_id: a.alias
        for a in UserAlias.objects.filter(user_id__in=owner_ids)
        if a.alias
    }


def _scored_builds(game_version, char_class_filter=None, level_bucket=None):
    qs = (Char.objects
          .filter(link_shared=True, deleted=False, game_version=game_version)
          .select_related('owner')
          .annotate(
              like_count=Count(Case(When(buildvote__vote_type='like', then=1),
                                    output_field=IntegerField())),
              favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1),
                                        output_field=IntegerField())),
          ))
    if char_class_filter:
        qs = qs.filter(char_class=char_class_filter)
    if level_bucket == '1-50':
        qs = qs.filter(level__lte=50)
    elif level_bucket == '51-100':
        qs = qs.filter(level__gte=51, level__lte=100)
    elif level_bucket == '101-150':
        qs = qs.filter(level__gte=101, level__lte=150)
    elif level_bucket == '151-199':
        qs = qs.filter(level__gte=151, level__lte=199)
    elif level_bucket == '200+':
        qs = qs.filter(level__gte=200)
    return qs


def _serialize(request, build, owner_alias_by_id):
    encoded = encode_char_id(int(build.id))
    char_name = build.char_name or 'shared'
    link = request.build_absolute_uri(version_reverse(request, 'solution_linked',
                                                       char_name, encoded))
    creator = (owner_alias_by_id.get(build.owner_id) if build.owner_id else None) or \
              (build.owner.username if build.owner else _('Anonymous'))
    meta = _get_shared_build_meta(build)
    score = (build.like_count or 0) * 3 + (build.favorite_count or 0) * 5 + min(50, build.view_count)
    return {
        'char': build,
        'link': link,
        'creator': creator,
        'like_count': build.like_count or 0,
        'favorite_count': build.favorite_count or 0,
        'view_count': build.view_count or 0,
        'score': score,
        'preview_items': meta.get('preview_items', []),
        'is_invalid': meta.get('is_invalid', False),
        'build_name_translated': translate_build_name(build.char_build or ''),
    }


def tierlist(request):
    game_version = getattr(request, 'game_version', 'dofus3')
    char_class_filter = request.GET.get('char_class') or None
    level_bucket = request.GET.get('level_bucket') or None
    if level_bucket and level_bucket not in LEVEL_BUCKETS:
        level_bucket = None

    cache_key = _cache_key(game_version, char_class_filter, level_bucket)
    cached = cache.get(cache_key)
    if cached is None:
        all_builds = list(_scored_builds(game_version, char_class_filter, level_bucket))
        owner_ids = [b.owner_id for b in all_builds if b.owner_id]
        aliases = _aliases_for(owner_ids)

        by_class = {}
        for b in all_builds:
            cls = b.char_class or _('Unknown')
            by_class.setdefault(cls, []).append(_serialize(request, b, aliases))

        # Keep top N per class and hide invalid ones unless that's all we have
        sections = []
        for cls, builds in by_class.items():
            valid = [x for x in builds if not x['is_invalid']]
            pool = valid if valid else builds
            pool.sort(key=lambda x: x['score'], reverse=True)
            sections.append({
                'char_class': cls,
                'count': len(builds),
                'top_builds': pool[:TIERLIST_TOP_PER_CLASS],
            })
        sections.sort(key=lambda s: s['count'], reverse=True)
        cached = sections
        cache.set(cache_key, cached, TIERLIST_CACHE_SECONDS)

    all_classes = list(Char.objects
                       .filter(link_shared=True, deleted=False, game_version=game_version)
                       .values_list('char_class', flat=True).distinct().order_by('char_class'))

    return set_response(request, 'chardata/tierlist.html', {
        'sections': cached,
        'all_classes': all_classes,
        'level_buckets': LEVEL_BUCKETS,
        'selected_class': char_class_filter or '',
        'selected_level': level_bucket or '',
    })
