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
from django.urls import reverse
from django.shortcuts import get_object_or_404
from django.utils.translation import gettext as _
from django.views.decorators.http import require_POST
import json
import jsonpickle
from urllib.parse import urlparse

from chardata.encoded_char_id import decode_char_id, encode_char_id
from chardata.models import Char
from chardata.solution import get_solution
from chardata.solution_result import SolutionResult, evolve_result_item
from chardata.solution_view import generate_link
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

def _process_parameters(sets_params):
    return [x for x in sets_params.split('/') if x]

def compare_sets(request, sets_params):
    char_strs = _process_parameters(sets_params)
    
    chars = []
    for char_str in char_strs:
        try:
            chars.append(get_char_possibly_encoded_or_raise(request, char_str))
        except (Http404, PermissionDenied):
            # A build that was removed (or made private) since it was added to the
            # comparison cart: drop it and compare the rest instead of 404ing the
            # whole page.
            continue
    if len(chars) < 2:
        # Fewer than two of the requested builds still exist -- nothing to compare.
        raise Http404
    solutions = {}
    is_guest = {}
    links = {}
    all_chars_are_shared = True
    for char in chars:
        solution = get_solution(char)
        sol_result = SolutionResult(solution)
        solutions[char.pk] = sol_result.get_params()
        is_guest[char.pk] = not char_belongs_to_user(request, char)
        if not char_belongs_to_user(request, char):
            links[char.pk] = generate_link(request, char)
        else:
            links[char.pk] = request.build_absolute_uri(reverse('solution_2',
                                    args=(char.pk,)))
        all_chars_are_shared = all_chars_are_shared and char.link_shared
    
    char_ids = [char.pk for char in chars]
    if len(char_ids) > 2:
        char_ids_cols = char_ids
    else:
        char_ids_cols = char_ids + ['diff']
    
    compare_link_shared = None
    if all_chars_are_shared:
        compare_link_shared = _generate_share_compare_link(request, char_ids)

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
    
    response = set_response(request, 
                            'chardata/compare_sets.html',
                            params)
    return response

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
    params = {}
             
    for i in range(4):
        char_id = request.POST.get('char%d' % i, None)
        if char_id:
            params['char%d' % i] = char_id
            
    return set_response(request, 
                        'chardata/choose_compare_sets.html',
                        params)

@require_POST
def choose_compare_sets_post(request):
    links_json = request.POST.get('links', None)
    if links_json is None:
        return _get_text_error_response(_('Paste links of at least 2 projects to compare'))
    try:
        links = json.loads(links_json)
    except (ValueError, TypeError):
        return _get_text_error_response(_('Paste links of at least 2 projects to compare'))
    links_digested = [_process_link(l) for l in links]
    
    if len(links_digested) <= 1:
        return _get_text_error_response(_('Paste links of at least 2 projects to compare'))

    # Validation
    char_ids = []
    for i, mystery_char_id in enumerate(links_digested):
        if mystery_char_id.isdigit():
            char_id = int(mystery_char_id)
            char = get_or_none(Char, pk=char_id)
            if not char:
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
            if not char.link_shared:
                return _get_text_error_response(_('%s is not shared') % links[i])
            char_ids.append('s' + mystery_char_id)

    compare_path = '/'.join(char_ids)

    return HttpResponseText(version_reverse(request, 'compare_sets', compare_path))

def _process_link(l):
    parsed = urlparse(l)
    path_pieces = parsed.path.split('/')
    for path_piece in reversed(path_pieces):
        if path_piece:
            return path_piece
    return None

def get_sharing_link(request, sets_params):
    char_strs = _process_parameters(sets_params)
    char_ids = []
    for char_str in char_strs:
        char_id, was_encoded = get_char_id_possibly_encoded(char_str)
        char = get_object_or_404(Char, pk=char_id)
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

    return HttpResponseText(_generate_share_compare_link(request, char_ids))

def _generate_share_compare_link(request, char_ids):
    params = '/'.join(['s%s' % encode_char_id(char_id) for char_id in char_ids])
    return request.build_absolute_uri(version_reverse(request, 'compare_sets', params))

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
        chars = Char.objects.filter(owner=request.user)
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
    return HttpResponseText('Error')
