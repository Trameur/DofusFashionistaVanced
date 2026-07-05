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
import logging

from django.views.decorators.http import require_POST
from chardata.util import set_response, safe_int, HttpResponseText, HttpResponseJson
from fashionistapulp.dofus_constants import (ELEMENT_KEY_TO_NAME, ELEMENT_NAME_TO_KEY,
                                             DamageDigest, STAT_ORDER, STAT_KEY_TO_NAME)
from fashionistapulp.item import Item
from fashionistapulp.modify_items_db import (update_item, update_set, delete_item, delete_set,
                                             insert_item, insert_set)
from fashionistapulp.set import Set
from fashionistapulp.structure import get_structure, invalidate_structure
from fashionistapulp.translation import NON_EN_LANGUAGES, LANGUAGES
from fashionistapulp.weapon import Weapon

logger = logging.getLogger(__name__)


def edit_item(request, item_id=None):
    structure = get_structure()
    types_list = structure.get_types_list()
    
    return set_response(request, 
                        'chardata/edit_item.html', 
                        {'types': sorted(types_list),
                         'stats_order': json.dumps(structure.get_stats_list_names_sorted()),
                         'item_id': json.dumps(item_id),
                         'non_en_languages': NON_EN_LANGUAGES,
                         'languages': LANGUAGES})

def edit_set(request):
    structure = get_structure()
    
    return set_response(request, 
                        'chardata/edit_set.html', 
                        {'stats_order': json.dumps(structure.get_stats_list_names_sorted()),
                         'languages': NON_EN_LANGUAGES})

@require_POST
def update_item_post(request):
    item_json = request.POST.get('item', None)
    if item_json is None:
        return HttpResponseText('not ok')
    try:
        item = json.loads(item_json)
    except (ValueError, TypeError):
        return HttpResponseText('not ok')
    if item is None:
        return HttpResponseText('not ok')

    item_id = safe_int(item['id'])
    if item_id:
        new_item, new_weapon = _convert_json_item_to_item(item)
        old_item = get_structure().get_item_by_id(item_id)
        update_item(old_item, new_item, new_weapon, True)
        return HttpResponseText('ok')
    else:
        _insert_item(item)
        return HttpResponseText('ok')

@require_POST
def update_set_post(request):
    set_json = request.POST.get('set', None)
    if set_json is None:
        return HttpResponseText('not ok')
    try:
        s = json.loads(set_json)
    except (ValueError, TypeError):
        return HttpResponseText('not ok')
    if s is None:
        return HttpResponseText('not ok')

    set_id = safe_int(s['id'])
    if set_id:
        new_set = _convert_json_set_to_set(s)
        worked = update_set(set_id, new_set)
        if worked:
            return HttpResponseText('ok')
        else:
            return HttpResponseText('not ok')
    else:
        _insert_set(s)
        return HttpResponseText('ok')

def delete_item_post(request):
    item_id = safe_int(request.POST.get('itemId', None))
    if not item_id:
        return HttpResponseText('not ok')

    worked = _delete_item(item_id)
    if not worked:
        return HttpResponseText('not ok')
        
    return HttpResponseText('ok')

def delete_set_post(request):
    set_id = safe_int(request.POST.get('setId', None))
    if not set_id:
        return HttpResponseText('not ok')

    worked = _delete_set(set_id)
    if not worked:
        return HttpResponseText('not ok')
        
    return HttpResponseText('ok')

def _add_to_old_cond(old_item, stat_id, is_min, value):
    if is_min:    
        old_item.min_stats_to_equip.append((stat_id, value))
    else:    
        old_item.max_stats_to_equip.append((stat_id, value))
    
def _add_to_old_stat(old_item, stat_id, value):
    old_item.stats.append((stat_id, value))

def _add_to_old_extra(old_item, lang, extra):
    old_item.localized_extras.setdefault(lang, []).append(extra)

def edit_item_search_item(request):
    name_piece = request.POST.get('name[term]', None)
    item_list = []
    if name_piece:
        name_piece = name_piece.lower()
        structure = get_structure()
        items = structure.get_concatenated_items_lists()
        for item in items:
            if name_piece in item.name.lower():
                item_list.append('[DT] %d %s' % (item.id, item.name) if item.dofus_touch else '%d %s' % (item.id, item.name))
    return HttpResponseJson(json.dumps(item_list))
    
def edit_item_search_sets(request):
    name_piece = request.POST.get('name[term]', None)
    set_list = []
    if name_piece:
        name_piece = name_piece.lower()
        structure = get_structure()
        sets = structure.get_sets_list() + structure.get_sets_list(True)
        for s in sets:
            if name_piece in s.name.lower():
                set_list.append('[DT] %d %s' % (s.id, s.name) if s.dofus_touch else '%d %s' % (s.id, s.name))
    return HttpResponseJson(json.dumps(set_list))
    
def choose_item(request):
    structure = get_structure()
    
    item_id = safe_int(request.POST.get('id', None))
    item_reference = request.POST.get('name', None)
    item_name = None
    if item_reference:
        if '[DT]' in item_reference:
            item_reference = item_reference.split(' ', 2)
            if item_id == None:
                item_id = safe_int(item_reference[1])
            item_name = item_reference[2]
            dofus_touch = True
        else:
            item_reference = item_reference.split(' ', 1)
            if item_id == None:
                item_id = safe_int(item_reference[0])
            item_name = item_reference[1]
            dofus_touch = False
    
    
    item = None

    if item_id:
        item = structure.get_item_by_id(item_id)
        dofus_touch = item.dofus_touch
        
    if not item and item_name:
        item = structure.get_item_by_name(item_name, dofus_touch)

    if not item:
        return HttpResponseJson(json.dumps({}))
    
    item_stats = {}
    item_stats['name'] = item.name
    item_stats['id'] = item.id
    item_stats['ankama_id'] = item.ankama_id
    item_stats['ankama_type'] = item.ankama_type
    item_stats['level'] = item.level
    item_stats['type'] = structure.get_type_name_by_id(item.type)
    item_stats['removed'] = item.removed
    item_stats['dofus_touch'] = item.dofus_touch
    if item.set:
        item_stats['set'] = structure.get_set_by_id(item.set).name
    
    item_stats['weird_conditions'] = item.weird_conditions
    
    stats = []
    for stat, value in sorted(item.stats, key=lambda stats: STAT_ORDER[structure.get_stat_by_id(stats[0]).key]):
        stats.append((structure.get_stat_by_id(stat).name, value))
    item_stats['stats'] = stats
    
    conditions = {}
    if item.min_stats_to_equip:
        for stat, value in item.min_stats_to_equip:
            conditions[structure.get_stat_by_id(stat).name] = ('>', value - 1)
    if item.max_stats_to_equip:
        for stat, value in item.max_stats_to_equip:
            conditions[structure.get_stat_by_id(stat).name] = ('<', value + 1)
    item_stats['conditions'] = conditions
    
    item_stats['extras'] = {lang: item.localized_extras.get(lang, []) for lang in LANGUAGES}
    
    if item_stats['type'] == 'Weapon':
        weapon = structure.get_weapon_by_name(item.name, dofus_touch)
#        item_stats['one_handed'] = item.is_one_handed
        item_stats['ap'] = weapon.ap
        item_stats['crit_chance'] = weapon.crit_chance
        item_stats['crit_bonus'] = weapon.crit_bonus
        item_stats['weapon_type'] = structure.get_weapon_type_by_id(weapon.weapon_type).name
        hits = {}
        for key, value in weapon.hits_dict.items():
            hits[key] = (value.min_dam, value.max_dam, ELEMENT_KEY_TO_NAME[value.element],
                         value.steals, value.heals)
        item_stats['hits'] = hits
    
    for lang in NON_EN_LANGUAGES:
        item_stats['translated_name_%s' % lang] = item.localized_names.get(lang, '')
    
    or_items = []
    
    # Handle artificial items(Gelano, Turquoise Dofus)
    for alt_item in structure.get_items_by_or_name(item.or_name, dofus_touch):
        if alt_item.id != item.id:
            or_items.append({'id': alt_item.id, 'name': alt_item.name})
    
    result = {'item': item_stats, 'or_items': or_items}
    return HttpResponseJson(json.dumps(result))        

def choose_set(request):
    structure = get_structure()
    set_stats = {}
    
    
    set_id = safe_int(request.POST.get('id', None))
    set_reference = request.POST.get('name', None)
    set_reference = set_reference.split(' ', 1)
    if set_id == None:
        set_id = safe_int(set_reference[0])
    set_name = set_reference[1]
    
    
    s = None
    if set_id:
        s = structure.get_set_by_id(set_id)
        
    if not s and set_name:
        s = structure.get_set_by_name(set_name)

    if not s:
        return HttpResponseJson(json.dumps(set_stats))
    
    set_stats['name'] = s.name
    set_stats['id'] = s.id
    set_stats['ankama_id'] = s.ankama_id
    
    for lang in NON_EN_LANGUAGES:
        set_stats['translated_name_%s' % lang] = s.localized_names.get(lang, '')
    
    stats_per_num_items = {}
    for num_items in range(2, 8 + 1):
        for stat, value in s.bonus_per_num_items.get(num_items, {}).items():
            stats_per_num_items.setdefault(STAT_KEY_TO_NAME[stat], {})[num_items] = value
    stats = []
    for stat_name in sorted(stats_per_num_items,
                            key=lambda stat: STAT_ORDER[structure.get_stat_by_name(stat).key]):
        stats.append((stat_name, stats_per_num_items[stat_name]))
    set_stats['stats'] = stats
    
    items = []
    for item_id in s.items:
        item = structure.get_item_by_id(item_id)
        item_name = item.name
        items.append({'name': item_name, 'id': item_id})
    
    result = {'set': set_stats, 'items': items}
    
    return HttpResponseJson(json.dumps(result))        

def _delete_item(item_id):
    structure = get_structure()
    old_item = structure.get_item_by_id(item_id)
    if old_item is None:
        return False

    delete_item(item_id)
    invalidate_structure()
    return True

def _delete_set(set_id):
    structure = get_structure()
    old_set = structure.get_set_by_id(set_id)
    if old_set is None:
        return False

    delete_set(set_id)
    invalidate_structure()
    return True

def _insert_item(json_item):
    item, weapon = _convert_json_item_to_item(json_item)
    
    insert_item(item, weapon)

    invalidate_structure()

def _insert_set(json_set):
    s = _convert_json_set_to_set(json_set)
    
    insert_set(s)

    invalidate_structure()

def _convert_json_item_to_item(json_item):
    structure = get_structure()

    item = Item()
    item.name = json_item['name']
    item.ankama_id = json_item['ankama_id']
    item.ankama_type = json_item['ankama_type']
    item.level = json_item['level']
    item.removed = json_item['removed']
    item.dofus_touch = json_item['dofus_touch']
    item.type = structure.get_type_id_by_name(json_item['type'])
    if json_item['set']:
        item_set = json_item['set']
        if '[DT]' in item_set:
            set_reference = item_set.split(' ', 2)
            item.set = safe_int(set_reference[1])
        else:
            set_reference = item_set.split(' ', 2)
            item.set = safe_int(set_reference[0])
            logger.debug('%s', item.set)
    
    item.weird_conditions = json_item['weird_conditions']
    
    for stat in json_item['stats']:
        if stat['stat'] == '' or stat['stat'] == None:
            continue
        _add_to_old_stat(item, structure.get_stat_by_name(stat['stat']).id, int(stat['value']))

    for cond in json_item['conditions']:
        if cond['stat'] == '' or cond['stat'] == None:
            continue
        new_value = (int(cond['value']) - 1 if cond['min_max'] == '<' else int(cond['value']) + 1)
        _add_to_old_cond(item, structure.get_stat_by_name(cond['stat']).id, cond['min_max'] == '>', new_value)

    for lang, extras in json_item['extras'].items():
        for extra in extras:
            if extra == '':
                continue
            _add_to_old_extra(item, lang, extra)

    for lang in NON_EN_LANGUAGES:
        name_translated = json_item['translated_name_%s' % lang]
        if not name_translated.startswith('[!]'):
            item.localized_names[lang] = name_translated

    weapon = None    
    if json_item['type'] == 'Weapon':
        weapon = Weapon()
        weapon.ap = int(json_item['ap'])
        weapon.crit_chance = int(json_item['crit_chance'])
        weapon.crit_bonus = int(json_item['crit_bonus'])
#        item.is_one_handed = json_item['one_handed']
        weapon.weapon_type = structure.get_weapon_type_by_name(json_item['weapon_type']).id
        
        for hit in json_item['hits']:
            if hit['min_hit'] == '':
                continue
            index = int(hit['index'])
            
            weapon.hits_dict[index] = DamageDigest(int(hit['min_hit']), 
                                                   int(hit['max_hit']), 
                                                   ELEMENT_NAME_TO_KEY[hit['stat']], 
                                                   hit['steals'],
                                                   hit['heals'])

    return item, weapon

def _convert_json_set_to_set(json_set):
    structure = get_structure()
        
    s = Set()
    s.name = json_set['name']
    s.ankama_id = json_set['ankamaId']
    
    for lang in NON_EN_LANGUAGES:
        name_translated = json_set['translated_name_%s' % lang]
        if not name_translated.startswith('[!]'):
            s.localized_names[lang] = name_translated

    for stat in json_set['stats']:
        stat_name = stat['stat']
        if stat_name == '':
            continue
        
        for num_items, stat_value_string in zip(list(range(2, 8 + 1)), stat['values']):
            if not stat_value_string:
                continue
            stat_id = structure.get_stat_by_name(stat_name).id
            stat_value = int(stat_value_string)
            s.bonus.append((num_items, stat_id, stat_value))

    return s
