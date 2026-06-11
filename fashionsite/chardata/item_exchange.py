# -*- coding: utf-8 -*-

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

import json
import jsonpickle
import math
import pickle
import re
from django.core.cache import cache
from fashionistapulp.fashion_util import strip_accents
#import cProfile

from chardata.inventory_solver import get_effective_stat_overrides
from chardata.min_stats import get_min_stats_digested_by_key
from chardata.solution import get_solution, set_solution
from chardata.solution_result import evolve_result_item, AttributeLine
from chardata.util import get_char_or_raise, HttpResponseText, HttpResponseJson,\
    remove_cache_for_char
from fashionistapulp.dofus_constants import SLOTS, STAT_ORDER, SLOT_NAME_TO_TYPE, calculate_damage,\
    DAMAGE_TYPES, NEUTRAL, ELEMENT_KEY_TO_NAME
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure
from fashionistapulp.translation import get_supported_language
from django.utils.translation import gettext as _


def _parse_stat_filters(request):
    raw_filters = request.POST.get('stat_filters_json', None)
    if raw_filters is None:
        return []
    try:
        parsed = json.loads(raw_filters)
    except Exception:
        return []

    valid_stat_keys = {stat.key for stat in get_structure().get_stats_list()}
    filters = []
    for row in parsed if isinstance(parsed, list) else []:
        if not isinstance(row, dict):
            continue
        stat_key = row.get('key', None)
        min_raw = row.get('min', None)
        if stat_key not in valid_stat_keys:
            continue
        try:
            min_value = int(min_raw)
        except (TypeError, ValueError):
            continue
        filters.append({'key': stat_key, 'min': min_value})
    return filters


def _get_item_stats_by_key(item):
    structure = get_structure()
    normalized_item = item
    if item.name in structure.or_items:
        normalized_item = structure.get_or_item_by_name(item.name)[0]
    stats_by_key = {}
    for stat_id, stat_value in normalized_item.stats:
        stat_obj = structure.get_stat_by_id(stat_id)
        if stat_obj is not None:
            stats_by_key[stat_obj.key] = stat_value
    return stats_by_key


def _apply_stat_filters(items, stat_filters):
    if not stat_filters:
        return items
    filtered = []
    for item in items:
        stats_by_key = _get_item_stats_by_key(item)
        include = True
        for stat_filter in stat_filters:
            if stats_by_key.get(stat_filter['key'], 0) < stat_filter['min']:
                include = False
                break
        if include:
            filtered.append(item)
    return filtered


def _order_items(item_type, char, search_term, stat_filters=None):
    structure = get_structure()
    items = structure.get_unique_items_by_type_and_level(item_type, char.level)
    search_term = search_term.lower()
    search_term = strip_accents(search_term)
    if search_term is not None:
        items = [i for i in items if _item_contains_term(i, re.sub(r'\W+', '', search_term))]
    items = [i for i in items if _hide_removed_item(i)]
    items = _apply_stat_filters(items, stat_filters or [])
    weights = pickle.loads(char.stats_weight)
    sorted_items = sorted(items, key=lambda item: _rate(structure, item, weights), reverse=True)
    return sorted_items

def _hide_removed_item(item):
    s = get_structure()
    if item.name in s.or_items:
        item = s.get_or_item_by_name(item.name)[0]
    if item.removed:
        return False
    return True

def _owned_item_ids(request, char):
    """Item ids in the project owner's inventory (any folder of this game
    version), or None when the inventory does not apply (guest/anonymous)."""
    if not request.user.is_authenticated or char.owner_id != request.user.id:
        return None
    from chardata.models import InventoryItem
    return set(InventoryItem.objects.filter(
        folder__user=request.user,
        folder__game_version=char.game_version).values_list('item_id', flat=True))

def _is_owned(structure, item, owned_ids):
    if item.id in owned_ids:
        return True
    if item.name in structure.or_items:
        return any(variant.id in owned_ids
                   for variant in structure.get_or_item_by_name(item.name))
    return False

def _order_by_hits(item_type, char, search_term, stat_filters=None):
    structure = get_structure()
    items = structure.get_unique_items_by_type_and_level(item_type, char.level)
    search_term = search_term.lower()
    search_term = strip_accents(search_term)
    if search_term is not None and search_term != '':
        items = [i for i in items if _item_contains_term(i, re.sub(r'\W+', '', search_term))]
    items = [i for i in items if _hide_removed_item(i)]
    items = _apply_stat_filters(items, stat_filters or [])
    solution = get_solution(char)
    if solution is None:
        return items
    sorted_items = sorted(items, key=lambda item: _get_weapon_rate(item, char, solution), reverse=True)
    #print sorted_items[:5]
    return sorted_items

def _item_contains_term(item, search_term):
    s = get_structure()
    or_items = s.get_or_items()
    if item.name in or_items:
        item = s.get_or_item_by_name(item.name)[0]
    item_name = ''
    if get_supported_language() in item.localized_names:
        item_name = item.accentless_local_names[get_supported_language()].lower()
    else:
        item_name = item.name.lower()
    
    search_term = re.sub(r'\W+', '', search_term)
    item_name = re.sub(r'\W+', '', item_name)
    return search_term in item_name

def _rate(structure, item, weights):
    rating = 0
    if item.name in structure.or_items:
        item = structure.get_or_item_by_name(item.name)[0]
    for stat in item.stats:
        if structure.get_stat_by_id(stat[0]).key in weights:
            rating += stat[1] * weights[structure.get_stat_by_id(stat[0]).key]
    return rating
    
def check_if_violates(item, slot, char, stat_overrides=None):
    result = get_solution(char)
    if result is None:
        return []
    result.switch_item(item, slot, stat_overrides)
    minimums = get_min_stats_digested_by_key(char)
    return result.get_all_project_violations(item.type, minimums)

def get_items_of_type(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    page = int(request.POST.get('page', None))
    search_term = request.POST.get('search_term', None)
    slot = request.POST.get('slot', None)
    stat_filters = _parse_stat_filters(request)
    
    itype = SLOT_NAME_TO_TYPE[slot]
    structure = get_structure()
    
    cache_key = ('%s-%s-%s-%s' % (char_id,
                                  structure.get_type_id_by_name(itype),
                                  search_term,
                                  jsonpickle.encode(stat_filters, unpicklable=False)))
    cache_key = re.sub(r"\s+", '_', cache_key) 
    items = cache.get(cache_key)
    
    if items == None:
        items = _order_items(itype, char, search_term, stat_filters)
    cache.set(cache_key, items, 300)

    # Filtered after the cache so inventory edits show up immediately.
    owned_ids = _owned_item_ids(request, char)
    inventory_only = (request.POST.get('inventory_only') == 'true'
                      and owned_ids is not None)
    if inventory_only:
        items = [i for i in items if _is_owned(structure, i, owned_ids)]

    max_page = math.ceil(len(items) / 10.0)
    items_to_return = items[(page - 1) * 10 : page * 10]

    # Saved inventory rolls / manual overrides, so listed items show the
    # stats the solver actually counts.
    effective_overrides = get_effective_stat_overrides(char) or None

    itemResults = []
    for item in items_to_return:
        if item.name in structure.or_items:
            for or_item in structure.get_or_item_by_name(item.name):
                owned = owned_ids is not None and or_item.id in owned_ids
                # The whole or-group passes the inventory filter as soon as
                # one variant is owned; only surface the owned roll(s).
                if inventory_only and not owned:
                    continue
                result_item = ModelResultItem(or_item, effective_overrides)
                evolve_result_item(result_item)
                result_item.owned = owned
                itemResults.append(result_item)
        else:
            result_item = ModelResultItem(item, effective_overrides)
            evolve_result_item(result_item)
            result_item.owned = (owned_ids is not None
                                 and _is_owned(structure, item, owned_ids))
            itemResults.append(result_item)
        
    response = {'items': itemResults,
                'violations': None,
                'page': page,
                'max_page': max_page,
                'differences': None}
    
    json_response = jsonpickle.encode(response, unpicklable=False)
    
    return HttpResponseJson(json_response)  
    
def get_items_to_exchange(request, char_id):
    char = get_char_or_raise(request, char_id)
        
    slot = request.POST.get('slot', None)
    page = int(request.POST.get('page', 1))
    search_term = request.POST.get('search_term', None)
    order_by_stats = request.POST.get('order_by_stat', True)
    stat_filters = _parse_stat_filters(request)
    
    assert slot in SLOTS
    assert int(page) >= 0
    
    structure = get_structure()
    item_type = structure.get_type_id_by_name(SLOT_NAME_TO_TYPE.get(slot))
    
    cache_key = ('%s-%s-%s-%s-%s' % (char_id,
                                     item_type,
                                     search_term,
                                     order_by_stats,
                                     jsonpickle.encode(stat_filters, unpicklable=False)))
    cache_key = re.sub(r"\s+", '_', cache_key) 
    items_to_exchange = cache.get(cache_key) 
    
    if items_to_exchange == None:
        if slot == 'weapon' and order_by_stats == 'false':
            items_to_exchange = _order_by_hits(structure.get_type_name_by_id(item_type), char,
                                                                                             search_term, stat_filters)
        else:
            items_to_exchange = _order_items(structure.get_type_name_by_id(item_type), char,
                                                                                         search_term, stat_filters)
    cache.set(cache_key, items_to_exchange, 300)

    # Filtered after the cache so inventory edits show up immediately.
    owned_ids = _owned_item_ids(request, char)
    inventory_only = (request.POST.get('inventory_only') == 'true'
                      and owned_ids is not None)
    if inventory_only:
        items_to_exchange = [i for i in items_to_exchange
                             if _is_owned(structure, i, owned_ids)]

    max_page = math.ceil(len(items_to_exchange) / 10.0)

    items_to_return = items_to_exchange[(page - 1) * 10 : page * 10]
    violations = {}
    differences = {}
    itemResults = []
    weapon_info = {}
    # Saved inventory rolls / manual overrides, so listed items show the
    # stats the solver actually counts.
    effective_overrides = get_effective_stat_overrides(char) or None
    for item in items_to_return:
        if item.name in structure.or_items:
            for or_item in structure.get_or_item_by_name(item.name):
                owned = owned_ids is not None and or_item.id in owned_ids
                # The whole or-group passes the inventory filter as soon as
                # one variant is owned; only surface the owned roll(s).
                if inventory_only and not owned:
                    continue
                result_item = ModelResultItem(or_item, effective_overrides)
                result_item.set_slot(slot)
                evolve_result_item(result_item)
                result_item.owned = owned
                itemResults.append(result_item)
                vlist = []
                for vio in check_if_violates(or_item, slot, char, effective_overrides):
                    vlist.append(vio)
                violations[or_item.name] = vlist
                differences[or_item.name] = _get_difference(or_item, slot, char,
                                                            effective_overrides)
                if slot == 'weapon':
                    weapon_info[or_item.name] = _get_weapon_info(or_item, char,
                                                                 effective_overrides)
        else:
            result_item = ModelResultItem(item, effective_overrides)
            result_item.set_slot(slot)
            evolve_result_item(result_item)
            result_item.owned = (owned_ids is not None
                                 and _is_owned(structure, item, owned_ids))
            itemResults.append(result_item)
            vlist = []
            for vio in check_if_violates(item, slot, char, effective_overrides):
                vlist.append(vio)
            violations[item.name] = vlist
            differences[item.name] = _get_difference(item, slot, char,
                                                     effective_overrides)
            if slot == 'weapon':
                weapon_info[item.name] = _get_weapon_info(item, char,
                                                          effective_overrides)
    
            
    response = {'items': itemResults,
                'violations': violations,
                'page': page,
                'max_page': max_page,
                'weapon_info': weapon_info,
                'differences': differences}
    
    json_response = jsonpickle.encode(response, unpicklable=False)
    
    return HttpResponseJson(json_response)

def switch_item(request, char_id): 
    char = get_char_or_raise(request, char_id)
    item_name = request.POST.get('itemName', None)
    slot = request.POST.get('slot', None)
    assert slot in SLOTS
    
    structure = get_structure()
    result = get_solution(char)
    result.switch_item(structure.get_item_by_id(int(item_name)), slot,
                       get_effective_stat_overrides(char) or None)
    set_solution(char, result)
    remove_cache_for_char(char_id)

    return HttpResponseText('ok')

def remove_item(request, char_id):
    char = get_char_or_raise(request, char_id)
    slot = request.POST.get('slot', None)
    assert slot in SLOTS
    
    result = get_solution(char)
    result.switch_item(None, slot)
    set_solution(char, result)
    remove_cache_for_char(char_id)

    
    return HttpResponseText('ok')

def _get_difference(item, slot, char, stat_overrides=None):
    result = get_solution(char)
    if result is None:
        return []
    current_stats = result.stats_total.copy()
    result.switch_item(item, slot, stat_overrides)
    new_stats = result.stats_total.copy()

    difference = {}
    for (stat, _) in current_stats.items():
        if stat in new_stats:
            if (new_stats[stat] - current_stats[stat] != 0):
                difference[stat] = new_stats[stat] - current_stats[stat]
        else:
            difference[stat] = 0 - current_stats[stat]
    for (stat, _) in new_stats.items():  
        if stat not in current_stats:
            difference[stat] = new_stats[stat]
            
    ordered_diff = sorted(iter(difference.items()),
                          key=lambda x: STAT_ORDER[x[0]])
    
    stats_lines = []
    for stat_key, stat_value in ordered_diff:
        stat_name = get_structure().get_stat_by_key(stat_key).name
        stats_lines.append(AttributeLine(stat_key, stat_value, stat_name))
    return stats_lines

def _get_weapon_rate(weapon, char, result, stat_overrides=None):
    structure = get_structure()
    result_item = result.switch_item(weapon, 'weapon', stat_overrides)
    new_stats = result.stats_total.copy()
    weapon_obj = structure.get_weapon_by_name(weapon.name)
    if weapon_obj is None:
        return 0

    if result_item.is_mageable:
        result_item.mage_weapon_smartly(new_stats)
        element = result_item.element_maged
    else:
        element = NEUTRAL

    calculated_damage = {}
    for elementnew in DAMAGE_TYPES:
        calculated_damage[elementnew] = calculate_damage(weapon_obj.non_crit_hits[element],
                                                         new_stats, critical_hit=False, is_spell=False)
    
    total_damage = 0
    for damage in calculated_damage[element]:
        if damage.heals:
            total_damage -= (damage.min_dam + damage.max_dam)/2
        else:
            total_damage += (damage.min_dam + damage.max_dam)/2
    if weapon_obj.ap == 0:
        rating_non_crit = 0
    else:
        rating_non_crit = total_damage / float(weapon_obj.ap)
    
    
    if weapon_obj.has_crits:
        calculated_crit_damage = {}
        for elementnew in DAMAGE_TYPES:
            calculated_crit_damage[elementnew] = calculate_damage(weapon_obj.crit_hits[element],
                                                             new_stats, critical_hit=True, is_spell=False)
         
        total_damage = 0
        for damage in calculated_crit_damage[element]:
            if damage.heals:
                total_damage -= (damage.min_dam + damage.max_dam)/2
            else:
                total_damage += (damage.min_dam + damage.max_dam)/2
        if weapon_obj.ap == 0:
            rating_crit = 0
        else:
            rating_crit = total_damage / float(weapon_obj.ap)
    
    crits_total = new_stats['ch']
    if weapon_obj.crit_chance_percent:
        crits_total += weapon_obj.crit_chance_percent

    if weapon_obj.has_crits:
        rating = (rating_non_crit * (100 - crits_total) + rating_crit * crits_total)/100
    else:
        rating = rating_non_crit

    return rating if rating > 0 else -rating

def _get_weapon_info(weapon, char, stat_overrides=None):
    weapon_info = {}
    structure = get_structure()
    result = get_solution(char)
    result_item = result.switch_item(weapon, 'weapon', stat_overrides)
    new_stats = result.stats_total.copy()
    weapon_obj = structure.get_weapon_by_name(weapon.name)
    if weapon_obj is None:
        return weapon_info

    if result_item.is_mageable:
        result_item.mage_weapon_smartly(new_stats)
        element = result_item.element_maged
    else:
        element = NEUTRAL

    weapon_info['is_mageable'] = result_item.is_mageable
    weapon_info['element'] = _(ELEMENT_KEY_TO_NAME[element])
        
    calculated_damage = {}
    for elementnew in DAMAGE_TYPES:
        calculated_damage[elementnew] = calculate_damage(weapon_obj.non_crit_hits[element],
                                                         new_stats, critical_hit=False, is_spell=False)
    
    min_noncrit_dam = 0
    for damage in calculated_damage[element]:
        if damage.heals:
            min_noncrit_dam -= damage.min_dam
        else:
            min_noncrit_dam += damage.min_dam
            
    weapon_info['min_noncrit_dam'] = min_noncrit_dam
    
    max_noncrit_dam = 0
    for damage in calculated_damage[element]:
        if damage.heals:
            max_noncrit_dam -= damage.max_dam
        else:
            max_noncrit_dam += damage.max_dam
            
    weapon_info['max_noncrit_dam'] = max_noncrit_dam  
    
    if weapon_obj.has_crits:
    
        calculated_crit_damage = {}
        for elementnew in DAMAGE_TYPES:
            calculated_crit_damage[elementnew] = calculate_damage(weapon_obj.crit_hits[element],
                                                         new_stats, critical_hit=True, is_spell=False)
    
        min_crit_dam = 0
        for damage in calculated_crit_damage[element]:
            if damage.heals:
                min_crit_dam -= damage.min_dam
            else:
                min_crit_dam += damage.min_dam
                
        weapon_info['min_crit_dam'] = min_crit_dam
        
        max_crit_dam = 0
        for damage in calculated_crit_damage[element]:
            if damage.heals:
                max_crit_dam -= damage.max_dam
            else:
                max_crit_dam += damage.max_dam
                
        weapon_info['max_crit_dam'] = max_crit_dam  
    
    
    solution = get_solution(char)
    rating = _get_weapon_rate(weapon, char, solution, stat_overrides)
    weapon_info['rating'] = rating

    return weapon_info
