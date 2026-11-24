#!/usr/bin/env python
# coding=utf-8

"""store_retro_pet_bonuses.py: maxed-stat variants for Dofus Retro pets.

Classic Retro pets have no fixed stats: you feed them and one stat grows to a
cap, and most pets are locked to a specific stat (Air Bwak -> Agility, the
Dragoones -> Wisdom, Croums -> resist). Nothing in the data says which, so it
is curated in itemscraper/retro_pet_bonuses.json:

    { "<English pet name>": [ ["<stat name>", <max value>], ... ], ... }

A stat name beginning with "%" is a percentage; an empty list gets no variant.
Each (pet, stat) becomes a maxed Pet item, "<Pet> (+80 Agility)", localized in
FR/ES/PT/DE and reusing the pet's ankama id. Run after load_item_db."""

import argparse
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
import retro_release  # noqa: E402

GAME_VERSION = 'retro'
BONUSES_PATH = os.path.join(CURRENT_DIRECTORY, 'retro_pet_bonuses.json')
# Synthetic id range for the generated variants; real retro ids are < 100000.
VARIANT_ID_BASE = 10_000_000
NON_EN_LANGUAGES = ['fr', 'es', 'pt', 'de']

# Localized labels for the stats used by pets.
STAT_LABELS = {
    'Strength': {'fr': 'Force', 'es': 'Fuerza', 'pt': 'Força', 'de': 'Stärke'},
    'Intelligence': {'fr': 'Intelligence', 'es': 'Inteligencia', 'pt': 'Inteligência', 'de': 'Intelligenz'},
    'Chance': {'fr': 'Chance', 'es': 'Suerte', 'pt': 'Sorte', 'de': 'Glück'},
    # the German client says Flinkheit, not Agilitaet, and the site says it
    # everywhere else; a generated item name is a surface like any other
    'Agility': {'fr': 'Agilité', 'es': 'Agilidad', 'pt': 'Agilidade', 'de': 'Flinkheit'},
    'Vitality': {'fr': 'Vitalité', 'es': 'Vitalidad', 'pt': 'Vitalidade', 'de': 'Vitalität'},
    'Wisdom': {'fr': 'Sagesse', 'es': 'Sabiduría', 'pt': 'Sabedoria', 'de': 'Weisheit'},
    'Prospecting': {'fr': 'Prospection', 'es': 'Prospección', 'pt': 'Prospecção', 'de': 'Prospektion'},
    'Heals': {'fr': 'Soins', 'es': 'Curaciones', 'pt': 'Cura', 'de': 'Heilung'},
    'Damage': {'fr': 'Dommages', 'es': 'Daños', 'pt': 'Danos', 'de': 'Schaden'},
    'Pods': {'fr': 'Pods', 'es': 'Pods', 'pt': 'Pods', 'de': 'Pods'},
    '% Neutral Resist': {'fr': 'Rés Neutre', 'es': 'Res Neutral', 'pt': 'Res Neutra', 'de': 'Neutraler Wid'},
}


def _label(stat_name, lang):
    labels = STAT_LABELS.get(stat_name)
    if labels and lang in labels:
        return labels[lang]
    # Drop a leading "% ": the formatter adds the sign for percentage stats.
    return stat_name[2:] if stat_name.startswith('% ') else stat_name


def _variant_name(base_name, stat_label, value, is_percent):
    return ('%s (+%d%% %s)' if is_percent else '%s (+%d %s)') % (base_name, value, stat_label)


def main(release=retro_release.MAIN):
    global GAME_VERSION
    GAME_VERSION = retro_release.version_key(release)
    with open(BONUSES_PATH, encoding='utf-8') as in_file:
        bonuses = json.load(in_file)

    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    for table in ('items', 'stats_of_item', 'item_names', 'stats', 'item_types'):
        if not _table_exists(cursor, table):
            raise RuntimeError('%s table missing in %s' % (table, get_items_db_path(GAME_VERSION)))

    pet_type = cursor.execute("SELECT id FROM item_types WHERE name = 'Pet'").fetchone()[0]
    stat_id_by_name = {name: sid for sid, name in cursor.execute("SELECT id, name FROM stats")}
    if retro_release.is_beta(release):
        feedable = unnamed_feedable_pets(cursor, pet_type, bonuses)
        retro_release.notice(
            'pet bonuses: no source of the %s is read, the %d pets of main %s are reused; '
            '%d feedable %s pets it does not name get no variant%s'
            % (release, len(bonuses), os.path.basename(BONUSES_PATH), len(feedable), GAME_VERSION,
               (': ' + ', '.join(feedable[:20])) if feedable else ''))

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
            "SELECT id, ankama_id, name, level FROM items WHERE type = ? AND id < ? AND name = ?",
            (pet_type, VARIANT_ID_BASE, pet_name)).fetchall()
        if not rows:
            print('  ! pet not found in DB, skipping: %s' % pet_name)
            continue
        pets_done += 1
        for pet_id, ankama_id, en_name, level in rows:
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
                       VALUES (?, ?, ?, ?, NULL, ?, 'equipment', 0, 0)""",
                    (variant_id, _variant_name(en_name, _label(stat_name, 'en'), value, is_percent),
                     level, pet_type, ankama_id))
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
    print('[%s] Created %d maxed-stat variants for %d pets '
          '(%d pets left unmapped in retro_pet_bonuses.json).'
          % (GAME_VERSION, created, pets_done, unmapped))


def unnamed_feedable_pets(cursor, pet_type, bonuses):
    """English names of the pets with no stat of their own that the bonuses file does not name."""
    rows = cursor.execute(
        """SELECT name FROM items i WHERE type = ? AND id < ? AND NOT EXISTS
               (SELECT 1 FROM stats_of_item s WHERE s.item = i.id)""", (pet_type, VARIANT_ID_BASE))
    return sorted({name for (name,) in rows if name not in bonuses})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    retro_release.add_release_argument(parser)
    main(parser.parse_args().release)
