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

import pickle

from fashionistapulp.dofus_constants import SLOTS
from fashionistapulp.structure import get_structure


DEFAULT_EXCLUSIONS_121_PLUS = ['Gore Master\'s Ring (Gms Only)',
                               'Ultra-powerful Combat Bow Meow (GM)',
                               'Small Combat Bow Meow (GM)',
                               'Jiva Necklace',
                               'Fiery Tongue Sword',
                               'First Blood Staff',
                               'Crack Sparrow\'s Own Withered Hat',
                               'De Sendar\'s Ring',
                               'Basic Broom',
                               'Khardboard Goultard',
                               'Khardboard Gobball Headgear',
                               'Khardboard Dazzling Cloak',
                               'Khardboard Celestial Brooch',
                               'Khardboard Gelano',
                               'Khardboard Getas',
                               'Khardboard Moowolf Belt',
                               'Khardboard Bowisse\'s Shield',
                               'Lordsoth Daggers',
                               'Split Splinter Sprinter',
                               'Wild Crimson Seemyool',
                               'Wild Ebony Seemyool',
                               'Wild Indigo Seemyool',
                               'Wild Orchid Seemyool',
                               ]
DEFAULT_EXCLUSIONS_120_MINUS = (DEFAULT_EXCLUSIONS_121_PLUS
                                + [])

def get_default_exclusions(char):
    if char.level > 120:
        return DEFAULT_EXCLUSIONS_121_PLUS
    else:
        return DEFAULT_EXCLUSIONS_120_MINUS

def set_exclusions_list_and_check_inclusions(char, excluded_items):
    assert type(excluded_items) == list
    for item in excluded_items:
        assert type(item) == int
    _remove_inclusions_by_id(char, excluded_items)
    _save_exclusion_list(char, excluded_items)

def set_inclusions_dict_and_check_exclusions(char, inclusions_dict):
    remove_from_exclusion = []
    for slot in SLOTS:
        included_item = inclusions_dict.get(slot, None)
        if included_item:
            remove_from_exclusion.append(int(included_item))
    remove_items_from_exclusions(char, remove_from_exclusion)
    _save_inclusion_dict(char, inclusions_dict)

def get_all_inclusions_en_names(char):
    item_dict = get_inclusions_dict(char)
    return {key: _item_id_to_local_or_name(value, 'en')
            for key, value in list(item_dict.items())}

def get_inclusions_dict(char):
    inclusions = {}
    if char.inclusions:
        inclusions = pickle.loads(char.inclusions)
    return inclusions

def set_exclusions_list_by_name(char, excluded_items):
    s = get_structure()

    items = []
    for item_name in excluded_items:
        item = s.get_item_by_name(item_name)
        if item is None:
            result = s.get_or_item_by_name(item_name)
            if result:
                item = result[0]
            else:
                print('Item %s does not exist and cannot be excluded' % item_name)

        if item is not None:
            item_id = item.id
            items.append(item_id)
        else:
            print('Item %s does not exist and cannot be excluded' % item_name)
    set_exclusions_list_and_check_inclusions(char, items)
    
def remove_invalid_inclusions(char, level):
    structure = get_structure()
    inclusions = get_inclusions_dict(char)
    for item_type, equip in inclusions.items():
        if equip != '':
            item = structure.get_item_by_id(equip)
            if item is None or item.level > level:
                inclusions[item_type] = ''

    _save_inclusion_dict(char, inclusions)

def set_item_included(char, item_id, slot, included):
    inclusions = get_inclusions_dict(char)
    
    if included:
        inclusions[slot] = item_id
        set_excluded(char, item_id, False)
    else:
        if inclusions.get(slot, '') == item_id:
            inclusions[slot] = ''

    _save_inclusion_dict(char, inclusions)

def get_all_exclusions_with_names(char, language):
    item_list = []
    for item_id in _get_all_exclusions(char):
        item = {'id':  item_id,
                'name': _item_id_to_local_or_name(int(item_id), language)}
        item_list.append(item)
    return item_list

def get_all_exclusions_ids(char):
    return _get_all_exclusions(char)

def get_all_exclusions_en_names(char):
    return [_item_id_to_local_or_name(int(item_id), 'en')
            for item_id in _get_all_exclusions(char)]

def set_excluded(char, item_id, forbidden):
    item_ids = [int(item_id)]
    if forbidden:
        add_items_to_exclusions(char, item_ids)
    else:
        remove_items_from_exclusions(char, item_ids)
   
def _item_id_to_local_or_name(item_id, language):
    structure = get_structure()
    item = structure.get_item_by_id(item_id)

    if item is None:
        # Legacy pickles can reference retired items; fall back to any variant we still know
        for candidate in structure.get_items_by_or_id(item_id):
            if candidate is not None:
                item = candidate
                break

    if item is None:
        return f"Unknown item #{item_id}"

    localized_names = getattr(item, 'localized_names', {}) or {}
    if language in localized_names:
        return localized_names[language]

    if 'en' in localized_names:
        return localized_names['en']

    # Last resort: return first available localization or name/id to avoid crashing the UI
    if localized_names:
        return next(iter(localized_names.values()))
    if getattr(item, 'name', None):
        return item.name

    return str(item_id)

def _save_inclusion_dict(char, inclusions):
    inclusions = {slot: int(value)
                  for slot, value in list(inclusions.items()) if value != ''}
    char.inclusions = pickle.dumps(inclusions)
    char.save()

def _remove_inclusions_by_id(char, item_ids):
    inclusions = get_inclusions_dict(char)

    changed = False
    for slot in SLOTS:
        if inclusions.get(slot, '') in item_ids:
            inclusions[slot] = ''
            changed = True
    
    if changed:
        _save_inclusion_dict(char, inclusions)

def _save_exclusion_list(char, excluded_items):
    char.exclusions = pickle.dumps(excluded_items)
    char.save()

def _get_all_exclusions(char):
    exclusions = []
    if char.exclusions:
        exclusions = pickle.loads(char.exclusions)
    return exclusions

def add_items_to_exclusions(char, item_ids):
    exclusions = get_all_exclusions_ids(char)
    
    changed = False
    for item_id in item_ids:
        if item_id not in exclusions:
            exclusions.append(item_id)
            changed = True

    if changed:
        set_exclusions_list_and_check_inclusions(char, exclusions)

def remove_items_from_exclusions(char, item_ids):
    exclusions = get_all_exclusions_ids(char)
    
    changed = False
    for item_id in item_ids:
        if item_id in exclusions:
            exclusions.remove(item_id)
            changed = True

    if changed:
        _save_exclusion_list(char, exclusions)
    