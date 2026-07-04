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


# Items the optimiser excludes by default: GM-only, event, joke and duplicate items
# nobody wants the solver to pick. Keyed by Ankama item id (stable across versions and
# localisations), with the item name in a trailing comment. Ids absent from the active
# game version are skipped automatically, so a single list covers every version.
DEFAULT_EXCLUSION_ANKAMA_IDS = [
    9031,   # Gore Master's Ring (Gms Only)
    9202,   # Gore Master's Other Ring (Retro)
    6894,   # Ultra-powerful Combat Bow Meow (GM)
    6895,   # Small Combat Bow Meow (GM)
    2155,   # Jiva Necklace
    18853,  # Fiery Tongue Sword
    8575,   # First Blood Staff
    11761,  # Le Divhugalch (unobtainable retro joke staff, +3 AP/+3 MP)
    8854,   # Crack Sparrow's Own Withered Hat
    2154,   # De Sendar's Ring
    27645,  # Basic Broom
    27268,  # Khardboard Goultard
    27282,  # Khardboard Gobball Headgear
    27267,  # Khardboard Dazzling Cloak
    27265,  # Khardboard Celestial Brooch
    27284,  # Khardboard Gelano
    27278,  # Khardboard Getas
    27266,  # Khardboard Moowolf Belt
    27280,  # Khardboard Bowisse's Shield
    6713,   # Lordsoth Daggers
    13063,  # Split Splinter Sprinter
    8422,   # [wip] (Touch work-in-progress placeholder)
    12596,  # [!] WIP (Touch work-in-progress placeholder)
]

# Per-version defaults: items that are in the game data but shouldn't be proposed
# for that specific version (e.g. an item scraped into Touch that Touch players
# can't actually get). Same forbidden-by-default-but-removable behaviour, version
# scoped so the same Ankama id stays available where it is a real item (10076 is a
# genuine Retro shield but does not exist in Dofus Touch).
DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION = {
    'touch': [
        10076,  # Unique Hispanian Shield / Bouclier Hispanique Unique (not in Dofus Touch)
    ],
}

def get_default_exclusions(char):
    s = get_structure()
    ankama_ids = (DEFAULT_EXCLUSION_ANKAMA_IDS
                  + DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get(s.game_version, []))
    item_ids = []
    for ankama_id in ankama_ids:
        item = s.get_item_by_ankama_id(ankama_id)
        if item is not None:
            item_ids.append(item.id)
    return item_ids

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

def get_empty_slots(char):
    if char.empty_slots:
        return pickle.loads(char.empty_slots)
    return []

def set_empty_slot(char, slot, is_empty):
    empty = get_empty_slots(char)
    if is_empty:
        if slot not in empty:
            empty.append(slot)
    else:
        if slot in empty:
            empty.remove(slot)
    char.empty_slots = pickle.dumps(empty)
    char.save()

def get_stat_overrides(char):
    if char.stat_overrides:
        return pickle.loads(char.stat_overrides)
    return {}

def set_item_stat_override(char, item_id, stat_id, value):
    overrides = get_stat_overrides(char)
    if item_id not in overrides:
        overrides[item_id] = {}
    overrides[item_id][stat_id] = value
    char.stat_overrides = pickle.dumps(overrides)
    char.save()

def remove_item_stat_override(char, item_id, stat_id):
    overrides = get_stat_overrides(char)
    if item_id in overrides:
        overrides[item_id].pop(stat_id, None)
        if not overrides[item_id]:
            del overrides[item_id]
    char.stat_overrides = pickle.dumps(overrides)
    char.save()

def clear_item_stat_overrides(char, item_id):
    overrides = get_stat_overrides(char)
    overrides.pop(item_id, None)
    char.stat_overrides = pickle.dumps(overrides)
    char.save()
    