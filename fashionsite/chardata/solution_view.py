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

from django.http import Http404, HttpResponseBadRequest, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.db.models import Count, F
from django.core.cache import cache
import ipaddress
import json
import logging
import pickle

logger = logging.getLogger(__name__)

from chardata.character_look import (CLASS_TO_BREED, DEFAULT_COLORS,
                                     MOUNT_SLOT, SLOT_TO_NODE, UNDRAWN_SLOTS,
                                     breed_colors, get_character_look,
                                     parse_colors, parse_hidden, preview_box)
from chardata.character_assets import asset_formats, asset_token, preload_links
from chardata.encoded_char_id import encode_char_id
from chardata.fashion_action import fashion, get_options
from chardata.lock_forbid import (set_excluded,
                                  set_item_included,
                                  get_all_inclusions_en_names,
                                  get_all_exclusions_en_names,
                                  get_empty_slots, set_empty_slot)
from chardata.comment_view import get_comments_for_build
from chardata.model_wrappers import WrappedChar
from chardata.models import Char, BuildVote, BuildView, SolutionGeneration
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
import chardata.smart_build
from chardata.solution import get_solution, set_minimal_solution
from chardata.solution_history import get_generation_preview_items, get_generation_solution
from chardata.solution_scores import calculate_project_build_score
from chardata.spell_buffs import compute_full_buff_stats
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from datetime import timedelta
from chardata.solution_result import SolutionResult
from chardata.util import set_response, get_char_or_raise, get_alias, get_char_encoded_or_raise, \
    HttpResponseText, HttpResponseJson, get_base_stats_by_attr, version_reverse
from fashionistapulp.dofus_constants import SLOTS, STAT_ORDER, TYPE_NAME_TO_SLOT

from static_s3.templatetags.static_s3 import static
from fashionistapulp.structure import get_structure
from chardata.stat_icons import get_stat_icon_path
from fashionistapulp.modelresult import ModelResultMinimal
from chardata.themes import get_ajax_loader_URL, get_external_image_URL
from fashionistapulp.translation import get_supported_language


SHARED_SOLUTION_CACHE_TIMEOUT = 6 * 60 * 60

_SHARE_SLOT_ORDER = ['Weapon', 'Shield', 'Hat', 'Cloak', 'Amulet', 'Ring',
                     'Belt', 'Boots', 'Dofus', 'Pet']


# Hint a slot as upgradable only when the equipped item is clearly off the pace
# for *this build*: there must be at least this many strictly-better-scoring
# options for the slot (so a top pick is never flagged) AND the equipped item
# must score below this fraction of the slot's best score (so "good enough"
# items stay silent). Score = the item's stats dotted with the build's stat
# weights, the same ranking the "switch item" list uses, so a low-level item
# that scores well for the build is correctly left alone.
_UPGRADE_MIN_BETTER = 5
_UPGRADE_SCORE_RATIO = 0.8
_UPGRADE_MAX_HINTS = 4
# Slots whose item is well-modelled by the build's stat weights. Weapons are
# valued by damage/AP (own ranking), and Dofus/Pet are picked for unique
# effects, quests or ownership, a flat stat score is a poor "upgrade" signal
# for those, so they're left out to keep hints trustworthy.
_CHECKED_SLOTS = {'Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots', 'Shield'}


def _resolve_structure_item(structure, name):
    if not name or name == 'NoItem':
        return None
    item = structure.get_item_by_name(name)
    if item is None and name in structure.or_items:
        item = structure.get_or_item_by_name(name)[0]
    return item


def _weighted_rate(structure, item, weights):
    """Build-specific score: the item's stats weighted by the build's stat
    weights (mirrors item_exchange._rate, which orders the switch-item list)."""
    if item.name in structure.or_items:
        item = structure.get_or_item_by_name(item.name)[0]
    rating = 0
    for stat_id, value in item.stats:
        stat = structure.get_stat_by_id(stat_id)
        if stat is not None and stat.key in weights:
            rating += value * weights[stat.key]
    return rating


# Lazy: this dict is built at import, the language is only known per request.
_PIECE_LABELS = {'hat': gettext_lazy('Hat'), 'cloak': gettext_lazy('Cloak'),
                 'shield': gettext_lazy('Shield'), 'weapon': gettext_lazy('Weapon'),
                 'mount': gettext_lazy('Mount')}


def _default_colors(char):
    """What the game itself gives that class and gender."""
    breed = CLASS_TO_BREED.get(char.char_class)
    if breed is None:
        return list(DEFAULT_COLORS)
    return breed_colors(breed, getattr(char, 'gender', 0) or 0)


def _preview_pieces(char, look=None):
    hidden = parse_hidden(char.hidden_parts)
    gear = (look or {}).get('gear') or {}
    # Only two thirds of cloaks and under a third of weapons have art, so a box
    # for a slot the preview cannot draw does nothing when ticked.
    slots = [slot for slot in sorted(SLOT_TO_NODE)
             if slot not in UNDRAWN_SLOTS
             and (SLOT_TO_NODE[slot] in gear or slot in hidden)]
    # Hiding the mount takes it out of the look, so the box has to stay while
    # it is off or there is no way back.
    if (look and look.get('mount')) or MOUNT_SLOT in hidden:
        slots.append(MOUNT_SLOT)
    return [{'slot': slot, 'label': _PIECE_LABELS[slot], 'hidden': slot in hidden}
            for slot in slots]


def _preview_box_for(user):
    """The reader's own size setting, not the build owner's."""
    percent = 100
    if user is not None and not user.is_anonymous:
        percent = getattr(getattr(user, 'useralias', None), 'preview_size', 100)
    return preview_box(percent)


def _build_check(char, solution):
    """Heuristic build review. For each equipped slot, score the equipped item
    against every item that fits the slot using the build's own stat weights and
    hint only the slots where the equipped item is clearly suboptimal, many
    stronger options *and* well below the slot's best score. Stays silent for
    items that are already top picks (including low-level items that score well)
    and for pieces kept by an active set bonus. Returns equipped count + the
    suggestion list."""
    structure = get_structure()
    try:
        weights = pickle.loads(char.stats_weight) if char.stats_weight else None
    except Exception:
        weights = None

    # Resolve equipped items to structure items and tally set membership.
    equipped_entries = []  # (slot, result_item, structure_item)
    set_counts = {}
    for slot, items in solution.items.items():
        for item in items:
            if not getattr(item, 'item_added', False):
                continue
            structure_item = _resolve_structure_item(structure, getattr(item, 'name', None))
            if structure_item is None:
                continue
            equipped_entries.append((slot, item, structure_item))
            if structure_item.set is not None:
                set_counts[structure_item.set] = set_counts.get(structure_item.set, 0) + 1

    equipped_count = len(equipped_entries)
    char_level = char.level or 0

    suggestions = []
    if weights and char_level:
        rates_by_type = {}  # type_name -> sorted candidate scores (desc)
        for slot, result_item, structure_item in equipped_entries:
            if slot not in _CHECKED_SLOTS:
                continue
            # A piece kept for an active set bonus often scores poorly on its own.
            if structure_item.set is not None and set_counts.get(structure_item.set, 0) >= 2:
                continue

            type_name = structure.get_type_name_by_id(structure_item.type)
            # Skip slots whose stored item no longer matches the slot's type,
            # old builds carry item ids that current versions reuse for a
            # different item, which would otherwise be ranked against the wrong
            # list. (Such builds are surfaced as outdated elsewhere.)
            if TYPE_NAME_TO_SLOT.get(type_name, '').lower() != slot.lower():
                continue

            candidate_rates = rates_by_type.get(type_name)
            if candidate_rates is None:
                try:
                    candidates = structure.get_unique_items_by_type_and_level(type_name, char_level)
                except Exception:
                    candidates = []
                candidate_rates = sorted(
                    (_weighted_rate(structure, candidate, weights)
                     for candidate in candidates if not candidate.removed),
                    reverse=True)
                rates_by_type[type_name] = candidate_rates
            if not candidate_rates:
                continue

            best_rate = candidate_rates[0]
            if best_rate <= 0:
                # The build doesn't value this slot's stats, nothing to upgrade toward.
                continue

            equipped_rate = _weighted_rate(structure, structure_item, weights)
            better_count = sum(1 for rate in candidate_rates if rate > equipped_rate)
            if better_count >= _UPGRADE_MIN_BETTER and equipped_rate < best_rate * _UPGRADE_SCORE_RATIO:
                suggestions.append({
                    'slot': slot,
                    'name': structure.get_item_name_in_language(structure_item, get_supported_language()),
                    'better_count': better_count,
                    'gap': best_rate - equipped_rate,
                })

        # Biggest score gaps first, capped so the hint stays compact.
        suggestions.sort(key=lambda entry: entry['gap'], reverse=True)
        suggestions = suggestions[:_UPGRADE_MAX_HINTS]

    return {
        'equipped_count': equipped_count,
        'suggestions': suggestions,
        'has_hints': bool(suggestions),
    }


def _build_share_text(request, char, solution):
    """Plain-text build summary for pasting into Discord / forums."""
    title = char.char_name or char.name or char.char_class or 'Build'
    lines = ['%s - %s lvl %d' % (title, char.char_class, char.level), '']
    for slot in _SHARE_SLOT_ORDER:
        for item in solution.items.get(slot, []):
            name = getattr(item, 'name', None)
            if getattr(item, 'item_added', False) and name and name != 'NoItem':
                lines.append('%s: %s' % (slot, name))
    try:
        stats = solution.get_stats_total()
        chips = []
        for key, label in [('ap', 'AP'), ('mp', 'MP'), ('range', 'Range'),
                           ('vit', 'Vitality'), ('pow', 'Power')]:
            value = stats.get(key, 0)
            if value:
                chips.append('%s %d' % (label, int(value)))
        if chips:
            lines += ['', ' / '.join(chips)]
    except Exception:
        # Stats are a nice-to-have in the share text; don't fail the share if they
        # can't be computed, but surface it so the underlying bug gets noticed.
        logger.exception('Failed to build stats chips for share text (char %s)', char.id)
    lines.append('')
    if char.link_shared:
        lines.append(generate_link(request, char))
    else:
        lines.append('https://dofusfashionista.gg')
    return '\n'.join(lines)

# Classes for which we ship 6 wizard avatars under chardata/designs/wizard/<class>/.
_CLASS_AVATAR_DIRS = {'Cra', 'Ecaflip', 'Eliotrope', 'Eniripsa', 'Enutrof', 'Feca',
                      'Foggernaut', 'Huppermage', 'Iop', 'Masqueraider', 'Osamodas',
                      'Ouginak', 'Pandawa', 'Rogue', 'Sacrier', 'Sadida', 'Sram', 'Xelor'}
_CLASS_AVATAR_COUNT = 6


def get_class_avatar(char):
    """Stable per-char avatar URL, falling back to a placeholder for classes
    without art (Forgelance) or unknown values."""
    cls = char.char_class or ''
    if cls not in _CLASS_AVATAR_DIRS:
        return static('chardata/QuestionMark-lighttheme.png')
    idx = 1 + (int(char.id or 0) % _CLASS_AVATAR_COUNT)
    return static('chardata/designs/wizard/%s/myWizard%s%d.png' % (cls, cls, idx))


def _get_stat_filter_options():
    structure = get_structure()
    used_stat_keys = structure.get_used_stat_keys()
    stats = sorted(structure.get_stats_list(), key=lambda stat: STAT_ORDER.get(stat.key, 9999))
    result = []
    for stat in stats:
        if stat.key == 'hp':
            continue
        # PVP resists only exist in some versions (e.g. retro); show them
        # only where the current version's items actually use them.
        if stat.key.startswith('pvp') and stat.key not in used_stat_keys:
            continue
        icon_path = get_stat_icon_path(stat.key)
        result.append({
            'key': stat.key,
            'id': stat.id,
            'label': _(stat.name),
            'icon_url': static(icon_path) if icon_path else None,
        })
    return result


def _get_shared_solution_cache_key(char):
    modified_marker = 'none'
    if char.modified_time is not None:
        modified_marker = str(int(char.modified_time.timestamp() * 1000000))
    return 'shared-solution-%s-%s-%s' % (char.pk,
                                         modified_marker,
                                         get_supported_language())


def _get_shared_solution_params(char):
    cache_key = _get_shared_solution_cache_key(char)
    cached_params = cache.get(cache_key)
    if cached_params is not None:
        return cached_params

    inclusions = get_all_inclusions_en_names(char)
    exclusions = get_all_exclusions_en_names(char)
    solution = get_solution(char)
    solution_result = SolutionResult(solution,
                                     inclusions,
                                     exclusions)
    cached_params = solution_result.get_params()
    cache.set(cache_key, cached_params, SHARED_SOLUTION_CACHE_TIMEOUT)
    return cached_params


def _get_live_vote_data(request, char):
    vote_data = {
        'like_count': 0,
        'favorite_count': 0,
        'user_liked': False,
        'user_favorited': False,
    }

    if not char.link_shared:
        return vote_data

    try:
        vote_counts = BuildVote.objects.filter(build=char).values('vote_type').annotate(count=Count('id'))
        for vote_count in vote_counts:
            if vote_count['vote_type'] == 'like':
                vote_data['like_count'] = vote_count['count']
            elif vote_count['vote_type'] == 'favorite':
                vote_data['favorite_count'] = vote_count['count']

        if request.user.is_authenticated:
            user_votes = set(BuildVote.objects.filter(user=request.user,
                                                      build=char).values_list('vote_type', flat=True))
            vote_data['user_liked'] = 'like' in user_votes
            vote_data['user_favorited'] = 'favorite' in user_votes
    except Exception as e:
        logger.warning('Error fetching vote data: %s', e)

    return vote_data


def solution(request, char_id, empty=False):
    char = get_char_or_raise(request, char_id)
    solution = get_solution(char)
    if solution is None:
        if not empty:
            return fashion(request, char_id)
        else:
            input_ = {}
            input_['options'] = get_options(request, char_id)
            input_['base_stats_by_attr'] = get_base_stats_by_attr(request, char_id)
            input_['char_level'] = char.level
            set_minimal_solution(char, ModelResultMinimal.generate_empty_solution(input_))
    return _solution(request, char_id, False, char=char)


def _generation_compare_id(generation):
    return 'g%d' % generation.id


def _score_delta_text(delta):
    return '+%d' % delta if delta > 0 else str(delta)


def _build_generation_history(request, char, current_generation=None, current_score=None):
    generations = (SolutionGeneration.objects
                   .filter(char=char, game_version=char.game_version)
                   .order_by('-created_time', '-id')[:10])
    if current_score is None:
        try:
            current_score = calculate_project_build_score(char, get_solution(char))
        except Exception:
            current_score = None
    entries = []
    for generation in generations:
        solution = None
        build_score = None
        score_delta = None
        try:
            solution = get_generation_solution(char, generation)
            build_score = calculate_project_build_score(char, solution)
            if build_score is not None and current_score is not None:
                score_delta = build_score - current_score
        except Exception:
            build_score = None
            score_delta = None
        compare_id = _generation_compare_id(generation)
        score_delta_class = 'same'
        if score_delta is not None:
            if score_delta > 0:
                score_delta_class = 'positive'
            elif score_delta < 0:
                score_delta_class = 'negative'
        entries.append({
            'id': generation.id,
            'created_time': generation.created_time,
            'score': build_score,
            'has_score': build_score is not None,
            'score_delta': score_delta,
            'score_delta_text': _score_delta_text(score_delta) if score_delta is not None else '',
            'score_delta_class': score_delta_class,
            'has_score_delta': score_delta is not None,
            'preview_items': get_generation_preview_items(generation),
            'view_url': version_reverse(request, 'solution_generation', char.id, generation.id),
            'restore_url': version_reverse(request, 'restore_generation', char.id, generation.id),
            'compare_id': compare_id,
            'compare_with_current_url': version_reverse(
                request, 'compare_sets', '%s/%s' % (char.id, compare_id)),
            'is_current_snapshot': (
                current_generation is not None and current_generation.id == generation.id),
            'is_broken': solution is None,
        })
    return entries


def solution_generation(request, char_id, generation_id):
    char = get_char_or_raise(request, char_id)
    generation = get_object_or_404(SolutionGeneration,
                                   pk=generation_id,
                                   char=char,
                                   game_version=char.game_version)
    if get_generation_solution(char, generation) is None:
        raise Http404
    return _solution(request, char_id, False, char=char, generation=generation)


def restore_generation(request, char_id, generation_id):
    if request.method != 'POST':
        raise Http404
    char = get_char_or_raise(request, char_id)
    generation = get_object_or_404(SolutionGeneration,
                                   pk=generation_id,
                                   char=char,
                                   game_version=char.game_version)
    if get_generation_solution(char, generation) is None:
        raise Http404
    char.minimal_solution = generation.minimal_solution
    char.save()
    from chardata.util import remove_cache_for_char
    remove_cache_for_char(char.id)
    return HttpResponseRedirect(version_reverse(request, 'solution_2', char.id))


def _solution(request, char_id, is_guest, encoded_char_id=None, char=None, generation=None):
    if char is None:
        char = get_object_or_404(Char, pk=char_id)

    snapshot_solution = None
    is_generation_snapshot = generation is not None
    if generation is not None:
        snapshot_solution = get_generation_solution(char, generation)
        if snapshot_solution is None:
            raise Http404

    if is_guest and char.link_shared and generation is None:
        solution_params = _get_shared_solution_params(char)
    else:
        inclusions = get_all_inclusions_en_names(char)
        exclusions = get_all_exclusions_en_names(char)
        empty_slots = get_empty_slots(char)
        solution = snapshot_solution if snapshot_solution is not None else get_solution(char)
        solution_result = SolutionResult(solution,
                                         inclusions,
                                         exclusions,
                                         empty_slots)
        solution_params = solution_result.get_params()

    vote_data = _get_live_vote_data(request, char)
    class_avatar = get_class_avatar(char)
    character_look = get_character_look(
        char, snapshot_solution if snapshot_solution is not None else get_solution(char),
        getattr(request, 'game_version', 'dofus3'))
    seo_class = str(LOCALIZED_CHARACTER_CLASSES.get(char.char_class, char.char_class or ''))
    seo_build = WrappedChar(char).build_string() if char.char_build else ''

    share_text = ''
    build_check = None
    build_score = None
    try:
        _sol_for_text = snapshot_solution if snapshot_solution is not None else get_solution(char)
        if _sol_for_text is not None:
            share_text = _build_share_text(request, char, _sol_for_text)
            build_check = _build_check(char, _sol_for_text)
            build_score = calculate_project_build_score(char, _sol_for_text)
    except Exception:
        share_text = ''
        build_check = None
        build_score = None

    params = {'char_id': char_id,
              'lock_item': static('chardata/lock-icon.png'),
              'switch_item': static('chardata/1412645636_Left-right.png'),
              'delete_item': static('chardata/delete-icon.png'),
              'add_item': static('chardata/add-icon.png'),
              'ajax_loader': json.dumps(get_ajax_loader_URL(request)),
              'link_external_image': json.dumps(get_external_image_URL(request)),
              'is_guest': is_guest,
              'is_guest_json': json.dumps(is_guest),
              'encoded_char_id': encoded_char_id,
              'link_shared': char.link_shared,
              'owner_alias': get_alias(char.owner),
              'is_dueler': chardata.smart_build.char_has_aspect(char, 'duel'),
              'class_avatar': class_avatar,
              'character_look': json.dumps(character_look) if character_look else '',
              'character_colors': parse_colors(char.colors, _default_colors(char)) if character_look else [],
              'character_pieces': _preview_pieces(char, character_look) if character_look else [],
              'character_asset_version': asset_token() if character_look else '',
              'character_asset_formats': json.dumps(asset_formats()),
              'character_preloads': preload_links(character_look),
              'canonical_path': shared_build_path(char) if char.link_shared else '',
              'preview_box': _preview_box_for(request.user) if character_look else None,
              'seo_class': seo_class,
              'seo_build': seo_build,
              'share_text': share_text,
              'build_check': build_check,
              'build_score': build_score,
              'has_build_score': build_score is not None,
              # The history deltas always compare against the CURRENT build. When
              # viewing a saved generation, build_score is that snapshot's score,
              # not the current build's, so pass None there and let the helper
              # score the current solution (otherwise the snapshot's own row read
              # 0 and every other delta used the wrong baseline).
              # The history deltas always compare against the CURRENT build. When
              # viewing a saved generation, build_score is that snapshot's score,
              # not the current build's, so pass None there and let the helper
              # score the current solution (otherwise the snapshot's own row read
              # 0 and every other delta used the wrong baseline).
              'generation_history': [] if is_guest else _build_generation_history(
                  request, char, generation,
                  None if is_generation_snapshot else build_score),
              'is_generation_snapshot': is_generation_snapshot,
              'generation_created_time': generation.created_time if generation else None,
              'restore_generation_url': (
                  version_reverse(request, 'restore_generation', char.id, generation.id)
                  if generation else ''),
              'current_solution_url': version_reverse(request, 'solution_2', char.id),
              'current_solution_compare_id': char.id,
              'disable_solution_item_actions': is_generation_snapshot,
              'stat_filter_options_json': json.dumps(_get_stat_filter_options())}
              
    if char.link_shared:
        params['initial_link'] = generate_link(request, char)
        params['comments'] = get_comments_for_build(char, request.user)
        params['comments_json'] = json.dumps(params['comments'])
    else:
        params['comments'] = []
        params['comments_json'] = '[]'

    # "With buffs" stat preview: the character's class self-buffs fully active.
    game_version = getattr(request, 'game_version', 'dofus3')
    spell_buff_stats = compute_full_buff_stats(char, game_version)
    params['spell_buff_stats_json'] = json.dumps(spell_buff_stats)
    params['has_spell_buffs'] = bool(spell_buff_stats)

    params['build_tags'] = [{'id': t.id, 'name': t.display_name, 'slug': t.name}
                            for t in char.tags.all().order_by('created_time')]
    params['can_edit_tags'] = (not is_guest
                               and char.owner_id is not None
                               and request.user.is_authenticated
                               and char.owner_id == request.user.id)

    params.update(vote_data)
    params.update(solution_params)

    if not is_guest:
        from chardata.inventory_solver import get_effective_stat_overrides
        from chardata.item_exchange import _owned_item_ids
        raw_overrides = get_effective_stat_overrides(char)
        stat_overrides_json = {str(item_id): {str(stat_id): val for stat_id, val in stats.items()}
                               for item_id, stats in raw_overrides.items()}
        params['stat_overrides_json'] = json.dumps(stat_overrides_json)
        owned_ids = _owned_item_ids(request, char)
        params['owned_item_ids_json'] = json.dumps(sorted(owned_ids)) if owned_ids else None
        params['base_options_json'] = json.dumps(get_options(request, char_id))

    response = set_response(request,
                            'chardata/solution.html',
                            params,
                            char)
    return response


def get_sharing_link(request, char_id):
    char = get_char_or_raise(request, char_id)

    char.link_shared = True
    char.save()
    
    return HttpResponseText(generate_link(request, char))

def hide_sharing_link(request, char_id):
    char = get_char_or_raise(request, char_id)

    char.link_shared = False
    char.save()
        
    return HttpResponseText('hid')

def get_client_ip(request):
    """Client IP from the request, or None if it doesn't parse as an IP
    (X-Forwarded-For is client-controlled)."""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    if not ip:
        return None
    try:
        ipaddress.ip_address(ip)
    except ValueError:
        return None
    return ip

def solution_linked(request, char_name, encoded_char_id):
    char = get_char_encoded_or_raise(encoded_char_id)
    if char.game_version != getattr(request, 'game_version', 'dofus3'):
        raise Http404
    # A shared build whose solution was never stored (or was reset) cannot
    # render the solution page; 404 instead of an AttributeError 500.
    if get_solution(char) is None:
        raise Http404

    # Increment view count only once per IP per 24 hours
    try:
        ip_address = get_client_ip(request)
        if ip_address:  # Only track if we can get an IP
            twenty_four_hours_ago = timezone.now() - timedelta(hours=24)
            
            # Check if this IP has viewed this build in the last 24 hours
            recent_view = BuildView.objects.filter(
                build=char,
                ip_address=ip_address,
                viewed_at__gte=twenty_four_hours_ago
            ).exists()
            
            if not recent_view:
                # Record the view
                BuildView.objects.create(build=char, ip_address=ip_address)
                # Bump the counter without char.save(): a full save rewrites
                # every blob column and (auto_now) bumps modified_time, which
                # pollutes the "recently updated" ordering, the API's
                # modified_at, and the shared-build meta cache key on every
                # single view.
                Char.objects.filter(pk=char.pk).update(view_count=F('view_count') + 1)
                char.view_count += 1
    except Exception as e:
        # If view tracking fails, log it but don't break the page
        logger.warning('View tracking error: %s', e)
    
    return _solution(request, char.pk, True, encoded_char_id, char=char)

def _shared_build_slug(char):
    """A build nobody named used to be filed under the word "shared", which
    told a reader and a search engine nothing. The class and level are what
    the page is about, and the title already says exactly that."""
    if char.char_name:
        return char.char_name
    parts = [str(char.char_class or '').strip(), str(char.level or '').strip()]
    slug = '-'.join(p for p in parts if p).lower().replace(' ', '-')
    return slug or 'shared'


def shared_build_path(char):
    """The one url a shared build lives at. The name in the path is decorative
    (the view reads only the id), so every spelling of it serves the same page
    and would claim to be canonical on its own."""
    from urllib.parse import quote
    prefix = '' if char.game_version in (None, '', 'dofus3') else '/' + char.game_version
    return '%s/s/%s/%s/' % (prefix,
                            quote(_shared_build_slug(char).encode('utf-8'),
                                  safe=''),
                            encode_char_id(int(char.id)))


def generate_link(request, char):
    encoded_id = encode_char_id(int(char.id))
    char_name = char.char_name or 'shared'
    return request.build_absolute_uri(version_reverse(request, 'solution_linked',
                                                      char_name, encoded_id))

def set_item_locked(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    slot = request.POST.get('slot', None)
    item_name = request.POST.get('equip', None)
    locked = request.POST.get('locked', None)

    if slot not in SLOTS:
        return HttpResponseBadRequest('unknown slot')

    structure = get_structure()
    item = structure.get_item_by_name(item_name)
    if item is None:
        or_item = structure.get_or_item_by_name(item_name)
        item_id = or_item[0].id
    else:
        item_id = structure.get_item_by_name(item_name).id
    if locked == 'true':
        set_item_included(char, item_id, slot, True)
    elif locked == 'false':
        set_item_included(char, item_id, slot, False)
    
    return HttpResponseText('ok')

def set_char_gender(request, char_id):
    """Only the preview reads this, so nothing about the build changes."""
    char = get_char_or_raise(request, char_id)
    char.gender = 1 if request.POST.get('gender') == '1' else 0
    char.save(update_fields=['gender'])
    look = get_character_look(char, get_solution(char),
                              getattr(request, 'game_version', 'dofus3'))
    return HttpResponseJson(json.dumps(look or {}))


def set_char_colors(request, char_id):
    """Same as the sex switch: the preview only, never the build."""
    char = get_char_or_raise(request, char_id)
    defaults = _default_colors(char)
    wanted = parse_colors(request.POST.get('colors'), defaults)
    char.colors = '' if wanted == defaults else ','.join(wanted)
    char.save(update_fields=['colors'])
    look = get_character_look(char, get_solution(char),
                              getattr(request, 'game_version', 'dofus3'))
    return HttpResponseJson(json.dumps(look or {}))


def set_char_hidden(request, char_id):
    """Which pieces the preview leaves off. The solution keeps them all."""
    char = get_char_or_raise(request, char_id)
    char.hidden_parts = ','.join(parse_hidden(request.POST.get('hidden')))
    char.save(update_fields=['hidden_parts'])
    look = get_character_look(char, get_solution(char),
                              getattr(request, 'game_version', 'dofus3'))
    return HttpResponseJson(json.dumps(look or {}))


def set_item_forbidden(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    slot = request.POST.get('slot', None)
    item_name = request.POST.get('equip', None)
    forbidden = request.POST.get('forbidden', None)
    
    structure = get_structure()
    item = structure.get_item_by_name(item_name)
    if item is None:
        or_item = structure.get_or_item_by_name(item_name)
        item_id = or_item[0].id
    else:
        item_id = structure.get_item_by_name(item_name).id
    
    if forbidden == 'true':
        set_excluded(char, item_id, True)
    elif forbidden == 'false':
        set_excluded(char, item_id, False)

    return HttpResponseText('ok')

def set_slot_lock_empty(request, char_id):
    char = get_char_or_raise(request, char_id)

    slot = request.POST.get('slot', None)
    locked = request.POST.get('locked', None)

    if slot not in SLOTS:
        return HttpResponseBadRequest('unknown slot')

    set_empty_slot(char, slot, locked == 'true')

    return HttpResponseText('ok')
