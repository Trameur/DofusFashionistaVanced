#!/usr/bin/env python
# coding=utf-8

"""store_touch_pet_bonuses.py: maxed-stat variants for Dofus Touch pets.

Touch pets gain their stats by feeding, so the backend datacenter carries no
bonus values; scrape_touch_pet_bonuses.py writes the official per-pet maxima to
itemscraper/touch_pet_bonuses.json:

    { "<English pet name>": [ ["<stat name>", <max value>], ... ], ... }

Each listed (pet, stat) is an exclusive feeding choice, so every entry becomes
one maxed Pet item, "<Pet> (+110 Agility)", localized in FR/ES/PT/DE. Variants
reuse the pet's ankama id. Re-dumps items_touch.db.

A saved build keeps the variant's id, so the id is computed from the pet and
the stat, never from a position in the file: see variant_id. Every id ever
written is recorded in touch_pet_variant_ids.json, and one that is not written
any more resolves through legacy_item_ids to the same pet."""

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
REGISTRY_PATH = os.path.join(CURRENT_DIRECTORY, 'touch_pet_variant_ids.json')
# Reserved id range for generated variants; real Touch ids stay below ~101M.
VARIANT_ID_BASE = 200_000_000
# Until 2026-09-18 a counter over the file handed out 200000000 to 200000227,
# and 200000228 is what old builds keep for the Gelano
# (structure.GELANO_DEPLOYED_IDS). Those ids are retired for good. The fixed
# Gelano ids start at 990000001.
FIRST_FREE_VARIANT_ID = 200_000_229
VARIANT_ID_CEILING = 990_000_000
NON_EN_LANGUAGES = ['fr', 'es', 'pt', 'de']

# The last part of a variant id. A number is never changed nor given to another
# stat: new stats take the next free one, below 100.
STAT_SLOTS = {
    'Vitality': 1, 'Wisdom': 2, 'Strength': 3, 'Intelligence': 4,
    'Chance': 5, 'Agility': 6, 'Power': 7, 'AP': 8, 'MP': 9, 'Range': 10,
    'Summon': 11, 'Critical Hits': 12, 'Initiative': 13, 'Prospecting': 14,
    'Pods': 15, 'Heals': 16, 'Damage': 17, 'Neutral Damage': 18,
    'Earth Damage': 19, 'Fire Damage': 20, 'Water Damage': 21,
    'Air Damage': 22, 'Critical Damage': 23, 'Pushback Damage': 24,
    'Trap Damage': 25, '% Trap Damage': 26, '% Neutral Resist': 27,
    '% Earth Resist': 28, '% Fire Resist': 29, '% Water Resist': 30,
    '% Air Resist': 31, 'Neutral Resist': 32, 'Earth Resist': 33,
    'Fire Resist': 34, 'Water Resist': 35, 'Air Resist': 36,
    'Critical Resist': 37, 'Pushback Resist': 38, 'Dodge': 39, 'Lock': 40,
    'AP Reduction': 41, 'MP Reduction': 42, 'AP Loss Resist': 43,
    'MP Loss Resist': 44, 'Reflects': 45,
}


def variant_id(ankama_id, stat_name):
    """The id of the variant of this pet fed toward this stat. A cap that moves
    keeps it, and so does every other variant when a pet or a line comes or
    goes."""
    variant = VARIANT_ID_BASE + ankama_id * 100 + STAT_SLOTS[stat_name]
    if not FIRST_FREE_VARIANT_ID <= variant < VARIANT_ID_CEILING:
        raise ValueError('pet %d gives variant id %d, outside [%d, %d)'
                         % (ankama_id, variant, FIRST_FREE_VARIANT_ID,
                            VARIANT_ID_CEILING))
    return variant


def read_registry(path=REGISTRY_PATH):
    """{variant id: (pet ankama id, stat name)} for every id ever written."""
    if not os.path.exists(path):
        return {}
    with open(path, encoding='utf-8') as handle:
        return {int(key): (int(pet), stat)
                for key, (pet, stat) in json.load(handle).items()}


def write_registry(registry, path=REGISTRY_PATH):
    lines = ['  "%d": [%d, %s]' % (key, pet, json.dumps(stat))
             for key, (pet, stat) in sorted(registry.items())]
    with open(path, 'w', encoding='utf-8', newline='\n') as handle:
        handle.write('{\n' + ',\n'.join(lines) + '\n}\n')


def legacy_targets(registry, written, base_pet_ids):
    """{retired id: live item id}. A retired id goes to the variant of the same
    pet and stat when there is one, the fake per-meal lines included, and to
    the pet itself otherwise: its cap is a stat of its own (Sirocco 160
    Agility) or the game took the line away. A pet the data lost entirely
    resolves to nothing."""
    targets = {}
    for old_id, (pet, stat) in registry.items():
        if old_id in written:
            continue
        current = variant_id(pet, stat) if stat in STAT_SLOTS else None
        if current in written:
            targets[old_id] = current
        elif pet in base_pet_ids:
            targets[old_id] = base_pet_ids[pet]
    return targets


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
    'Initiative': {'fr': 'Initiative', 'es': 'Iniciativa', 'pt': 'Iniciativa', 'de': 'Initiative'},
    'Heals': {'fr': 'Soins', 'es': 'Curaciones', 'pt': 'Cura', 'de': 'Heilung'},
    'Damage': {'fr': 'Dommages', 'es': 'Daños', 'pt': 'Danos', 'de': 'Schaden'},
    'Pods': {'fr': 'Pods', 'es': 'Pods', 'pt': 'Pods', 'de': 'Pods'},
    'Power': {'fr': 'Puissance', 'es': 'Potencia', 'pt': 'Potência', 'de': 'Schlagkraft'},
    'AP': {'fr': 'PA', 'es': 'PA', 'pt': 'PA', 'de': 'AP'},
    'MP': {'fr': 'PM', 'es': 'PM', 'pt': 'PM', 'de': 'BP'},
    'Dodge': {'fr': 'Fuite', 'es': 'Huida', 'pt': 'Fuga', 'de': 'Ausweichen'},
    'Lock': {'fr': 'Tacle', 'es': 'Placaje', 'pt': 'Bloqueio', 'de': 'Blocken'},
    'AP Loss Resist': {'fr': 'Esquive PA', 'es': 'Esquiva de PA', 'pt': 'Esquiva PA',
                       'de': 'AP-Verlustresistenz'},
    'MP Loss Resist': {'fr': 'Esquive PM', 'es': 'Esquiva de PM', 'pt': 'Esquiva PM',
                       'de': 'Resistenz gegen BP-Verlust'},
    'Critical Damage': {'fr': 'Dommages Critiques', 'es': 'Daños Críticos',
                        'pt': 'Danos Críticos', 'de': 'Kritischer Schaden'},
    'Critical Resist': {'fr': 'Résistance Critique', 'es': 'Resistencia a los críticos',
                        'pt': 'Resistência Crítica', 'de': 'Kritischer Widerstand'},
    'Pushback Damage': {'fr': 'Dommages Poussée', 'es': 'Daños de Empuje',
                        'pt': 'Danos de Empurrão', 'de': 'Schubsschaden'},
    'Pushback Resist': {'fr': 'Résistance Poussée', 'es': 'Resistencia al empuje',
                        'pt': 'Resistência ao Empurrão', 'de': 'Pushback-Widerstand'},
    'Range': {'fr': 'Portée', 'es': 'Alcance', 'pt': 'AL', 'de': 'Reichweite'},
    'Summon': {'fr': 'Invocations', 'es': 'Invocaciones', 'pt': 'Invocações',
               'de': 'Beschwörung'},
    'Critical Hits': {'fr': 'Coups critiques', 'es': 'Golpes Críticos',
                      'pt': 'Golpes Críticos', 'de': 'Kritische Treffer'},
    'Trap Damage': {'fr': 'Dommages (Pièges)', 'es': 'Daños con trampas',
                    'pt': 'Danos Armadilhas', 'de': 'Fallenschaden'},
    '% Trap Damage': {'fr': 'Puissance Pièges', 'es': 'Potencia Trampas',
                      'pt': 'Potência Armadilhas', 'de': 'Fallenschaden'},
    'AP Reduction': {'fr': 'Retrait PA', 'es': 'Retiro de PA', 'pt': 'Retirada de PA',
                     'de': 'AP-Entzug'},
    'MP Reduction': {'fr': 'Retrait PM', 'es': 'Retiro de PM', 'pt': 'Retirada de PM',
                     'de': 'BP-Entzug'},
    'Reflects': {'fr': 'Renvoi', 'es': 'Reenvío de daños', 'pt': 'Danos Refletidos',
                 'de': 'Reflektiert'},
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


def _best_lines(pet_name, entries):
    """[(stat, value)], one per stat, at its highest value. A stat listed twice
    was the diet's gain per meal read as a cap, and one id per pet and stat
    has room for one line."""
    best = {}
    for stat_name, value in entries:
        value = int(value)
        if stat_name in best and best[stat_name] != value:
            print('  ! %s lists %s twice (%d and %d), keeping the higher'
                  % (pet_name, stat_name, best[stat_name], value))
        best[stat_name] = max(value, best.get(stat_name, value))
    return list(best.items())


def _drop_own_legacy_rows(cursor, registry):
    """Remove the aliases a previous run wrote, after checking that none of
    those ids is held by another table's alias for another item."""
    if not _table_exists(cursor, 'legacy_item_ids'):
        cursor.execute("""CREATE TABLE legacy_item_ids
             (old_id INTEGER PRIMARY KEY, item INTEGER,
              FOREIGN KEY(item) REFERENCES items(id))""")
        return
    clashes = []
    for old_id, (pet, _stat) in registry.items():
        row = cursor.execute(
            "SELECT i.ankama_id FROM legacy_item_ids l"
            " LEFT JOIN items i ON i.id = l.item WHERE l.old_id = ?",
            (old_id,)).fetchone()
        if row is not None and row[0] is not None and row[0] != pet:
            clashes.append(old_id)
    if clashes:
        raise RuntimeError('legacy_item_ids already sends %d variant id(s) to '
                           'another item, e.g. %s' % (len(clashes), clashes[:5]))
    cursor.executemany("DELETE FROM legacy_item_ids WHERE old_id = ?",
                       [(old_id,) for old_id in registry])


def main():
    with open(BONUSES_PATH, encoding='utf-8') as in_file:
        bonuses = json.load(in_file)
    registry = read_registry()

    conn = _open_items_db(GAME_VERSION)
    cursor = conn.cursor()
    for table in ('items', 'stats_of_item', 'item_names', 'stats', 'item_types'):
        if not _table_exists(cursor, table):
            raise RuntimeError('%s table missing in %s' % (table, get_items_db_path(GAME_VERSION)))

    pet_type = cursor.execute("SELECT id FROM item_types WHERE name = 'Pet'").fetchone()[0]
    stat_id_by_name = {name: sid for sid, name in cursor.execute("SELECT id, name FROM stats")}

    # item_drops does not exist yet on a from-scratch rebuild. This step runs
    # BEFORE drops/store on purpose, because store_drops attaches a drop to
    # every internal row of an ankama id and a variant created afterwards would
    # keep none. So on a fresh db the table is simply absent, and the two
    # statements that touch it raised "no such table: item_drops", took the
    # whole transaction down with them and left the 228 pet variants
    # unwritten: 3146 Touch items instead of 3374. The order is right; this
    # script has to cope with the table not being there yet.
    has_drops = cursor.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table'"
        " AND name = 'item_drops'").fetchone() is not None

    _drop_own_legacy_rows(cursor, registry)

    # Drop the variants of a previous run.
    cursor.execute("DELETE FROM stats_of_item WHERE item >= ?", (VARIANT_ID_BASE,))
    cursor.execute("DELETE FROM item_names WHERE item >= ?", (VARIANT_ID_BASE,))
    cursor.execute("DELETE FROM items WHERE id >= ?", (VARIANT_ID_BASE,))
    cursor.execute("DELETE FROM item_descriptions WHERE item >= ?", (VARIANT_ID_BASE,))
    cursor.execute("DELETE FROM item_extra_info WHERE item >= ?", (VARIANT_ID_BASE,))
    if has_drops:
        cursor.execute("DELETE FROM item_drops WHERE item >= ?", (VARIANT_ID_BASE,))

    # Mounts share the Pet type but number their ankama ids on their own, so
    # one of theirs could give a pet's variant id.
    base_pet_ids = {}
    for pet_id, ankama_id in cursor.execute(
            """SELECT id, ankama_id FROM items WHERE type = ? AND id < ?
               AND ankama_id IS NOT NULL AND ankama_type != 'mounts'""",
            (pet_type, VARIANT_ID_BASE)):
        base_pet_ids.setdefault(ankama_id, pet_id)

    written = {}
    pets_done = 0
    for pet_name, entries in bonuses.items():
        if not entries:
            continue
        rows = cursor.execute(
            """SELECT id, ankama_id, name, level, ankama_type, dofustouch
               FROM items WHERE type = ? AND id < ? AND name = ?
               AND ankama_id IS NOT NULL AND ankama_type != 'mounts'""",
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

            base_stats = set(cursor.execute(
                "SELECT stat, value FROM stats_of_item WHERE item = ?",
                (pet_id,)).fetchall())

            for stat_name, value in _best_lines(pet_name, entries):
                stat_id = stat_id_by_name.get(stat_name)
                if stat_id is None or stat_name not in STAT_SLOTS:
                    print('  ! unknown stat %r for %s, skipping' % (stat_name, pet_name))
                    continue
                # Some pets already carry their maxed bonus as datacenter stats
                # (Sirocco 160 agi).
                if (stat_id, value) in base_stats:
                    continue
                is_percent = stat_name.strip().startswith('%')
                new_id = variant_id(ankama_id, stat_name)
                if new_id in written:
                    raise RuntimeError('two pet rows share ankama id %d' % ankama_id)
                if registry.get(new_id, (ankama_id, stat_name)) != (ankama_id, stat_name):
                    raise RuntimeError('variant id %d was %s and would become %s'
                                       % (new_id, registry[new_id],
                                          (ankama_id, stat_name)))
                written[new_id] = (ankama_id, stat_name)
                cursor.execute(
                    """INSERT INTO items(id, name, level, type, item_set, ankama_id,
                                         ankama_type, removed, dofustouch)
                       VALUES (?, ?, ?, ?, NULL, ?, ?, 0, ?)""",
                    (new_id, _variant_name(en_name, _label(stat_name, 'en'), value, is_percent),
                     level, pet_type, ankama_id, ankama_type, dofustouch))
                cursor.execute(
                    "INSERT INTO stats_of_item(item, stat, value) VALUES (?, ?, ?)",
                    (new_id, stat_id, value))
                for lang in NON_EN_LANGUAGES:
                    base = base_names.get(lang) or en_name
                    cursor.execute(
                        "INSERT INTO item_names(item, language, name) VALUES (?, ?, ?)",
                        (new_id, lang,
                         _variant_name(base, _label(stat_name, lang), value, is_percent)))
                # Descriptions and pods are written before this step runs, so
                # copy the pet's. Drops are only there on a rerun over an
                # existing db; on a fresh one drops/store fills them in after
                # us. Without them a maxed variant shows no "Dropped by" while
                # the pet it is made from does.
                cursor.execute(
                    "INSERT OR REPLACE INTO item_descriptions(item, language, description)"
                    " SELECT ?, language, description FROM item_descriptions"
                    " WHERE item = ?", (new_id, pet_id))
                cursor.execute(
                    "INSERT OR REPLACE INTO item_extra_info(item, pods)"
                    " SELECT ?, pods FROM item_extra_info WHERE item = ?",
                    (new_id, pet_id))
                if has_drops:
                    cursor.execute(
                        "INSERT INTO item_drops(item, monster_ankama_id, rate,"
                        " conditions) SELECT ?, monster_ankama_id, rate,"
                        " conditions FROM item_drops WHERE item = ?",
                        (new_id, pet_id))

    registry.update(written)
    targets = legacy_targets(registry, written, base_pet_ids)
    cursor.executemany("INSERT INTO legacy_item_ids(old_id, item) VALUES (?, ?)",
                       sorted(targets.items()))
    lost = sorted(set(registry) - set(written) - set(targets))

    conn.commit()
    conn.close()
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    write_registry(registry)
    unmapped = sum(1 for v in bonuses.values() if not v)
    print('[touch] Created %d maxed-stat variants for %d pets '
          '(%d pets left unmapped in touch_pet_bonuses.json).'
          % (len(written), pets_done, unmapped))
    to_variant = sum(1 for item in targets.values() if item >= VARIANT_ID_BASE)
    print('[touch] %d retired variant ids resolve: %d to a variant, %d to the '
          'pet itself.' % (len(targets), to_variant, len(targets) - to_variant))
    if lost:
        print('  ! %d retired variant id(s) of pets the data no longer has '
              'resolve to nothing: %s' % (len(lost), lost[:10]))


if __name__ == '__main__':
    main()
