#!/usr/bin/env python
# coding=utf-8

"""store_touch_pet_bonuses.py: maxed-stat variants for Dofus Touch pets.

Touch pets gain their stats by feeding (hormone caps), so the backend
datacenter carries no bonus values; scrape_touch_pet_bonuses.py pulls the
official per-pet maxima from the dofus-touch.com encyclopedia into
itemscraper/touch_pet_bonuses.json:

    { "<English pet name>": [ ["<stat name>", <max value>], ... ], ... }

Like on Retro, each listed (pet, stat) is an exclusive feeding choice, so this
creates one maxed Pet item per entry, "<Pet> (+110 Agility)", localized in
FR/ES/PT/DE, that the optimizer can pick. Variants reuse the pet's ankama id
(the encyclopedia still shows one pet) and live in a reserved id range so
re-runs replace cleanly. The range starts at 200M because the Touch db already
uses ids around 101M for synthesized mounts. Re-dumps items_touch.db."""

import json
import os
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _open_items_db, _save_db_to_dump, _table_exists)

GAME_VERSION = 'touch'
BONUSES_PATH = os.path.join(CURRENT_DIRECTORY, 'touch_pet_bonuses.json')
# Reserved id range for generated variants (real Touch ids stay far below:
# max observed is ~101M from the synthesized mounts).
VARIANT_ID_BASE = 200_000_000
NON_EN_LANGUAGES = ['fr', 'es', 'pt', 'de']

# Localized labels for the stats used by pets, so variant names read naturally.
# Falls back to the English stat name for anything not listed here.
STAT_LABELS = {
    'Strength': {'fr': 'Force', 'es': 'Fuerza', 'pt': 'Força', 'de': 'Stärke'},
    'Intelligence': {'fr': 'Intelligence', 'es': 'Inteligencia', 'pt': 'Inteligência', 'de': 'Intelligenz'},
    'Chance': {'fr': 'Chance', 'es': 'Suerte', 'pt': 'Sorte', 'de': 'Glück'},
    'Agility': {'fr': 'Agilité', 'es': 'Agilidad', 'pt': 'Agilidade', 'de': 'Agilität'},
    'Vitality': {'fr': 'Vitalité', 'es': 'Vitalidad', 'pt': 'Vitalidade', 'de': 'Vitalität'},
    'Wisdom': {'fr': 'Sagesse', 'es': 'Sabiduría', 'pt': 'Sabedoria', 'de': 'Weisheit'},
    'Prospecting': {'fr': 'Prospection', 'es': 'Prospección', 'pt': 'Prospecção', 'de': 'Prospektion'},
    'Initiative': {'fr': 'Initiative', 'es': 'Iniciativa', 'pt': 'Iniciativa', 'de': 'Initiative'},
    'Heals': {'fr': 'Soins', 'es': 'Curaciones', 'pt': 'Cura', 'de': 'Heilung'},
    'Damage': {'fr': 'Dommages', 'es': 'Daños', 'pt': 'Danos', 'de': 'Schaden'},
    'Pods': {'fr': 'Pods', 'es': 'Pods', 'pt': 'Pods', 'de': 'Pods'},
    'Power': {'fr': 'Puissance', 'es': 'Potencia', 'pt': 'Potência', 'de': 'Macht'},
    'Air Damage': {'fr': 'Dommages Air', 'es': 'Daños Aire', 'pt': 'Danos Ar', 'de': 'Luftschaden'},
    'Earth Damage': {'fr': 'Dommages Terre', 'es': 'Daños Tierra', 'pt': 'Danos Terra', 'de': 'Erdschaden'},
    'Fire Damage': {'fr': 'Dommages Feu', 'es': 'Daños Fuego', 'pt': 'Danos Fogo', 'de': 'Feuerschaden'},
    'Water Damage': {'fr': 'Dommages Eau', 'es': 'Daños Agua', 'pt': 'Danos Água', 'de': 'Wasserschaden'},
    'Neutral Damage': {'fr': 'Dommages Neutre', 'es': 'Daños Neutral', 'pt': 'Danos Neutro', 'de': 'Neutralschaden'},
    '% Neutral Resist': {'fr': 'Rés Neutre', 'es': 'Res Neutral', 'pt': 'Res Neutra', 'de': 'Neutral-Wid'},
    '% Air Resist': {'fr': 'Rés Air', 'es': 'Res Aire', 'pt': 'Res Ar', 'de': 'Luft-Wid'},
    '% Earth Resist': {'fr': 'Rés Terre', 'es': 'Res Tierra', 'pt': 'Res Terra', 'de': 'Erd-Wid'},
    '% Fire Resist': {'fr': 'Rés Feu', 'es': 'Res Fuego', 'pt': 'Res Fogo', 'de': 'Feuer-Wid'},
    '% Water Resist': {'fr': 'Rés Eau', 'es': 'Res Agua', 'pt': 'Res Água', 'de': 'Wasser-Wid'},
    'Neutral Resist': {'fr': 'Rés Neutre', 'es': 'Res Neutral', 'pt': 'Res Neutra', 'de': 'Neutral-Wid'},
    'Air Resist': {'fr': 'Rés Air', 'es': 'Res Aire', 'pt': 'Res Ar', 'de': 'Luft-Wid'},
    'Earth Resist': {'fr': 'Rés Terre', 'es': 'Res Tierra', 'pt': 'Res Terra', 'de': 'Erd-Wid'},
    'Fire Resist': {'fr': 'Rés Feu', 'es': 'Res Fuego', 'pt': 'Res Fogo', 'de': 'Feuer-Wid'},
    'Water Resist': {'fr': 'Rés Eau', 'es': 'Res Agua', 'pt': 'Res Água', 'de': 'Wasser-Wid'},
}


def _label(stat_name, lang):
    labels = STAT_LABELS.get(stat_name)
    if labels and lang in labels:
        return labels[lang]
    return stat_name[2:] if stat_name.startswith('% ') else stat_name


def _variant_name(base_name, stat_label, value, is_percent):
    return ('%s (+%d%% %s)' if is_percent else '%s (+%d %s)') % (base_name, value, stat_label)


def main():
    with open(BONUSES_PATH, encoding='utf-8') as in_file:
        bonuses = json.load(in_file)

    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    for table in ('items', 'stats_of_item', 'item_names', 'stats', 'item_types'):
        if not _table_exists(cursor, table):
            raise RuntimeError('%s table missing in %s' % (table, get_items_db_path(GAME_VERSION)))

    pet_type = cursor.execute("SELECT id FROM item_types WHERE name = 'Pet'").fetchone()[0]
    stat_id_by_name = {name: sid for sid, name in cursor.execute("SELECT id, name FROM stats")}

    # Idempotent: drop any variants this script created before, then rebuild.
    cursor.execute("DELETE FROM stats_of_item WHERE item >= ?", (VARIANT_ID_BASE,))
    cursor.execute("DELETE FROM item_names WHERE item >= ?", (VARIANT_ID_BASE,))
    cursor.execute("DELETE FROM items WHERE id >= ?", (VARIANT_ID_BASE,))

    next_id = VARIANT_ID_BASE
    created = 0
    pets_done = 0
    for pet_name, entries in bonuses.items():
        if not entries:
            continue
        rows = cursor.execute(
            """SELECT id, ankama_id, name, level, ankama_type, dofustouch
               FROM items WHERE type = ? AND id < ? AND name = ?""",
            (pet_type, VARIANT_ID_BASE, pet_name)).fetchall()
        if not rows:
            print('  ! pet not found in DB, skipping: %s' % pet_name)
            continue
        pets_done += 1
        for pet_id, ankama_id, en_name, level, ankama_type, dofustouch in rows:
            base_names = {'en': en_name}
            for lang, name in cursor.execute(
                    "SELECT language, name FROM item_names WHERE item = ?", (pet_id,)).fetchall():
                base_names[lang] = name

            for entry in entries:
                stat_name, value = entry[0], int(entry[1])
                stat_id = stat_id_by_name.get(stat_name)
                if stat_id is None:
                    print('  ! unknown stat %r for %s, skipping' % (stat_name, pet_name))
                    continue
                is_percent = stat_name.strip().startswith('%')
                variant_id = next_id
                next_id += 1
                cursor.execute(
                    """INSERT INTO items(id, name, level, type, item_set, ankama_id,
                                         ankama_type, removed, dofustouch)
                       VALUES (?, ?, ?, ?, NULL, ?, ?, 0, ?)""",
                    (variant_id, _variant_name(en_name, _label(stat_name, 'en'), value, is_percent),
                     level, pet_type, ankama_id, ankama_type, dofustouch))
                cursor.execute(
                    "INSERT INTO stats_of_item(item, stat, value) VALUES (?, ?, ?)",
                    (variant_id, stat_id, value))
                for lang in NON_EN_LANGUAGES:
                    base = base_names.get(lang) or en_name
                    cursor.execute(
                        "INSERT INTO item_names(item, language, name) VALUES (?, ?, ?)",
                        (variant_id, lang,
                         _variant_name(base, _label(stat_name, lang), value, is_percent)))
                created += 1

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    unmapped = sum(1 for v in bonuses.values() if not v)
    print('[touch] Created %d maxed-stat variants for %d pets '
          '(%d pets left unmapped in touch_pet_bonuses.json).'
          % (created, pets_done, unmapped))


if __name__ == '__main__':
    main()
