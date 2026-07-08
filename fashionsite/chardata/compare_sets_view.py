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

from collections import Counter
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, Http404
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
import json
import jsonpickle
from urllib.parse import urlencode, urlparse

from chardata.encoded_char_id import decode_char_id, encode_char_id
from chardata.models import BuildVote, Char, SolutionGeneration
from chardata.solution import get_solution
from chardata.solution_history import get_generation_solution
from chardata.solution_result import SolutionResult, evolve_result_item
from chardata.solution_view import generate_link
from chardata.spell_buffs import get_damage_spells_for_version
from chardata.spells_view import _create_spell_web_digest, _create_weapon_web_digest
from chardata.translation_util import LOCALIZED_CHARACTER_CLASSES
from chardata.util import (set_response, get_char_possibly_encoded_or_raise, get_or_none,
                           HttpResponseText, char_belongs_to_user, get_char_id_possibly_encoded,
                           HttpResponseJson, version_reverse)
from fashionistapulp.dofus_constants import TYPE_NAME_TO_SLOT_NUMBER, TYPE_NAME_TO_SLOT
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure


TYPE_ORDER = [
    'Weapon',
    'Hat',
    'Cloak',
    'Amulet',
    'Ring',
    'Belt',
    'Boots',
    'Pet',
    'Shield',
    'Dofus',
]

COMPARE_SHARE_QUERY_KEYS = ('spell_class', 'spell_name')
COMPARE_PICKER_LIMIT = 24

NON_DAMAGE_PREVIEW_ELEMENTS = {
    'attracts', 'pushes', 'advances', 'steals_mp', 'removes_ap'}


class _CompareBuild:

    def __init__(self, key, char, solution, link, is_guest, shareable, name=None):
        self.id = key
        self.pk = key
        self.char = char
        self.solution = solution
        self.link = link
        self.is_guest = is_guest
        self.shareable = shareable
        self.name = name or char.name
        self.char_name = char.char_name
        self.char_class = char.char_class
        self.level = char.level
        self.link_shared = char.link_shared


def _process_parameters(sets_params):
    return [x for x in sets_params.split('/') if x]


def _resolve_compare_build(request, char_str):
    game_version = getattr(request, 'game_version', 'dofus3')
    if char_str.startswith('g'):
        try:
            generation_id = int(char_str[1:])
        except (TypeError, ValueError):
            raise Http404
        generation = get_object_or_404(SolutionGeneration,
                                       pk=generation_id,
                                       game_version=game_version)
        char = generation.char
        if not char_belongs_to_user(request, char):
            raise PermissionDenied
        solution = get_generation_solution(char, generation)
        if solution is None:
            raise Http404
        link = version_reverse(request, 'solution_generation', char.id, generation.id)
        return _CompareBuild(
            char_str,
            char,
            solution,
            link,
            True,
            False,
            '%s - %s' % (char.name, _('Saved generation')))

    char = get_char_possibly_encoded_or_raise(request, char_str)
    if char.game_version != game_version:
        raise Http404
    solution = get_solution(char)
    if solution is None:
        raise Http404
    is_guest = not char_belongs_to_user(request, char)
    link = generate_link(request, char) if is_guest else version_reverse(request, 'solution_2', char.pk)
    return _CompareBuild(char.pk, char, solution, link, is_guest, char.link_shared)


def compare_sets(request, sets_params):
    char_strs = _process_parameters(sets_params)
    
    chars = []
    for char_str in char_strs:
        try:
            chars.append(_resolve_compare_build(request, char_str))
        except (Http404, PermissionDenied):
            # A build that was removed (or made private) since it was added to the
            # comparison cart: drop it and compare the rest instead of 404ing the
            # whole page.
            continue
    if len(chars) < 2:
        # Fewer than two of the requested builds still exist -- nothing to compare.
        raise Http404
    solutions = {}
    model_results = {}
    is_guest = {}
    links = {}
    all_chars_are_shared = True
    for char in chars:
        solution = char.solution
        model_results[char.pk] = solution
        sol_result = SolutionResult(solution)
        solutions[char.pk] = sol_result.get_params()
        is_guest[char.pk] = char.is_guest
        links[char.pk] = request.build_absolute_uri(char.link)
        all_chars_are_shared = all_chars_are_shared and char.shareable
    
    char_ids = [char.pk for char in chars]
    if len(char_ids) > 2:
        char_ids_cols = char_ids
    else:
        char_ids_cols = char_ids + ['diff']
    
    compare_link_shared = None
    if all_chars_are_shared:
        compare_link_shared = _generate_share_compare_link(
            request, char_ids, _compare_share_query_string(request))

    get_compare_link_url = version_reverse(request, 'get_compare_sharing_link',
                                           sets_params)

    params = {'chars': chars,
              'char_ids': char_ids,
              'char_ids_cols': char_ids_cols,
              'solutions': solutions,
              'items_sorted': _sort_items(solutions),
              'char_is_guest': is_guest,
              'links': links,
              'compare_link_shared': compare_link_shared,
              'get_compare_link_url': get_compare_link_url}
    params.update(_build_spell_preview_context(request, chars, model_results))
    
    response = set_response(request, 
                            'chardata/compare_sets.html',
                            params)
    return response

def _build_spell_preview_context(request, chars, model_results):
    game_version = getattr(request, 'game_version', 'dofus3')
    spells_by_class = get_damage_spells_for_version(game_version)
    reference_char = chars[0]
    available_spell_classes = sorted(
        class_name for class_name in spells_by_class
        if class_name != 'default')
    selected_spell_class = reference_char.char_class
    requested_spell_class = (request.GET.get('spell_class') or '').strip()
    if selected_spell_class not in available_spell_classes and available_spell_classes:
        selected_spell_class = available_spell_classes[0]
    if requested_spell_class in available_spell_classes:
        selected_spell_class = requested_spell_class

    requested_spell_name = (request.GET.get('spell_name') or '').strip()
    spell_entries = []
    for spell in (spells_by_class.get(selected_spell_class, [])
                  + spells_by_class.get('default', [])):
        if not _spell_has_direct_damage(spell):
            continue
        digest = _create_spell_web_digest(spell, game_version)
        compare_key = 'spell_%d' % len(spell_entries)
        digest['compare_key'] = compare_key
        row = {
            'key': compare_key,
            'kind': 'spell',
            'name': digest['name'],
            'image_url': digest['image_url'],
        }
        spell_entries.append({
            'value': spell.name,
            'row': row,
            'digest': digest,
        })
    selected_spell_name = ''
    if requested_spell_name in {entry['value'] for entry in spell_entries}:
        selected_spell_name = requested_spell_name
    displayed_spell_entries = [
        entry for entry in spell_entries
        if not selected_spell_name or entry['value'] == selected_spell_name
    ]
    spell_rows = [entry['row'] for entry in displayed_spell_entries]
    spell_digests = [entry['digest'] for entry in displayed_spell_entries]

    weapon_digests = {}
    for char in chars:
        solution = model_results.get(char.pk)
        if solution is None:
            continue
        weapons = solution.items.get('Weapon', [])
        if not weapons:
            continue
        weapon = weapons[0]
        if weapon.item_added and hasattr(weapon, 'non_crit_hits'):
            weapon_digests[str(char.pk)] = _create_weapon_web_digest(weapon)

    rows = []
    if weapon_digests:
        rows.append({
            'key': 'weapon',
            'kind': 'weapon',
            'name': _('Weapon'),
            'image_url': '',
        })
    rows.extend(spell_rows)

    return {
        'spell_preview_rows': rows,
        'spell_preview_selected_class': selected_spell_class,
        'spell_preview_class_options': [
            {
                'value': class_name,
                'label': str(LOCALIZED_CHARACTER_CLASSES.get(class_name, class_name)),
                'selected': class_name == selected_spell_class,
            }
            for class_name in available_spell_classes
        ],
        'spell_preview_selected_spell': selected_spell_name,
        'spell_preview_spell_options': (
            [{
                'value': '',
                'label': str(_('All damage spells')),
                'selected': selected_spell_name == '',
            }] + [
                {
                    'value': entry['value'],
                    'label': entry['row']['name'],
                    'selected': entry['value'] == selected_spell_name,
                }
                for entry in spell_entries
            ] if spell_entries else []
        ),
        'spell_preview_digests_json': jsonpickle.encode(
            spell_digests, unpicklable=False),
        'weapon_digests_json': jsonpickle.encode(
            weapon_digests, unpicklable=False),
        'char_levels_json': json.dumps(
            {str(char.pk): char.level for char in chars}),
    }


def _spell_has_direct_damage(spell):
    digest = spell.get_effects_digest()
    for level_dams in list(digest.non_crit_dams) + list(digest.crit_dams):
        for effect in level_dams:
            if _is_direct_damage_effect(effect):
                return True
    return False


def _is_direct_damage_effect(effect):
    return (not getattr(effect, 'heals', False)
            and 'buff' not in effect.element
            and effect.element not in NON_DAMAGE_PREVIEW_ELEMENTS)


def _sort_items(solutions):
    item_counters = {}
    for type_name in TYPE_ORDER:
        slot_number = TYPE_NAME_TO_SLOT_NUMBER[type_name]
        if slot_number > 1:
            item_counter = Counter()
            slot_name = TYPE_NAME_TO_SLOT[type_name]
            for _, solution in solutions.items():
                for i in range(1, slot_number + 1):
                    slot_key = "%s%d" % (slot_name, i)
                    item = solution['item_per_slot'].get(slot_key)
                    if item is not None and item.item_added:
                        item_counter[item.or_name] += 1
            item_counters[type_name] = item_counter

    result = {}
    for char_id, solution in solutions.items():
        result[char_id] = []

        for type_name in TYPE_ORDER:
            slot_number = TYPE_NAME_TO_SLOT_NUMBER[type_name]
            slot_name = TYPE_NAME_TO_SLOT[type_name]
            if slot_number > 1:
                item_counter = item_counters[type_name]
                items_sorted_by_popularity = []
                for i in range(1, slot_number + 1):
                    slot_key = "%s%d" % (slot_name, i)
                    item = solution['item_per_slot'].get(slot_key)
                    items_sorted_by_popularity.append(item)
                def get_key(item):
                    if item and item.item_added:
                        return (-item_counter.get(item.or_name, 0), item.or_name)
                    else:
                        return (0, '') 
                items_sorted_by_popularity.sort(key=get_key)
                result[char_id].extend(items_sorted_by_popularity)
            else:
                item = solution['item_per_slot'].get(slot_name)
                result[char_id].append(item)
    return result

def choose_compare_sets(request):
    params = {
        'compare_picker_sections': _build_compare_picker_sections(request),
    }
             
    for i in range(4):
        char_id = request.POST.get('char%d' % i, None)
        if char_id:
            params['char%d' % i] = char_id
            
    return set_response(request, 
                        'chardata/choose_compare_sets.html',
                        params)


def _build_compare_picker_sections(request):
    if not request.user.is_authenticated:
        return []

    game_version = getattr(request, 'game_version', 'dofus3')
    own_builds = (Char.objects
                  .filter(owner=request.user, deleted=False, game_version=game_version)
                  .exclude(minimal_solution=b'')
                  .order_by('-modified_time')[:COMPARE_PICKER_LIMIT])

    favorite_votes = (BuildVote.objects
                      .filter(user=request.user, vote_type='favorite',
                              build__deleted=False, build__game_version=game_version)
                      .exclude(build__minimal_solution=b'')
                      .select_related('build')
                      .order_by('-created_time')[:COMPARE_PICKER_LIMIT])
    liked_votes = (BuildVote.objects
                   .filter(user=request.user, vote_type='like',
                           build__deleted=False, build__game_version=game_version)
                   .exclude(build__minimal_solution=b'')
                   .select_related('build')
                   .order_by('-created_time')[:COMPARE_PICKER_LIMIT])

    return [
        {
            'key': 'owned',
            'title': _('My builds'),
            'empty': _('No saved builds with a solution yet.'),
            'builds': _compare_picker_entries(request, own_builds),
        },
        {
            'key': 'favorites',
            'title': _('Favorites'),
            'empty': _('No favorite builds for this version yet.'),
            'builds': _compare_picker_entries(
                request, (vote.build for vote in favorite_votes)),
        },
        {
            'key': 'likes',
            'title': _('Likes'),
            'empty': _('No liked builds for this version yet.'),
            'builds': _compare_picker_entries(
                request, (vote.build for vote in liked_votes)),
        },
    ]


def _compare_picker_entries(request, chars):
    entries = []
    seen = set()
    for char in chars:
        if char.pk in seen:
            continue
        seen.add(char.pk)
        link = _compare_picker_link(request, char)
        if not link:
            continue
        entries.append({
            'id': char.pk,
            'name': char.name,
            'char_class': LOCALIZED_CHARACTER_CLASSES.get(char.char_class, char.char_class),
            'level': char.level,
            'build': char.char_build,
            'link': link,
        })
    return entries


def _compare_picker_link(request, char):
    if char_belongs_to_user(request, char):
        return version_reverse(request, 'solution_2', char.pk)
    if char.link_shared:
        return generate_link(request, char)
    return ''

@require_POST
def choose_compare_sets_post(request):
    links_json = request.POST.get('links', None)
    if links_json is None:
        return _get_text_error_response(_('Paste links of at least 2 projects to compare'))
    try:
        parsed_links = json.loads(links_json)
        if not isinstance(parsed_links, list):
            raise ValueError
        links = [
            link.strip() for link in parsed_links
            if isinstance(link, str) and link.strip()
        ]
    except (ValueError, TypeError):
        return _get_text_error_response(_('Paste links of at least 2 projects to compare'))
    links_digested = [_process_link(l) for l in links]
    
    if len(links_digested) <= 1:
        return _get_text_error_response(_('Paste links of at least 2 projects to compare'))
    if len(links_digested) > 4:
        return _get_text_error_response(_('Choose at most 4 builds to compare'))

    # Validation
    char_ids = []
    for i, mystery_char_id in enumerate(links_digested):
        if not mystery_char_id:
            return _get_text_error_response(_('%s is not a valid share link') % links[i])
        if mystery_char_id.startswith('g') and mystery_char_id[1:].isdigit():
            generation = get_or_none(SolutionGeneration, pk=int(mystery_char_id[1:]))
            if not generation or generation.game_version != getattr(request, 'game_version', 'dofus3'):
                return _get_text_error_response(_('%s does not refer to a valid project')
                                                % links[i])
            if not char_belongs_to_user(request, generation.char):
                return _get_text_error_response(_('%s refers to someone else\'s project')
                                                % links[i])
            char_ids.append(mystery_char_id)
        elif mystery_char_id.isdigit():
            char_id = int(mystery_char_id)
            char = get_or_none(Char, pk=char_id)
            if not char or char.game_version != getattr(request, 'game_version', 'dofus3'):
                return _get_text_error_response(_('%s does not refer to a valid project')
                                                % links[i])
            if not char_belongs_to_user(request, char):
                return _get_text_error_response(_('%s refers to someone else\'s project')
                                                % links[i])
            char_ids.append(mystery_char_id)
        else:
            try:
                char_id = decode_char_id(mystery_char_id)
            except:
                char_id = None
            if char_id is None:
                return _get_text_error_response(_('%s is not a valid share link') % links[i])
            char = get_or_none(Char, pk=char_id)
            if not char or char.game_version != getattr(request, 'game_version', 'dofus3'):
                return _get_text_error_response(_('%s does not refer to a valid project')
                                                % links[i])
            if not char.link_shared:
                return _get_text_error_response(_('%s is not shared') % links[i])
            char_ids.append('s' + mystery_char_id)

    compare_path = '/'.join(char_ids)

    return HttpResponseText(version_reverse(request, 'compare_sets', compare_path))

def _process_link(l):
    parsed = urlparse(l)
    path_pieces = [piece for piece in parsed.path.split('/') if piece]
    if len(path_pieces) >= 3 and path_pieces[-3] == 'solutiongeneration':
        return 'g%s' % path_pieces[-1]
    for path_piece in reversed(path_pieces):
        if path_piece:
            return path_piece
    return None

def get_sharing_link(request, sets_params):
    char_strs = _process_parameters(sets_params)
    char_ids = []
    for char_str in char_strs:
        if char_str.startswith('g'):
            return _get_text_error_response(_('Saved generations cannot be shared directly.'))
        char_id, was_encoded = get_char_id_possibly_encoded(char_str)
        char = get_object_or_404(Char, pk=char_id)
        if char.game_version != getattr(request, 'game_version', 'dofus3'):
            return _get_text_error_response(_('Project %s is not in this game version.') % char_str)
        if char_belongs_to_user(request, char):
            # Share it, if still not shared.
            if not char.link_shared:
                char.link_shared = True
                char.save()
        else:
            # Verify it had a signature and was shared.
            if not was_encoded:
                raise PermissionDenied
            if not char.link_shared:
                return _get_text_error_response(_('Project %s is not shared.') % char_str)
        char_ids.append(char_id)

    return HttpResponseText(_generate_share_compare_link(
        request, char_ids, _compare_share_query_string(request)))


def _compare_share_query_string(request):
    query = []
    for key in COMPARE_SHARE_QUERY_KEYS:
        value = (request.GET.get(key) or '').strip()
        if value:
            query.append((key, value))
    return urlencode(query)


def _generate_share_compare_link(request, char_ids, query_string=''):
    params = '/'.join(['s%s' % encode_char_id(char_id) for char_id in char_ids])
    url = request.build_absolute_uri(version_reverse(request, 'compare_sets', params))
    if query_string:
        url = '%s?%s' % (url, query_string)
    return url

def get_item_stats(request):
    item_id = request.POST.get('itemId', None)
    if item_id == '':
        return HttpResponseJson(None)
    try:
        item_id = int(item_id)
    except (TypeError, ValueError):
        return HttpResponseJson(None)
    structure = get_structure()
    item = structure.get_item_by_id(item_id)
    if item is None:
        # Stale compare page or an id from another game version: no such item
        # in the current structure, answer null like the empty-id case.
        return HttpResponseJson(None)
    result_item = ModelResultItem(item)
    evolve_result_item(result_item)
    
    json_response = jsonpickle.encode(result_item, unpicklable=False)
    
    return HttpResponseJson(json_response)


def compare_set_search_proj_name(request):
    name_piece = request.POST.get('name[term]', None)
    
    if (request.user is not None and not request.user.is_anonymous):
        chars = Char.objects.filter(
            owner=request.user,
            game_version=getattr(request, 'game_version', 'dofus3'))
        chars = chars.exclude(deleted=True)
        
        char_list = []
        if name_piece:
            name_piece = name_piece.lower()
            for char in chars:
                if name_piece in char.name.lower():
                    if get_solution(char) is not None:
                        char_list.append({'label': char.name, 'idx': char.id})
    else:
        char_list = []
    return JsonResponse(char_list, safe=False)

def _get_text_error_response(cause):
    return HttpResponseText('Error: %s' % cause)
