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
import pickle
import os
import sys

current_directory = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_directory)
sys.path.append(project_root)

_parser = argparse.ArgumentParser(description="Build SQLite dump from transformed equipment JSON")
_parser.add_argument("--dump-output", default=None, help="Output path for the dump file (default: item_db_dumped.dump)")
_parser.add_argument("--input-dir", default=None, help="Directory containing transformed_equipment.json and transformed_sets.json (default: script directory)")
_args = _parser.parse_args()

_default_dump = os.path.join(current_directory, '..', 'fashionistapulp', 'fashionistapulp', 'item_db_dumped.dump')
dump_output_path = _args.dump_output if _args.dump_output else _default_dump
input_dir = os.path.abspath(_args.input_dir) if _args.input_dir else current_directory

from fashionistapulp.fashionistapulp.dofus_constants import (
    STAT_NAME_TO_KEY,
    STAT_ORDER,
    TYPE_NAME_TO_SLOT
)
#current_directory = os.path.dirname(__file__)

LANGUAGES = ['en', 'fr', 'es', 'pt', 'de']

# Mounts and equipment share ankama_ids, so we offset mount IDs
# Duplicate items (same ankama_id, different conditions) also need offsets
MOUNT_ID_OFFSET = 1000000
DUPLICATE_ID_OFFSET = 100000000

# Track ankama_id occurrences to handle duplicates
ankama_id_counter = {}

def get_item_id(item):
    """Get the database ID for an item, accounting for mount and duplicate offsets"""
    ankama_id = item['ankama_id']
    
    # Track duplicates
    if ankama_id not in ankama_id_counter:
        ankama_id_counter[ankama_id] = 0
    else:
        ankama_id_counter[ankama_id] += 1
    
    # Calculate ID
    if item.get('ankama_type') == 'mounts':
        new_id = MOUNT_ID_OFFSET + ankama_id
        if ankama_id_counter[ankama_id] > 0:
            new_id += DUPLICATE_ID_OFFSET * ankama_id_counter[ankama_id]
    else:
        new_id = ankama_id
        if ankama_id_counter[ankama_id] > 0:
            new_id += DUPLICATE_ID_OFFSET * ankama_id_counter[ankama_id]
    
    return new_id

WEAPON_TYPES = {
    'Hammer': 'hammer',
    'Axe': 'axe',
    'Shovel': 'shovel',
    'Staff': 'staff',
    'Sword': 'sword',
    'Dagger': 'dagger',
    'Bow': 'bow',
    'Wand': 'wand',
    'Pickaxe': 'pickaxe',
    'Scythe': 'scythe',
    'Lance': 'lance',
}

STAT_NAME_TO_KEY_LOCAL = {
    'Power': 'pow',
    'Damage': 'dam',
    'Heals': 'heals',
    'AP': 'ap',
    'MP': 'mp',
    'Critical Hits': 'ch',
    'Agility': 'agi',
    'Strength': 'str',
    'Neutral Damage': 'neutdam',
    'Earth Damage': 'earthdam',
    'Intelligence': 'int',
    'Fire Damage': 'firedam',
    'Air Damage': 'airdam',
    'Chance': 'cha',
    'Water Damage': 'waterdam',
    'Vitality': 'vit',
    'Initiative': 'init',
    'Summon': 'summon',
    'Range': 'range',
    'Wisdom': 'wis',
    'Neutral Resist': 'neutres',
    'Water Resist': 'waterres',
    'Air Resist': 'airres',
    'Fire Resist': 'fireres',
    'Earth Resist': 'earthres',
    '% Neutral Resist': 'neutresper',
    '% Air Resist': 'airresper',
    '% Fire Resist': 'fireresper',
    '% Water Resist': 'waterresper',
    '% Earth Resist': 'earthresper',
    'Neutral Resist in PVP': 'pvpneutres',
    'Water Resist in PVP': 'pvpwaterres',
    'Air Resist in PVP': 'pvpairres',
    'Fire Resist in PVP': 'pvpfireres',
    'Earth Resist in PVP': 'pvpearthres',
    '% Neutral Resist in PVP': 'pvpneutresper',
    '% Air Resist in PVP': 'pvpairresper',
    '% Fire Resist in PVP': 'pvpfireresper',
    '% Water Resist in PVP': 'pvpwaterresper',
    '% Earth Resist in PVP': 'pvpearthresper',
    'Prospecting': 'pp',
    'Pods': 'pod',
    'AP Reduction': 'apred',
    'MP Reduction': 'mpred',
    'Lock': 'lock',
    'Dodge': 'dodge',
    'Reflects': 'ref',
    'Pushback Damage': 'pshdam',
    'Trap Damage': 'trapdam',
    '% Trap Damage': 'trapdamper',
    'Critical Resist': 'crires',
    'Pushback Resist': 'pshres',
    'MP Loss Resist': 'mpres',
    'AP Loss Resist': 'apres',
    'Critical Damage': 'cridam',
    'Critical Failure': 'cf',
    '% Melee Damage': 'permedam',
    '% Ranged Damage': 'perrandam',
    '% Weapon Damage': 'perweadam',
    '% Spell Damage': 'perspedam',
    '% Melee Resist': 'respermee',
    '% Ranged Resist': 'resperran',
    'HP': 'hp',
    '% Weapon Resist': 'resperwea'
}

def escape_single_quotes(s):
    return s.replace("'", "''")

# Read the original JSON file
with open(os.path.join(input_dir, 'transformed_equipment.json'), 'r', encoding='utf-8') as f:
    original_data = json.load(f)

with open(os.path.join(input_dir, 'transformed_sets.json'), 'r', encoding='utf-8') as f:
    original_sets = json.load(f)

# Open the .dump file for writing
with open(dump_output_path, 'w', encoding='utf-8') as f:
    # Write initial SQL commands
    f.write("PRAGMA foreign_keys=OFF;\nBEGIN TRANSACTION;\nCREATE TABLE item_types\n             (id INTEGER PRIMARY KEY AUTOINCREMENT, name text);\n")

    # Write item_types INSERT commands
    for index, item in enumerate(TYPE_NAME_TO_SLOT, start=1):
        f.write(f"INSERT INTO item_types VALUES ({index},'{item}');\n")

    # Write CREATE TABLE for stats
    f.write("CREATE TABLE stats\n             (id INTEGER PRIMARY KEY AUTOINCREMENT, name text,\n             key text);\n")

    # Write stats INSERT commands
    for index, item in enumerate(STAT_NAME_TO_KEY_LOCAL, start=1):
        f.write(f"INSERT INTO stats VALUES({index},'{item}','{STAT_NAME_TO_KEY_LOCAL[item]}');\n")

    # Write CREATE TABLE for stats_of_items
    #f.write("CREATE TABLE stats_of_items\n             (item INTEGER, stat INTEGER, value INTEGER,\n             FOREIGN KEY(item) REFERENCES items(id),\n             FOREIGN KEY(stat) REFERENCES stats(id));\n")

    # Write CREATE TABLE for sets
    f.write("""CREATE TABLE "sets" (
	    `id`	INTEGER PRIMARY KEY,
	    `name`	text,
	    `ankama_id`	INTEGER,
	    `dofustouch`	INTEGER
    );\n""")

    #INSERT INTO sets VALUES(1,'Pink Piwi Set',70,NULL);

    for item in original_sets:
        set_id = item['ankama_id']
        f.write(f"INSERT INTO sets VALUES({set_id},'{escape_single_quotes(item['name_en'])}',{item['ankama_id']},NULL);\n")

    # Write CREATE TABLE for items
    f.write("""CREATE TABLE "items" (
        `id` INTEGER PRIMARY KEY,
        `name` text,
        `level` INTEGER,
        `type` INTEGER,
        `item_set` INTEGER,
        `ankama_id` INTEGER,
        `ankama_type` text,
        `removed` INTEGER,
        `dofustouch` INTEGER,
        FOREIGN KEY(`type`) REFERENCES item_types (id),
        FOREIGN KEY(`item_set`) REFERENCES sets (id)
    );\n""")

    #INSERT INTO items VALUES(6854,'Leurnettes',12,1,NULL,340,'equipment',0,1);
    
    # Dictionary to store item_id for each item (to reuse when writing stats)
    item_to_id = {}
    
    for item in original_data:
        # Write INSERT command for items
        if item['w_type'] == 'Trophy':
            item['w_type'] = 'Dofus'
            item['is_trophy'] = True
        if item['w_type'] == 'Prysmaradite':
            item['w_type'] = 'Dofus'
            item['is_prysmaradite'] = True
        if item['w_type'] == 'Backpack':
            item['w_type'] = 'Cloak'
        _MOUNT_SUBTYPES = ('Petsmount', 'Dragoturkey', 'Seemyool', 'Rhineetle',
                           'Dragodinde', 'Muldo', 'Volkorne', 'Mount')
        if any(t in item.get('w_type', '') for t in _MOUNT_SUBTYPES):
            item['w_type'] = 'Pet'

        if item['w_type'] not in TYPE_NAME_TO_SLOT and item['w_type'] != '':
            item['weapon_type'] = item['w_type']
            item['w_type'] = 'Weapon'
        
        if item['w_type'] == '':
            item['w_type'] = 'Dofus'

        set_id = None
        
        for set_item in original_sets:
            if item['ankama_id'] in set_item['equipment_ids']:
                set_id = set_item['ankama_id']  # Using the set's ankama_id
                break

        # Use 'NULL' if set_id is None, otherwise use the set_id
        set_id_or_null = 'NULL' if set_id is None else set_id
        # Use ankama_id as the primary key (id), with offset for mounts
        item_id = get_item_id(item)
        # Store the item_id for later use in stats
        item_to_id[id(item)] = item_id
        f.write(f"INSERT INTO items VALUES({item_id},'{escape_single_quotes(item['name_en'])}',{item['level']},{list(TYPE_NAME_TO_SLOT.values()).index(item['w_type'].lower()) + 1},{set_id_or_null},{item['ankama_id']},'{item['ankama_type']}',NULL,NULL);\n")

    # Write CREATE TABLE for stats_of_items
    f.write("""CREATE TABLE stats_of_item
            (item INTEGER, stat INTEGER, value INTEGER,
            FOREIGN KEY(item) REFERENCES items(id),
            FOREIGN KEY(stat) REFERENCES stats(id));\n""")

    # Track skipped stats
    skipped_stats = []
    # Write INSERT commands for stats_of_items
    for item in original_data:
        # Reuse the item_id that was calculated during item insertion
        item_id = item_to_id[id(item)]
        for stat in item['stats']:
            if stat[2] not in STAT_NAME_TO_KEY_LOCAL:
                if stat[2] not in skipped_stats:
                    print(f"Skipping {stat[2]}")
                    skipped_stats.append(stat[2])
                continue
            stat_value = stat[1] if stat[1] is not None else stat[0]
            stat_value = stat[0] if stat[0] < 0 else stat_value
            f.write(f"INSERT INTO stats_of_item VALUES({item_id},{list(STAT_NAME_TO_KEY_LOCAL).index(stat[2]) + 1},{stat_value});\n")

    # Write CREATE TABLE for set_bonus
    f.write("""CREATE TABLE set_bonus
             (item_set INTEGER, num_pieces_used INTEGER, stat INTEGER, value INTEGER,
              FOREIGN KEY(item_set) REFERENCES sets(id),
              FOREIGN KEY(stat) REFERENCES stats(id));\n""")
    
    # Write INSERT commands for set_bonus
    for set_data in original_sets:
        set_id = set_data['ankama_id']
        if 'stats_list' in set_data:
            for effect_data in set_data['stats_list']:
                effect_key = int(effect_data['effect_key'])  # Number of pieces used
                for bonus in effect_data['effects']:
                    if bonus[2] not in STAT_NAME_TO_KEY_LOCAL:
                        if bonus[2] not in skipped_stats:
                            print(f"Skipping {bonus[2]}") # Skip unknown stats, Title, Emote or Pet mostly
                            skipped_stats.append(bonus[2])
                        continue
                    f.write(f"INSERT INTO set_bonus VALUES({set_id},{effect_key},{list(STAT_NAME_TO_KEY_LOCAL).index(bonus[2]) + 1},{bonus[0]});\n")

    # Dofus 3 internal characteristic IDs used inside "Max." set effects
    MAX_EFFECT_CHAR_ID_TO_STAT_NAME = {
        19: 'Summon',
        23: 'MP',
        26: 'Range',
    }

    # Write CREATE TABLE for set_max_caps
    f.write("""CREATE TABLE set_max_caps
             (item_set INTEGER, num_pieces_used INTEGER, stat INTEGER, max_value INTEGER,
              FOREIGN KEY(item_set) REFERENCES sets(id),
              FOREIGN KEY(stat) REFERENCES stats(id));\n""")

    for set_data in original_sets:
        set_id = set_data['ankama_id']
        if 'stats_list' in set_data:
            for effect_data in set_data['stats_list']:
                effect_key = int(effect_data['effect_key'])
                for bonus in effect_data['effects']:
                    char_id, max_value, stat_name = bonus
                    if stat_name != 'Max.' or max_value is None:
                        continue
                    mapped = MAX_EFFECT_CHAR_ID_TO_STAT_NAME.get(char_id)
                    if mapped is None:
                        continue
                    stat_index = list(STAT_NAME_TO_KEY_LOCAL).index(mapped) + 1
                    f.write(f"INSERT INTO set_max_caps VALUES({set_id},{effect_key},{stat_index},{max_value});\n")

    # Write CREATE TABLE for min_stat_to_equip
    f.write("""CREATE TABLE min_stat_to_equip
             (item INTEGER, stat INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id),
              FOREIGN KEY(stat) REFERENCES stats(id));\n""")
    
    # Write INSERT commands for min_stat_to_equip
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'conditions' in item:
            for condition_string in item['conditions']:
                parts = condition_string.split(' ')  # Split the string by spaces
                if len(parts) > 3:  # Some stat names have multiple words like "Alignment Level > 20"
                    joined_name = " ".join(parts[:-2])
                    parts = [joined_name, parts[-2], parts[-1]]
                if len(parts) == 3 and parts[0] in STAT_NAME_TO_KEY_LOCAL:
                    stat_name = parts[0]  # The stat name, e.g., "Strength"
                    operator = parts[1]  # The operator, e.g., ">"
                    stat_value = parts[2]  # The value, e.g., "34"
                    stat_index = list(STAT_NAME_TO_KEY_LOCAL).index(stat_name) + 1
                    if operator == '>':
                        f.write(f"INSERT INTO min_stat_to_equip VALUES({item_id},{stat_index},{int(stat_value)+1});\n")

    # Write CREATE TABLE for max_stat_to_equip
    f.write("""CREATE TABLE max_stat_to_equip
             (item INTEGER, stat INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id),
              FOREIGN KEY(stat) REFERENCES stats(id));\n""")
    
    # Write INSERT commands for max_stat_to_equip
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'conditions' in item:
            for condition_string in item['conditions']:
                parts = condition_string.split(' ')  # Split the string by spaces
                if len(parts) == 3 and parts[0] in STAT_NAME_TO_KEY_LOCAL:
                    stat_name = parts[0]  # The stat name, e.g., "Strength"
                    operator = parts[1]
                    stat_value = parts[2]  # The value, e.g., "34"
                    stat_index = list(STAT_NAME_TO_KEY_LOCAL).index(stat_name) + 1
                    if operator == '<':
                        f.write(f"INSERT INTO max_stat_to_equip VALUES({item_id},{stat_index},{int(stat_value)-1});\n")

    # Write CREATE TABLE for min_rank_to_equip
    f.write("""CREATE TABLE min_rank_to_equip
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    f.write("""CREATE TABLE min_align_level_to_equip
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    f.write("""CREATE TABLE min_prof_level_to_equip
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    f.write("""CREATE TABLE weapon_is_onehanded
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    f.write("""CREATE TABLE weapon_crit_hits
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'crit_chance' in item:
            f.write(f"INSERT INTO weapon_crit_hits VALUES({item_id},{item['crit_chance']});\n")

    f.write("""CREATE TABLE weapon_crit_bonus
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'crit_bonus' in item:
            f.write(f"INSERT INTO weapon_crit_bonus VALUES({item_id},{item['crit_bonus']});\n")

    f.write("""CREATE TABLE weapon_ap
             (item INTEGER, value INTEGER,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'ap' in item:
            f.write(f"INSERT INTO weapon_ap VALUES({item_id},{item['ap']});\n")

    f.write("""CREATE TABLE weapontype
             (id INTEGER PRIMARY KEY AUTOINCREMENT, name text, key text);\n""")
    
    for index, item in enumerate(WEAPON_TYPES, start=1):
        f.write(f"INSERT INTO weapontype VALUES({index},'{item}','{WEAPON_TYPES[item]}');\n")

    f.write("""CREATE TABLE weapon_weapontype
             (item INTEGER, weapontype INTEGER,
              FOREIGN KEY(item) REFERENCES items(id),
              FOREIGN KEY(weapontype) REFERENCES weapontype(id));\n""")
    
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'weapon_type' in item:
            if item['weapon_type'] in WEAPON_TYPES:
                f.write(f"INSERT INTO weapon_weapontype VALUES({item_id},{list(WEAPON_TYPES).index(item['weapon_type']) + 1});\n")

    f.write("""CREATE TABLE weapon_hits
             (item INTEGER, hit INTEGER, min_value INTEGER, max_value INTEGER, steals INTEGER,
              heals INTEGER, element text,
              FOREIGN KEY(item) REFERENCES items(id));\n""")
    
    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'stats' in item:
            i = 0
            for stat in item['stats']:
                # Extract values and description
                min_value, max_value, description = stat

                if max_value is None:
                    max_value = min_value

                # Parse weapon hit lines, handling "(Fire heals)", "((Fire damage))"
                # (the dofus2 source double-wraps hit lines) and legacy "Fire Steal".
                normalized_description = description.strip()
                is_parenthesized_hit = (
                    normalized_description.startswith("(")
                    and normalized_description.endswith(")")
                )
                # Strip every surrounding parenthesis layer (single or double).
                while (normalized_description.startswith("(")
                       and normalized_description.endswith(")")):
                    normalized_description = normalized_description[1:-1].strip()

                parts = normalized_description.lower().split()
                # "Best Element" arrives as two words; the element set uses "best-element".
                if len(parts) >= 2 and parts[0] == 'best' and parts[1] == 'element':
                    parts = ['best-element'] + parts[2:]
                if len(parts) >= 2:
                    element = parts[0]
                    damage_type = parts[1]

                    if element in {'neutral', 'earth', 'fire', 'water', 'air', 'best-element'} and damage_type in {'damage', 'steal', 'steals', 'heal', 'heals', 'healing'}:
                        # Plain labels like "Fire Damage" are stats and must not become hit lines.
                        # Keep plain parsing only for legacy steal/heal labels (e.g. "Fire Steal").
                        if not is_parenthesized_hit and damage_type == 'damage':
                            continue

                        steals = 0
                        heals = 0

                        if damage_type in {'steal', 'steals'}:
                            steals = 1
                        elif damage_type in {'heal', 'heals', 'healing'}:
                            heals = 1

                        if element == 'neutral':
                            element = 'neut'
                        elif element == 'best-element':
                            element = 'best'

                        f.write(f"INSERT INTO weapon_hits VALUES({item_id},{i},{min_value},{max_value},{steals},{heals},'{element}');\n")

                        i += 1

                    elif is_parenthesized_hit and parts:
                        special_element = None
                        if parts[0] == 'attracts':
                            special_element = 'attracts'
                        elif parts[0] in {'pushes', 'push'}:
                            special_element = 'pushes'
                        elif parts[0] == 'advances':
                            special_element = 'advances'
                        elif parts[0] == 'steals' and len(parts) >= 2 and parts[1] == 'mp':
                            special_element = 'steals_mp'
                        elif parts[0] == 'removes' and len(parts) >= 2 and parts[1] == 'ap':
                            special_element = 'removes_ap'
                        if special_element:
                            f.write(f"INSERT INTO weapon_hits VALUES({item_id},{i},{min_value},{max_value},0,0,'{special_element}');\n")
                            i += 1

    f.write("""CREATE TABLE item_flags (item INTEGER, flag TEXT, FOREIGN KEY(item) REFERENCES items(id));\n""")

    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'stats' in item:
            for stat in item['stats']:
                min_value, max_value, description = stat
                if min_value is None and max_value is None:
                    desc = str(description).strip()
                    if not (desc.startswith('(') and desc.endswith(')')):
                        f.write(f"INSERT INTO item_flags VALUES({item_id}, '{escape_single_quotes(desc)}');\n")

    # Trophies share the Dofus slot (same internal type), so the only way to tell
    # them apart later is a flag. w_type == 'Trophy' is overwritten to 'Dofus' above
    # for the slot, so we captured it as is_trophy; keep it as a 'Trophy' flag so the
    # optimizer can offer a "no trophies" option. Runs for every version.
    for item in original_data:
        if item.get('is_trophy'):
            item_id = item_to_id[id(item)]
            f.write(f"INSERT INTO item_flags VALUES({item_id}, 'Trophy');\n")

    f.write("""CREATE TABLE extra_lines (item INTEGER, line text, language text, FOREIGN KEY(item) REFERENCES items(id));\n""")

    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'special_spell_en' in item:
            for lang in LANGUAGES:
                special_spell_key = f'special_spell_{lang}'
                if special_spell_key in item:
                    description = item[special_spell_key]
                    
                    # Split the description into lines and store in a list
                    description_lines = description.split('\n')

                    # Serialize the list using pickle
                    pickled_data = pickle.dumps(description_lines)

                    # Convert the pickled data to a hexadecimal string
                    hex_data = pickled_data.hex()

                    f.write(f"INSERT INTO extra_lines VALUES({item_id}, X'{hex_data}', '{lang}');\n")

    f.write("""CREATE TABLE item_names (item INTEGER, language text, name text, FOREIGN KEY(item) REFERENCES items(id));\n""")

    for item in original_data:
        item_id = item_to_id[id(item)]
        for lang in LANGUAGES:
            if lang == 'en':
                continue
            name_key = f'name_{lang}'
            if name_key in item:
                name = item[name_key]
                f.write(f"INSERT INTO item_names VALUES({item_id}, '{lang}', '{escape_single_quotes(name)}');\n")

    f.write("""CREATE TABLE set_names (item_set INTEGER, language text, name text, FOREIGN KEY(item_set) REFERENCES sets(id));\n""")

    for item in original_sets:
        set_id = item['ankama_id']
        for lang in LANGUAGES:
            if lang == 'en':
                continue
            name_key = f'name_{lang}'
            if name_key in item:
                name = item[name_key]
                f.write(f"INSERT INTO set_names VALUES({set_id}, '{lang}', '{escape_single_quotes(name)}');\n")

    f.write("""CREATE TABLE item_weird_conditions (item INTEGER, condition_id INTEGER, FOREIGN KEY(item) REFERENCES items(id));\n""")

    for item in original_data:
        item_id = item_to_id[id(item)]
        if 'conditions' in item:
            _conds = item["conditions"]
            _cond_text = _conds if isinstance(_conds, str) else ' '.join(str(c) for c in _conds)
            # light_set: dofus3/beta "Set bonus < 3" -> id 1 (cap 2); the stricter
            # touch "Set bonus < 2" -> id 3 (cap 1). See LIGHT_SET_LIMIT_FROM_ID.
            if 'Set bonus < 2' in _cond_text:
                f.write(f"INSERT INTO item_weird_conditions VALUES({item_id}, 3);\n")
            elif 'Set bonus <' in _cond_text:
                f.write(f"INSERT INTO item_weird_conditions VALUES({item_id}, 1);\n")
        if 'is_prysmaradite' in item:
            if item['is_prysmaradite']:
                f.write(f"INSERT INTO item_weird_conditions VALUES({item_id}, 2);\n")

    # Note: sqlite_sequence is no longer needed since we're not using AUTOINCREMENT
    # The IDs are now explicitly set using ankama_id
    f.write("""COMMIT;\n""")
    
