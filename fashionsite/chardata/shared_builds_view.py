# Copyright (C) 2020 The Dofus Fashionista
# 
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
# 
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

from django.db.models import Q, Count, Case, When, IntegerField, F
from django.core.cache import cache
from django.utils.translation import gettext as _
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import logging
import json
import pickle

from chardata.models import BuildComment, BuildTag, BuildVote, Char, UserAlias
from chardata.min_stats import get_min_stats_digested_by_key
from chardata.util import set_response, version_reverse
from chardata.encoded_char_id import encode_char_id
from chardata.image_store import get_image_url
from chardata.item_sources import (format_acquisition_counts,
                                   summarize_by_ankama_id)
from chardata.solution import get_solution
from chardata.solution_scores import calculate_public_build_score
from chardata.stat_icons import get_stat_icon_path
from chardata.smart_build import ASPECT_TO_NAME, ASPECT_TO_SHORT_NAME
from fashionistapulp.dofus_constants import TYPE_NAME_TO_SLOT, TYPE_NAME_TO_SLOT_NUMBER, SLOTS
from fashionistapulp.structure import (get_current_game_version, get_structure,
                                       set_current_game_version)
from fashionistapulp.translation import get_supported_language
from static_s3.templatetags.static_s3 import static


logger = logging.getLogger(__name__)

# Create reverse mapping from short names to keys
SHORT_NAME_TO_KEY = {v: k for k, v in ASPECT_TO_SHORT_NAME.items()}
SHARED_BUILDS_PAGE_SIZE = 24

# Char columns not needed to render a gallery card; minimal_solution stays
# because the meta computation reads it on cache misses.
_HEAVY_CHAR_FIELDS = ('minimum_stats', 'minimum_crits', 'stats_weight',
                      'options', 'inclusions', 'exclusions', 'aspects',
                      'empty_slots', 'stat_overrides')
SHARED_BUILD_META_CACHE_TIMEOUT = 6 * 60 * 60


def _get_valid_slots_for_type(type_name):
    slot_name = TYPE_NAME_TO_SLOT.get(type_name)
    if slot_name is None:
        return set()

    slot_count = TYPE_NAME_TO_SLOT_NUMBER.get(type_name, 1)
    if slot_count > 1:
        return set('%s%d' % (slot_name, idx) for idx in range(1, slot_count + 1))
    return {slot_name}


def _meta_cache_key(pk, modified_time, game_version='dofus3'):
    modified_marker = 'none'
    if modified_time is not None:
        modified_marker = str(int(modified_time.timestamp() * 1000000))
    return 'shared-build-meta-v3-%s-%s-%s-%s' % (
        pk, game_version or 'dofus3', modified_marker, get_supported_language())


def _get_shared_build_meta_cache_key(char):
    return _meta_cache_key(char.pk, char.modified_time, char.game_version)


def _get_preview_items(minimal_solution, structure, game_version):
    preview_items = []
    item_per_slot = getattr(minimal_solution, 'item_per_slot', {}) or {}
    language = get_supported_language()

    for slot in SLOTS:
        item_id = item_per_slot.get(slot)
        if item_id is None:
            continue
        item = structure.get_item_by_id(item_id)
        if item is None:
            continue
        preview_items.append({
            'slot': slot,
            'name': structure.get_item_name_in_language(item, language),
            'image_url': static(get_image_url(
                structure.get_type_name_by_id(item.type),
                item.name,
                game_version)),
        })
    return preview_items


def _get_compact_stats(solution, structure):
    total_stats = solution.get_stats_total()
    compact_stats = []

    def add_chip(key, value, label=None, icon_key=None):
        if not value:
            return
        icon_path = get_stat_icon_path(icon_key or key)
        compact_stats.append({
            'key': key,
            'label': label,
            'value': int(value) if float(value).is_integer() else round(value, 1),
            'icon_url': static(icon_path) if icon_path else None,
        })

    # Keep shared card stats intentionally compact: only main/core stats.
    for stat_key in ['ap', 'mp', 'range', 'summon', 'vit', 'wis', 'str', 'int', 'cha', 'agi', 'pow', 'ch']:
        stat = structure.get_stat_by_key(stat_key)
        if stat is None:
            continue
        add_chip(stat_key, total_stats.get(stat_key, 0), label=_(stat.name))

    return compact_stats


def _get_shared_build_meta(char):
    cache_key = _get_shared_build_meta_cache_key(char)
    cached_meta = cache.get(cache_key)
    if cached_meta is not None:
        return cached_meta


    meta = {
        'has_outdated_slots': False,
        'has_condition_issues': False,
        'has_missing_items': False,
        'is_invalid': False,
        'public_score': 0,
        'preview_items': [],
        'compact_stats': [],
        'acquisition_summary': '',
    }

    if not char.minimal_solution:
        cache.set(cache_key, meta, SHARED_BUILD_META_CACHE_TIMEOUT)
        return meta

    game_version = char.game_version or 'dofus3'
    previous_game_version = get_current_game_version()
    set_current_game_version(game_version)
    try:
        structure = get_structure(game_version)

        try:
            minimal_solution = pickle.loads(char.minimal_solution)
        except Exception:
            meta['has_outdated_slots'] = True
            meta['is_invalid'] = True
            cache.set(cache_key, meta, SHARED_BUILD_META_CACHE_TIMEOUT)
            return meta

        item_per_slot = getattr(minimal_solution, 'item_per_slot', {}) or {}
        meta['preview_items'] = _get_preview_items(
            minimal_solution, structure, game_version)
        acquisition_entries = []
        for slot, item_id in item_per_slot.items():
            if item_id is None:
                continue

            item = structure.get_item_by_id(item_id)
            if item is None:
                meta['has_missing_items'] = True
                meta['has_outdated_slots'] = True
                continue

            item_type_name = structure.get_type_name_by_id(item.type)
            if slot not in _get_valid_slots_for_type(item_type_name):
                meta['has_outdated_slots'] = True
            acquisition_entries.append((item.ankama_id, item_type_name))

        # What the build costs to assemble. Counts only: the rarest drop rate
        # would need a query per build, and the build's own page says it.
        counts = summarize_by_ankama_id(acquisition_entries, game_version)
        meta['acquisition_summary'] = format_acquisition_counts(
            counts['craftable'], counts['drop_only'], counts['unknown'])

        try:
            solution = get_solution(char)
        except Exception:
            solution = None
            meta['has_condition_issues'] = True

        if solution is None:
            meta['is_invalid'] = (
                meta['has_outdated_slots'] or meta['has_condition_issues'])
            cache.set(cache_key, meta, SHARED_BUILD_META_CACHE_TIMEOUT)
            return meta

        try:
            meta['public_score'] = calculate_public_build_score(
                solution, game_version) or 0
            meta['compact_stats'] = _get_compact_stats(solution, structure)
        except Exception:
            meta['public_score'] = 0
            meta['compact_stats'] = []

        item_condition_violations = False
        for item in solution.item_list:
            if item.item_added and solution.get_violations_on_item(item):
                item_condition_violations = True
                break

        project_min_violations = solution._get_min_violations(
            get_min_stats_digested_by_key(char))
        meta['has_condition_issues'] = (
            item_condition_violations or bool(project_min_violations))
        meta['is_invalid'] = (
            meta['has_outdated_slots'] or meta['has_condition_issues'])
        cache.set(cache_key, meta, SHARED_BUILD_META_CACHE_TIMEOUT)
        return meta
    finally:
        set_current_game_version(previous_game_version)

def translate_build_name(build_name):
    """Translate a build name that may contain multiple aspects separated by / or spaces"""
    if not build_name:
        return ''
    
    # First, try to match the entire string (e.g., "Glass Cannon" as a whole)
    lookup_key = SHORT_NAME_TO_KEY.get(build_name, build_name.lower())
    if lookup_key in ASPECT_TO_NAME:
        return str(ASPECT_TO_NAME[lookup_key])
    
    # Handle slash-separated parts first (e.g., "Agi Glass Cannon/Pushback")
    if '/' in build_name:
        parts = build_name.split('/')
        translated_parts = []
        for part in parts:
            part = part.strip()
            if part:
                # Recursively translate each part (which may contain spaces)
                translated_parts.append(translate_build_name(part))
        return '/'.join(translated_parts)
    
    # Handle space-separated parts (e.g., "Int Crit Glass Cannon")
    # But we need to be smart about multi-word build types like "Glass Cannon"
    if ' ' in build_name:
        # Try to find multi-word matches first (longer matches first)
        words = build_name.split(' ')
        translated_parts = []
        i = 0
        while i < len(words):
            # Try matching 2 words first (for "Glass Cannon", etc.)
            matched = False
            if i + 1 < len(words):
                two_word = f"{words[i]} {words[i+1]}"
                lookup_key = SHORT_NAME_TO_KEY.get(two_word, two_word.lower())
                if lookup_key in ASPECT_TO_NAME:
                    translated_parts.append(str(ASPECT_TO_NAME[lookup_key]))
                    i += 2
                    matched = True
            
            # If no 2-word match, try single word
            if not matched:
                lookup_key = SHORT_NAME_TO_KEY.get(words[i], words[i].lower())
                translated_parts.append(str(ASPECT_TO_NAME.get(lookup_key, words[i])))
                i += 1
        
        return ' '.join(translated_parts)
    
    # Single word that wasn't found
    return build_name

def shared_builds(request):
    """Display a page with all shared builds, with search and filter options."""

    # Get filter parameters from GET request
    char_class = request.GET.get('char_class', '')
    min_level = request.GET.get('min_level', '')
    max_level = request.GET.get('max_level', '')
    order_by = request.GET.get('order_by', 'created')  # views, modified, created, likes, favorites
    search_query = request.GET.get('search', '')
    user_search = request.GET.get('user_search', '')
    show_liked = request.GET.get('show_liked', '')  # Show only liked builds by current user
    show_favorited = request.GET.get('show_favorited', '')  # Show only favorited builds by current user
    hide_invalid = request.GET.get('hide_invalid', '')
    tag_filter = (request.GET.get('tag') or '').strip().lower()
    page_number = request.GET.get('page', 1)
    
    # Get selected build aspects from checkboxes
    selected_aspects = []
    for aspect in ['str', 'int', 'cha', 'agi', 'omni', 'vit', 'res', 'wis', 
                   'glasscannon', 'dam', 'crit', 'noncrit', 'heal', 'aprape', 'mprape',
                   'pvp', 'duel', 'trap', 'summon', 'pushback', 'pp', 'pods', 'balanced']:
        if request.GET.get(f'check_{aspect}'):
            selected_aspects.append(aspect)
    
    # Start with all shared, non-deleted builds for the current game version.
    # Only annotate vote counts when needed for ordering, it's an expensive JOIN.
    game_version = getattr(request, 'game_version', 'dofus3')
    needs_vote_annotation = order_by in ('likes', 'favorites') or (
        request.user.is_authenticated and (show_liked or show_favorited)
    )

    base_filter = dict(link_shared=True, deleted=False, game_version=game_version)
    if needs_vote_annotation:
        builds = Char.objects.filter(**base_filter).select_related('owner').annotate(
            like_count=Count(Case(When(buildvote__vote_type='like', then=1), output_field=IntegerField())),
            favorite_count=Count(Case(When(buildvote__vote_type='favorite', then=1), output_field=IntegerField()))
        )
    else:
        builds = Char.objects.filter(**base_filter).select_related('owner')
    
    # Apply filters
    if char_class:
        builds = builds.filter(char_class=char_class)
    
    # Filter by selected build aspects (if any)
    if selected_aspects:
        # Special handling for Balanced: if Balanced is selected, we need to filter differently
        # because balanced builds don't have focus aspects stored in char_build
        if 'balanced' in selected_aspects:
            # Get all the focus aspects that should NOT be in the build
            focus_aspects = ['vit', 'glasscannon', 'dam', 'heal', 'aprape', 'mprape', 
                           'crit', 'res', 'wis', 'pp', 'pods', 'trap', 'summon', 
                           'pushback', 'noncrit']
            
            # Remove balanced from the list and filter for other aspects normally
            aspects_to_filter = [aspect for aspect in selected_aspects if aspect != 'balanced']
            
            # Match builds that contain the selected non-balanced aspects
            for aspect in aspects_to_filter:
                aspect_short = ASPECT_TO_SHORT_NAME.get(aspect, aspect)
                builds = builds.filter(char_build__icontains=aspect_short)
            
            # Exclude builds that contain any focus aspect (these are not balanced)
            for focus_aspect in focus_aspects:
                focus_short = ASPECT_TO_SHORT_NAME.get(focus_aspect, focus_aspect)
                builds = builds.exclude(char_build__icontains=focus_short)
        else:
            # Special handling for Omni: if Omni is selected, only search for Omni builds
            # even if individual elements are also checked (for UI purposes)
            if 'omni' in selected_aspects:
                # Filter only for Omni, ignore individual element selections
                aspects_to_filter = [aspect for aspect in selected_aspects 
                                   if aspect not in ['str', 'int', 'cha', 'agi']]
            else:
                aspects_to_filter = selected_aspects
            
            # Match builds that contain ALL selected aspects
            for aspect in aspects_to_filter:
                # Map aspect keys to their short names for matching
                aspect_short = ASPECT_TO_SHORT_NAME.get(aspect, aspect)
                builds = builds.filter(char_build__icontains=aspect_short)
    
    if min_level:
        try:
            builds = builds.filter(level__gte=int(min_level))
        except ValueError:
            pass
    
    if max_level:
        try:
            builds = builds.filter(level__lte=int(max_level))
        except ValueError:
            pass
    
    if search_query:
        builds = builds.filter(
            Q(name__icontains=search_query) |
            Q(char_name__icontains=search_query)
        )

    if tag_filter:
        builds = builds.filter(tags__name=tag_filter)
    
    # Filter by user
    if user_search:
        # Search by username or alias
        builds = builds.filter(
            Q(owner__username__icontains=user_search) |
            Q(owner__useralias__alias__icontains=user_search)
        )
    
    # Filter by liked/favorited (only for logged-in users)
    if request.user.is_authenticated:
        if show_liked:
            builds = builds.filter(buildvote__user=request.user, buildvote__vote_type='like')
        if show_favorited:
            builds = builds.filter(buildvote__user=request.user, buildvote__vote_type='favorite')
    
    # Order results
    if order_by == 'views':
        builds = builds.order_by('-view_count', '-modified_time')
    elif order_by == 'modified':
        builds = builds.order_by(
            F('modified_time').desc(nulls_last=True),
            F('created_time').desc(nulls_last=True),
            '-id'
        )
    elif order_by == 'created':
        builds = builds.order_by(
            F('created_time').desc(nulls_last=True),
            F('modified_time').desc(nulls_last=True),
            '-id'
        )
    elif order_by == 'likes' and needs_vote_annotation:
        builds = builds.order_by('-like_count', '-modified_time')
    elif order_by == 'favorites' and needs_vote_annotation:
        builds = builds.order_by('-favorite_count', '-modified_time')
    else:
        builds = builds.order_by('-view_count', '-modified_time')

    # Sort and paginate on ids only: ordering full rows drags every blob
    # column through the MySQL sort buffer, which made this page ~10x slower
    # than the rest of the site. Full rows are fetched for the shown page only.
    def _fetch_page_chars(page_ids):
        chars_by_id = {
            char.id: char
            for char in Char.objects.filter(id__in=page_ids)
            .defer(*_HEAVY_CHAR_FIELDS).select_related('owner')}
        return [chars_by_id[i] for i in page_ids if i in chars_by_id]

    builds_data = []
    if hide_invalid:
        # Validity comes from the per-build meta cache; check it with a
        # 2-column scan. Full rows are fetched only for cache misses and for
        # the page actually shown.
        id_rows = list(builds.values_list('id', 'modified_time', 'game_version'))
        metas = {}
        miss_ids = []
        for row_id, row_modified, row_game_version in id_rows:
            cached = cache.get(_meta_cache_key(
                row_id, row_modified, row_game_version))
            if cached is not None:
                metas[row_id] = cached
            else:
                miss_ids.append(row_id)
        if miss_ids:
            for char in Char.objects.filter(id__in=miss_ids).defer(*_HEAVY_CHAR_FIELDS):
                metas[char.id] = _get_shared_build_meta(char)

        valid_ids = [row_id for row_id, _row_modified, _row_game_version in id_rows
                     if row_id in metas and not metas[row_id]['is_invalid']]

        paginator = Paginator(valid_ids, SHARED_BUILDS_PAGE_SIZE)
        try:
            builds_page = paginator.page(page_number)
        except PageNotAnInteger:
            builds_page = paginator.page(1)
        except EmptyPage:
            builds_page = paginator.page(paginator.num_pages)

        page_ids = list(builds_page.object_list)
        page_chars = _fetch_page_chars(page_ids)
        meta_by_id = {i: metas[i] for i in page_ids if i in metas}
    else:
        paginator = Paginator(builds.values_list('id', flat=True),
                              SHARED_BUILDS_PAGE_SIZE)
        try:
            builds_page = paginator.page(page_number)
        except PageNotAnInteger:
            builds_page = paginator.page(1)
        except EmptyPage:
            builds_page = paginator.page(paginator.num_pages)

        page_chars = _fetch_page_chars(list(builds_page.object_list))
        meta_by_id = {char.id: _get_shared_build_meta(char) for char in page_chars}

    # Bulk-fetch vote counts for just the page items (1-2 queries for N items).
    # Always needed now: the page rows are re-fetched by id, so ordering
    # annotations do not survive to them.
    if page_chars:
        page_char_ids = [char.id for char in page_chars]
        vote_rows = BuildVote.objects.filter(
            build_id__in=page_char_ids
        ).values('build_id', 'vote_type').annotate(cnt=Count('build_id'))
        like_counts = {}
        favorite_counts = {}
        for row in vote_rows:
            if row['vote_type'] == 'like':
                like_counts[row['build_id']] = row['cnt']
            elif row['vote_type'] == 'favorite':
                favorite_counts[row['build_id']] = row['cnt']
        for char in page_chars:
            char.like_count = like_counts.get(char.id, 0)
            char.favorite_count = favorite_counts.get(char.id, 0)

    owner_ids = [char.owner_id for char in page_chars if char.owner_id]
    alias_by_user_id = {
        alias.user_id: alias.alias
        for alias in UserAlias.objects.filter(user_id__in=owner_ids)
        if alias.alias
    }

    # Bulk-fetch tags for the page items so each build row can show its chips.
    tags_by_char = {}
    comment_counts = {}
    if page_chars:
        page_char_ids_for_chips = [c.id for c in page_chars]
        for t in BuildTag.objects.filter(char_id__in=page_char_ids_for_chips).order_by('created_time'):
            tags_by_char.setdefault(t.char_id, []).append(
                {'name': t.display_name, 'slug': t.name})
        for row in (BuildComment.objects
                    .filter(build_id__in=page_char_ids_for_chips, deleted=False)
                    .values('build_id')
                    .annotate(cnt=Count('id'))):
            comment_counts[row['build_id']] = row['cnt']

    for char in page_chars:
        encoded_id = encode_char_id(int(char.id))
        char_name = char.char_name or 'shared'
        link = request.build_absolute_uri(version_reverse(request, 'solution_linked',
                                                           char_name, encoded_id))

        creator_name = None
        if char.owner:
            creator_name = alias_by_user_id.get(char.owner_id, char.owner.username)

        focus_aspects = ['Vit', 'Glass Cannon', 'Dam', 'Heals', 'AP Red', 'MP Red',
                        'Crit', 'Res', 'Leecher', 'PP', 'Pods', 'Traps', 'Summons',
                        'Pushback', 'Non-Crit']
        has_focus = any(focus in char.char_build for focus in focus_aspects if char.char_build)

        if char.char_build and not has_focus:
            build_name_translated = f"{translate_build_name(char.char_build)} {ASPECT_TO_NAME['balanced']}"
        elif not char.char_build:
            build_name_translated = str(ASPECT_TO_NAME['balanced'])
        else:
            build_name_translated = translate_build_name(char.char_build)

        build_meta = meta_by_id[char.id]
        builds_data.append({
            'char': char,
            'link': link,
            'encoded_id': encoded_id,
            'public_score': build_meta.get('public_score', 0),
            'preview_items': build_meta['preview_items'],
            'compact_stats': build_meta['compact_stats'],
            'acquisition_summary': build_meta.get('acquisition_summary', ''),
            'view_count': char.view_count,
            'build_name_translated': build_name_translated,
            'creator_name': creator_name,
            'like_count': char.like_count,
            'favorite_count': char.favorite_count,
            'user_liked': False,
            'user_favorited': False,
            'has_outdated_slots': build_meta['has_outdated_slots'],
            'has_condition_issues': build_meta['has_condition_issues'],
            'is_invalid': build_meta['is_invalid'],
            'tags': tags_by_char.get(char.id, []),
            'comment_count': comment_counts.get(char.id, 0),
        })

    # Get user's votes if logged in.
    if request.user.is_authenticated and builds_data:
        build_ids = [build['char'].id for build in builds_data]
        user_likes = set(BuildVote.objects.filter(
            user=request.user, vote_type='like', build_id__in=build_ids
        ).values_list('build_id', flat=True))
        user_favorites = set(BuildVote.objects.filter(
            user=request.user, vote_type='favorite', build_id__in=build_ids
        ).values_list('build_id', flat=True))

        for build in builds_data:
            build['user_liked'] = build['char'].id in user_likes
            build['user_favorited'] = build['char'].id in user_favorites
    
    # Get all unique classes for filter dropdown (same game version)
    all_classes = Char.objects.filter(link_shared=True, deleted=False, game_version=game_version).values_list('char_class', flat=True).distinct().order_by('char_class')
    
    # Prepare aspect names and layout for checkboxes (same as projdetails.html)
    aspect_to_name = {k: str(v) for k, v in ASPECT_TO_NAME.items()}
    aspect_layout = [['str', 'int', 'cha', 'agi', 'omni'],
                     ['pvp', 'duel'],
                     ['balanced', 'vit', 'glasscannon', 'dam', 'heal', 'aprape', 'mprape', 'crit'],
                     ['res', 'wis', 'pp', 'pods', 'trap', 'summon', 'pushback', 'noncrit']]
    
    params = {
        'builds': builds_data,
        'page_obj': builds_page,
        'all_classes': all_classes,
        'aspect_to_name': json.dumps(aspect_to_name),
        'aspect_layout': json.dumps(aspect_layout),
        'selected_aspects': json.dumps(selected_aspects),
        'filters': {
            'char_class': char_class,
            'min_level': min_level,
            'max_level': max_level,
            'order_by': order_by,
            'search': search_query,
            'user_search': user_search,
            'show_liked': show_liked,
            'show_favorited': show_favorited,
            'hide_invalid': hide_invalid,
            'tag': tag_filter,
        }
    }
    
    response = set_response(request, 
                            'chardata/shared_builds.html',
                            params)
    return response


@login_required
@require_POST
def vote_build(request, build_id):
    """API endpoint to add/remove a vote (like or favorite) on a build"""
    try:
        build = Char.objects.get(id=build_id, link_shared=True, deleted=False)
        vote_type = request.POST.get('vote_type')  # 'like' or 'favorite'
        action = request.POST.get('action')  # 'add' or 'remove'
        
        if vote_type not in ['like', 'favorite']:
            return JsonResponse({'error': _('Invalid vote type')}, status=400)
        
        if action == 'add':
            BuildVote.objects.get_or_create(user=request.user, build=build, vote_type=vote_type)
            message = 'Added'
        elif action == 'remove':
            BuildVote.objects.filter(user=request.user, build=build, vote_type=vote_type).delete()
            message = 'Removed'
        else:
            return JsonResponse({'error': _('Invalid action')}, status=400)
        
        # Get updated counts
        like_count = BuildVote.objects.filter(build=build, vote_type='like').count()
        favorite_count = BuildVote.objects.filter(build=build, vote_type='favorite').count()
        
        return JsonResponse({
            'success': True,
            'message': message,
            'like_count': like_count,
            'favorite_count': favorite_count
        })
    except Char.DoesNotExist:
        return JsonResponse({'error': _('Build not found')}, status=404)
    except Exception:
        logger.exception('Unexpected error while voting on build', extra={'build_id': build_id})
        return JsonResponse({'error': _('Internal server error')}, status=500)
