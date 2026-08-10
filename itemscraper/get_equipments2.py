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

import argparse
import json
from copy import deepcopy
import os

current_directory = os.path.dirname(os.path.abspath(__file__))

_parser = argparse.ArgumentParser(description="Transform downloaded equipment JSON files")
_parser.add_argument("--work-dir", default=None, help="Directory to read/write JSON files (default: script directory)")
_args = _parser.parse_args()
if _args.work_dir:
    current_directory = os.path.abspath(_args.work_dir)
    os.makedirs(current_directory, exist_ok=True)


STAT_TRANSLATE = {
    '% Power': 'Power',
    'Damage': 'Damage',
    'Heal': 'Heals',
    'AP': 'AP',
    'MP': 'MP',
    '% Critical': 'Critical Hits',
    'Agility': 'Agility',
    'Strength': 'Strength',
    'Neutral Damage': 'Neutral Damage',
    'Earth Damage': 'Earth Damage',
    'Intelligence': 'Intelligence',
    'Fire Damage': 'Fire Damage',
    'Air damage': 'Air Damage',
    'Chance': 'Chance',
    'Water Damage': 'Water Damage',
    'Vitality': 'Vitality',
    'Initiative': 'Initiative',
    'Summons': 'Summon',
    'Range': 'Range',
    'Wisdom': 'Wisdom',
    'Neutral Resistance': 'Neutral Resist',
    'Water Resistance': 'Water Resist',
    'Air Resistance': 'Air Resist',
    'Fire Resistance': 'Fire Resist',
    'Earth Resistance': 'Earth Resist',
    '% Neutral Resistance': '% Neutral Resist',
    '% Air Resistance': '% Air Resist',
    '% Fire Resistance': '% Fire Resist',
    '% Water Resistance': '% Water Resist',
    '% Earth Resistance': '% Earth Resist',
    'Neutral Resistance in PvP': 'Neutral Resist in PVP',
    'Water Resistance in PvP': 'Water Resist in PVP',
    'Air Resistance in PvP': 'Air Resist in PVP',
    'Fire Resistance in PvP': 'Fire Resist in PVP',
    'Earth Resistance in PvP': 'Earth Resist in PVP',
    '% Neutral Resistance in PvP': '% Neutral Resist in PVP',
    '% Air Resistance in PvP': '% Air Resist in PVP',
    '% Fire Resistance in PvP': '% Fire Resist in PVP',
    '% Water Resistance in PvP': '% Water Resist in PVP',
    '% Earth Resistance in PvP': '% Earth Resist in PVP',
    'Prospecting': 'Prospecting',
    'pods': 'Pods',
    'Pod': 'Pods',
    'AP Reduction': 'AP Reduction',
    'MP Reduction': 'MP Reduction',
    'Lock': 'Lock',
    'Dodge': 'Dodge',
    'Reflects': 'Reflects',
    'Reflects ': 'Reflects',
    'Reflects  damage': 'Reflects',
    'reflected Damage': 'Reflects',
    'Pushback Damage': 'Pushback Damage',
    'Trap Damage': 'Trap Damage',
    'Power (traps)': '% Trap Damage',
    'Critical Resistance': 'Critical Resist',
    'Pushback Resistance': 'Pushback Resist',
    'MP Loss Resistance': 'MP Loss Resist',
    'AP Loss Resistance': 'AP Loss Resist',
    'Critical Damage': 'Critical Damage',
    'HP': 'HP',
    'MP Parry': 'MP Loss Resist',
    '% Air Resist in PVP': '% Air Resist in PVP',
    '% Water Resist in PVP': '% Water Resist in PVP',
    'Fire Resist in PVP': 'Fire Resist in PVP',
    '% Melee Resistance': '% Melee Resist',
    '% Ranged Resistance': '% Ranged Resist',
    'AP Parry': 'AP Loss Resist',
    '% Melee Damage': '% Melee Damage',
    '% Ranged Damage': '% Ranged Damage',
    '% Weapon Damage': '% Weapon Damage',
    '% Spell Damage': '% Spell Damage',
    '(Neutral damage)': '(Neutral damage)',
    '(Fire damage)': '(Fire damage)',
    'Hunting weapon': 'Hunting Weapon',
    '(Air damage)': '(Air damage)',
    '(Water damage)': '(Water damage)',
    'Power': 'Power',
    'Exchangeable': 'Exchangeable',
    '-special spell-': '-special spell-',
    'Emote': 'Emote',
    '(Fire steal)': 'Fire Steal',
    '(Earth damage)': '(Earth damage)',
    '(<sprite name="feu"> Fire heals)': 'Fire heals',
    '(Water steal)': '(Water steal)',
    '(Neutral steal)': '(Neutral steal)',
    '/': '/',
    'Linked to the character': 'Linked to the character',
    '(Pushes back cell)': '(Pushes back cell)',
    '(Air steal)': '(Air steal)',
    '(Earth steal)': '(Earth steal)',
    ': line of sight off': ': line of sight off',
    ': - AP': ': - AP',
    ': - cooldown': ': - cooldown',
    ': + Maximum Range': ': + Maximum Range',
    ': - Minimum Range': ': - Minimum Range',
    'Changes speech': 'Changes speech',
    ': + cast(s) per target': ': + cast(s) per target',
    ': +% Critical': ': +% Critical',
    'Exchangeable:' : 'Exchangeable',
    ': straight-line casting off': ': straight-line casting off',
    ': modifiable Range': ': modifiable Range',
    ': + cast(s) per turn': ': + cast(s) per turn',
    ': occupied cell needed off': ': occupied cell needed off',
    ': + Damage': ': + Damage',
    'Changes appearance': 'Changes appearance',
    'Number of victims:' : 'Number of victims:',
    'Title:' : 'Title:',
    '(Steals kamas)': '(Steals kamas)',
    'Someone\'s following you!' : 'Someone\'s following you!',
    ': + base damage': ': + base damage',
    'Add a temporary spell' : 'Add a temporary spell',
    'Cooperative crafting impossible' : 'Cooperative crafting impossible',
    'Received on' : 'Received on',
    'Teleport' : 'Teleport',
    'What\'s inside?' : 'What\'s inside?',
    '(Damage (best element))' : '(Damage (best element))',
    '(Steals MP)' : '(Steals MP)',
    'Max.': 'Max.',
    '(MP)': '(MP)',
    'reflected damage' : 'Reflects',
    '(best-element damage)' : '(best-element damage)',
    'Size: %' : 'Size: %',
    'Action Points (AP)': 'AP',
    'Movement Points (MP)': 'MP',
    '(Attracts by cell)': '(Attracts by cell)',
    '(removes ap)': '(removes ap)',
    '(removes mp)': '(removes mp)',
    '(best-element steal)' : '(best-element steal)',
    '(Advances by cell)' : '(Advances by cell)',
    '(Fire heals)' : 'Fire heals',
    'Fertile' : 'Fertile',
}

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']


# An in-fight effect that takes AP or MP off the target. Its type name is the
# bare characteristic, exactly like the wielder bonus, so the name alone cannot
# tell them apart; is_active can, and the game sets it. The old code keyed on
# dofusdude's effect number instead, and that number is minted per dump: the
# attract line is 255 in Dofus 3 and 253 in the beta, so blocking 253 silently
# cost the beta its five attract weapons while Dofus 3 kept theirs, and the MP a
# weapon removes is 238 here and 192 in Dofus 2, so Dofus 2 needed a hand-written
# list of six item names to patch over the miss.
IN_FIGHT_REMOVAL_HITS = {'AP': '(removes ap)', 'MP': '(removes mp)'}


# A spell hat writes a modifier on one named spell rather than a characteristic:
# "Fracture: +2 Maximum Range", "Reduces the Conquest spell's AP cost by 1". The
# optimizer has no notion of that, so nothing was stored and roughly 500 items
# across the three versions reached their page blank. The source already formats
# the sentence in all five languages, so it is kept as a read line.
# Told apart by shape, not by name or id, both of which drift between dumps: the
# effect puts the SPELL id in int_minimum, ignores int_maximum, and its formatted
# text opens on the spell name where a characteristic opens on its number.
def is_spell_modifier(eff):
    if not eff.get('ignore_int_max') or eff.get('int_maximum'):
        return False
    if (eff.get('int_minimum') or 0) < 1000:
        return False
    text = (eff.get('formatted') or '').strip()
    return bool(text) and not text[0].isdigit()


def effect_row(eff):
    """One stats row, [min, max, description], as get_equipments3 reads them."""
    lo = eff["int_minimum"] if not eff["ignore_int_min"] else None
    hi = eff["int_maximum"] if not eff["ignore_int_max"] else None
    name = eff['type']['name']
    if not eff['type']['is_active']:
        return [lo, hi, name]
    hit = IN_FIGHT_REMOVAL_HITS.get(name)
    if hit is None:
        return [lo, hi, f"({name})"]
    # The source writes the removal as a negative bonus, "-1 AP" or "-3 to -2 AP".
    # The hit already says it is taken off the target, so store how much is taken,
    # 2 to 3, the way the Touch client reports the same line. Left signed, the page
    # read "Removes -1 AP".
    taken = sorted(abs(v) for v in (lo, hi) if v is not None)
    return [taken[0], taken[-1], hit] if taken else [lo, hi, hit]


def clean_display_name(name):
    # Only strip the dofusdude "[!]" unavailable-language tag. Windows-forbidden
    # characters stay in the display name ("Wand Else?", "Plushy-Ball: Tofu");
    # icon filenames are normalized separately (get_equipments4/image_store).
    return name.replace("[!]", "").strip()

def parse_conditions(tree):
    """
    Recursive function to traverse the condition tree
    and return a list of all possible AND conditions.
    this is used to flatten items with multiple conditions.
    I.E : Lassay's Dagger Agility > 250 or Strength > 150
    will be flattened to:
    Lassay's Dagger Agility > 250
    Lassay's Dagger Strength > 150
    Creating a different item for each condition.
    """
    def traverse(node):
        # Dofus 2 atomic condition: {operator, int_value, element} with no tree wrapper
        if isinstance(node, dict) and 'operator' in node and 'is_operand' not in node and 'relation' not in node:
            return [[node]]

        # Dofus 3 operand
        if node.get('is_operand', False):
            return [[node['condition']]]

        # Otherwise, it's a composite node with children
        relation = node['relation']
        children_results = [traverse(child) for child in node['children']]

        if relation == 'and':
            # Flatten all children results with AND logic
            combined = [[]]
            for child_conditions in children_results:
                combined = [x + y for x in combined for y in child_conditions]
            return combined
        elif relation == 'or':
            # Combine all children results with OR logic
            return [item for sublist in children_results for item in sublist]
        else:
            raise ValueError(f"Unsupported relation: {relation}")

    # Dofus 2 ships conditions as a flat list (implicit AND); wrap for traversal.
    if isinstance(tree, list):
        tree = {'is_operand': False, 'relation': 'and', 'children': tree}

    return traverse(tree)

def convert_to_and_conditions(data):
    """Convert a list of conditions to a single AND condition tree.
    Some items conditions are stored as a list and a AND is assumed.
    This function converts the list to a tree structure anyway.
    """
    if isinstance(data, list):
        data = {'is_operand': False, 'relation': 'and', 'children': data}

    result = []
    add = parse_conditions(data)
    result.extend(add)
    return result

    
# Function to load data for each language
def load_data_for_language(lang, data_type):
    path = os.path.join(current_directory, f'all_{data_type}_{lang}.json')
    if not os.path.exists(path):
        return {data_type: []}
    with open(path, 'r', encoding='utf-8') as file:
        return json.load(file)
    
# Load equipment data for all languages
equipment_data = {lang: load_data_for_language(lang, 'equipment') for lang in LANGUAGES}
items_by_ankama_id = {
    lang: {i.get('ankama_id'): i for i in data['items']}
    for lang, data in equipment_data.items()
}

mount_data = {lang: load_data_for_language(lang, 'mounts') for lang in LANGUAGES}

# Keep mount records as source of truth when mounts and equipment share ankama_id.
mount_ankama_ids = {
    item.get('ankama_id')
    for item in mount_data['en'].get('mounts', [])
    if item.get('ankama_id') is not None
}

set_data = {lang: load_data_for_language(lang, 'sets') for lang in LANGUAGES}

# Create a list to store the new formatted items
new_data = []

# Initialize a dictionary to keep track of item name counts
name_counts = {}

# Iterate through the items
for item in equipment_data['en']['items']:
    item_type_name = item.get('type', {}).get('name', '')
    if ('Certificate' in item_type_name or 'Sidekick' in item_type_name or 'Badge' in item_type_name
            or 'Perceptor' in item_type_name or '[!] [UNKNOWN_TEXT_ID_0]' in item.get('name', '')):
        continue
    name = item['name']

    if name in name_counts:
        name_counts[name] += 1
        item['name'] = f"{name} {name_counts[name]}"
        for eff in item["effects"]:
            if eff["type"]["name"] == '-special spell-':
                print(f"An item need attention! Updated {name} to {item['name']}")
    else:
        name_counts[name] = 1

for item in equipment_data['en']['items']:
    if item.get('ankama_id') in mount_ankama_ids:
        continue
    item_type_name = item['type']['name']
    if ('Certificate' in item_type_name or 'Sidekick' in item_type_name or 'Badge' in item_type_name
            or '[!] [UNKNOWN_TEXT_ID_0]' in item['name'] or 'Perceptor' in item_type_name):
        continue
    transformed_item = {}
    if "ankama_id" in item:
        transformed_item["ankama_id"] = item["ankama_id"]
    _MOUNT_TYPE_NAMES = {'Dragoturkey', 'Seemyool', 'Rhineetle', 'Petsmount',
                         'Dragodinde', 'Muldo', 'Volkorne'}
    _is_mount_type = any(t in item_type_name for t in _MOUNT_TYPE_NAMES) or 'Mount' in item_type_name
    transformed_item["ankama_type"] = "mounts" if _is_mount_type else "equipment"
    if "name" in item:
        for lang in LANGUAGES:
            lang_name_key = f"name_{lang}"
            lang_item = next(
                (i for i in equipment_data[lang]['items'] if i['ankama_id'] == item['ankama_id']),
                None
            )
            if lang_item:
                original_name = lang_item['name']
                if lang == "en":
                    cleaned_name = clean_display_name(original_name)
                    if original_name != cleaned_name:
                        print(f"Modified name for {lang_name_key}: '{original_name}' -> '{cleaned_name}'")
                    transformed_item[lang_name_key] = cleaned_name
                else:
                    transformed_item[lang_name_key] = original_name
            else:
                transformed_item[lang_name_key] = None
    if "type" in item:
        transformed_item["w_type"] = item["type"]["name"]
    if "level" in item:
        transformed_item["level"] = item["level"]
    if "dofustouch" in item:
        transformed_item["dofustouch"] = item["dofustouch"]
    if "ap_cost" in item:
        transformed_item["ap"] = item["ap_cost"]
    if "max_cast_per_turn" in item:
        transformed_item["uses_per_turn"] = item["max_cast_per_turn"]
    if "range" in item:
        transformed_item["range"] = [item["range"]["min"], item["range"]["max"]]
    if "critical_hit_probability" in item:
        transformed_item["crit_chance"] = item["critical_hit_probability"]
    if "critical_hit_bonus" in item:
        transformed_item["crit_bonus"] = item["critical_hit_bonus"]
    if "effects" in item:
        transformed_item["stats"] = [effect_row(eff) for eff in item["effects"]]
        for eff in item["effects"]:
            if eff["type"]["name"] == '-special spell-':
                special_spell_effects = [eff for eff in item.get('effects', []) if eff['type']['name'] == '-special spell-']
                for eff in special_spell_effects:
                    # Add special spell descriptions in different languages
                    for lang in LANGUAGES:
                        lang_item = next((i for i in equipment_data[lang]['items'] if i['ankama_id'] == item['ankama_id']), None)
                        if lang_item:
                            lang_special_spell = next((e['formatted'] for e in lang_item.get('effects', []) if e['type']['name'] == '-special spell-'), None)
                            if lang_special_spell:
                                transformed_item[f"special_spell_{lang}"] = lang_special_spell

        if any(is_spell_modifier(eff) for eff in item["effects"]):
            for lang in LANGUAGES:
                lang_item = items_by_ankama_id[lang].get(item.get('ankama_id'))
                if lang_item is None:
                    continue
                lines = [e['formatted'].strip()
                         for e in (lang_item.get('effects') or [])
                         if is_spell_modifier(e)]
                if not lines:
                    continue
                key = f"special_spell_{lang}"
                if transformed_item.get(key):
                    lines.insert(0, transformed_item[key])
                transformed_item[key] = '\n'.join(lines)
    else:
        transformed_item["stats"] = []
   
    if "image_urls" in item:
        transformed_item["image_url"] = item["image_urls"]["sd"]
    transformed_item["dofustouch"] = False
    # Conditions treatment moved to the end to copy the item and add the condition to the new item
    if "conditions" in item:
        transformed_item["has_conditions"] = bool(item["conditions"])
        flattened_or_conditions = parse_conditions(item["conditions"])
        if len(flattened_or_conditions) == 0:
            raise ValueError("Invalid parsing of conditions detected")
        # An item is created per OR condition
        if len(flattened_or_conditions) > 1:
            for i, conditions in enumerate(flattened_or_conditions):
                copy_item = deepcopy(transformed_item)
                # "(#1)" and not " 1": structure.py groups the branches of one
                # item on that exact tag and shows the plain name to the player.
                for lang in LANGUAGES:
                    lang_name_key = f"name_{lang}"
                    if lang_name_key in copy_item:
                        copy_item[lang_name_key] += f" (#{i + 1})"
                copy_item["conditions"] = [f"{STAT_TRANSLATE.get(cond['element']['name'], cond['element']['name'])} {cond['operator']} {cond['int_value']}" for cond in conditions]
                new_data.append(copy_item)
        else:
            transformed_item["conditions"] = [f"{STAT_TRANSLATE.get(cond['element']['name'], cond['element']['name'])} {cond['operator']} {cond['int_value']}" for cond in flattened_or_conditions[0]]
            new_data.append(transformed_item)
    else:
        # Ensure "conditions" key exists with an empty list
        transformed_item["conditions"] = []     
        new_data.append(transformed_item)

for item in mount_data['en']['mounts']:
    transformed_item = {}
    transformed_item["dofustouch"] = False
    if "ankama_id" in item:
        transformed_item["ankama_id"] = item["ankama_id"]
    transformed_item["ankama_type"] = "mounts"
    if "name" in item:
        for lang in LANGUAGES:
            lang_name_key = f"name_{lang}"
            lang_item = next((i for i in mount_data[lang]['mounts'] if i['ankama_id'] == item['ankama_id']), None)
            transformed_item[lang_name_key] = lang_item['name'] if lang_item else None
    transformed_item["w_type"] = "Pet"
    transformed_item["level"] = 60
    if "dofustouch" in item:
        transformed_item["dofustouch"] = item["dofustouch"]
    if "conditions" in item:
        transformed_item["conditions"] = [f"{cond['element']['name']} {cond['operator']} {cond['int_value']}" for cond in item["conditions"]]
    if "effects" in item:
        transformed_item["stats"] = [
            [
                eff["int_minimum"] if not eff["ignore_int_min"] else None,
                eff["int_maximum"] if not eff["ignore_int_max"] else None,
                eff["type"]["name"]
            ] for eff in item["effects"]
        ]
    else:
        transformed_item["stats"] = []
    if "conditions" in item:
        transformed_item["has_conditions"] = bool(item["conditions"])
    if "image_urls" in item:
        transformed_item["image_url"] = item["image_urls"]["sd"]

    new_data.append(transformed_item)

missing_translation = []

for item in new_data:
    if "stats" in item:
        for stat in item["stats"]:
            original_stat_name = stat[-1]  # The original name is the last element in the stat list
            translated_stat_name = STAT_TRANSLATE.get(original_stat_name, original_stat_name)  # Translate or keep as-is
            if original_stat_name not in STAT_TRANSLATE:
                if original_stat_name not in missing_translation:
                    missing_translation.append(original_stat_name)
                    print(f"Missing translation for: '{original_stat_name}'")
            stat[-1] = translated_stat_name  # Update the name in the stat list

# Write the new JSON file
with open(f'{current_directory}/transformed_equipment.json', 'w', encoding='utf-8') as f:
    json.dump(new_data, f, ensure_ascii=False, indent=4)

def _normalize_set_effects(effects):
    """Dofus 2 ships set effects as a list-of-lists (one sublist per N-piece
    bonus, each effect carrying its own ``item_combination``). Dofus 3 uses a
    dict keyed by piece count. Normalize to the dict shape so downstream code
    works for both versions."""
    if not isinstance(effects, list):
        return effects
    by_combo = {}
    for idx, effect_group in enumerate(effects):
        if not effect_group:
            continue
        combo = next(
            (e.get('item_combination') for e in effect_group if isinstance(e, dict) and 'item_combination' in e),
            None,
        )
        key = str(combo) if combo is not None else str(idx + 2)
        by_combo[key] = effect_group
    return by_combo


new_data = []

for item in set_data['en']["sets"]:

    if "effects" in item:
        item["effects"] = _normalize_set_effects(item["effects"])

    # Translate `effects` names
    if "effects" in item:
        for effect_key, effect_group in item["effects"].items():  # Iterate over key-value pairs
            if effect_group is None:
                continue  # Skip if the value is null
            for effect in effect_group:  # Iterate over each effect in the group
                if "type" in effect and "name" in effect["type"]:
                    original_type_name = effect["type"]["name"]
                    translated_type_name = STAT_TRANSLATE.get(original_type_name, original_type_name)
                    if original_type_name not in STAT_TRANSLATE:
                        if original_type_name not in missing_translation:
                            missing_translation.append(original_type_name)
                            print(f"Missing translation for: '{original_type_name}'")
                    effect["type"]["name"] = translated_type_name  # Update the name

    transformed_item = {}
    if "ankama_id" in item:
        transformed_item["ankama_id"] = item["ankama_id"]
    if "name" in item:
        for lang in LANGUAGES:
            lang_name_key = f"name_{lang}"
            lang_item = next((i for i in set_data[lang]['sets'] if i['ankama_id'] == item['ankama_id']), None)
            transformed_item[lang_name_key] = lang_item['name'] if lang_item else None
    if "items" in item:
        transformed_item["items"] = item["items"]
    if "effects" in item:
        transformed_item["stats_list"] = []
        for effect_key, effect_value in item.get("effects", {}).items():
            if effect_value is None:
                continue
            stats_entry = {
                "effect_key": effect_key,
                "effects": [
                    [
                        eff.get("int_minimum", None) if not eff.get("ignore_int_min", False) else None,
                        eff.get("int_maximum", None) if not eff.get("ignore_int_max", False) else None,
                        eff.get("type", {}).get("name", "")
                    ] for eff in effect_value
                ]
            }
            transformed_item["stats_list"].append(stats_entry)
    if "equipment_ids" in item:
        transformed_item["equipment_ids"] = item["equipment_ids"]

    new_data.append(transformed_item)            

# Write the new JSON file
with open(f'{current_directory}/transformed_sets.json', 'w', encoding='utf-8') as f:
    json.dump(new_data, f, ensure_ascii=False, indent=4)