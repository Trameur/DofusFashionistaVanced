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
import re

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
    '(best-element steal)' : '(best-element steal)',
    '(Advances by cell)' : '(Advances by cell)',
    '(Fire heals)' : 'Fire heals',
    'Fertile' : 'Fertile',
}

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']


def sanitize_filename(name):
    name = re.sub(r'[\\/*?:"<>|]', "", name) 
    name = name.replace("[!]", "") # Remove unavailable language tag
    return name.strip()

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
        # If it's a condition (operand), return it as a single-item list
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
    # Start traversal from the root node
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
    name = item['name']

    # Count the occurrences of each name
    if name in name_counts:
        name_counts[name] += 1
        # Update the item name with the count
        item['name'] = f"{name} {name_counts[name]}"
        for eff in item["effects"]:
            if eff["type"]["name"] == '-special spell-':
                print(f"An item need attention! Updated {name} to {item['name']}")
    else:
        name_counts[name] = 1

for item in equipment_data['en']['items']:
    if item.get('ankama_id') in mount_ankama_ids:
        continue
    if 'Certificate' in item['type']['name'] or 'Sidekick' in item['type']['name'] or 'Badge' in item['type']['name'] or '[!] [UNKNOWN_TEXT_ID_0]' in item['name'] or 'Perceptor' in item['type']['name']:
        continue
    transformed_item = {}
    if "ankama_id" in item:
        transformed_item["ankama_id"] = item["ankama_id"]
    transformed_item["ankama_type"] = "equipment"
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
                    sanitized_name = sanitize_filename(original_name)
                    if original_name != sanitized_name:
                        print(f"Modified name for {lang_name_key}: '{original_name}' -> '{sanitized_name}'")
                    transformed_item[lang_name_key] = sanitized_name
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
        transformed_item["stats"] = [
            [
                eff["int_minimum"] if not eff["ignore_int_min"] else None,
                eff["int_maximum"] if not eff["ignore_int_max"] else None,
                f"({eff['type']['name']})" if eff["type"]["is_active"] else eff["type"]["name"]
            ] for eff in item["effects"]
            if not ((eff["type"]["name"] == 'MP' and item["name"] in ["War's Halbaxe", "Wulan's Bow", "Roasty Breadstick", "Pillar of Ephedrya", "Imp Sword", "Phonemenal Scythe"]) or (eff["type"]["id"] == 179) or (eff["type"]["id"] == 238) or (eff["type"]["id"] == 253) or (eff["type"]["id"] == 254))
        ]
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
                # Add the numbering to localized names
                for lang in LANGUAGES:
                    lang_name_key = f"name_{lang}"
                    if lang_name_key in copy_item:
                        copy_item[lang_name_key] += f" {i + 1}"
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

new_data = []

for item in set_data['en']["sets"]:

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