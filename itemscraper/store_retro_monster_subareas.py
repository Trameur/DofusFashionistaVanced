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

"""Store where each Retro monster can be found into items_retro.db, from the monsters and maps lang files; python store_retro_monster_subareas.py [--raw-dir DIR] [--languages fr en ...] from itemscraper/."""

import argparse
import json
import os
import re
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                       'items_retro.db')
RAW_DIR = os.path.join(CURRENT_DIR, 'retro_raw')

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
MIN_FR_ROWS = 1800

CREATE_TABLE = """
    CREATE TABLE monster_subareas (
        monster_ankama_id INTEGER NOT NULL,
        language TEXT NOT NULL,
        position INTEGER NOT NULL,
        name TEXT NOT NULL,
        PRIMARY KEY (monster_ankama_id, language, position)
    )
"""

REPLACEMENT_CHARACTER = chr(0xFFFD)
C1_CONTROL_RE = re.compile('[' + chr(0x80) + '-' + chr(0x9f) + ']')


def _int_keys(table):
    return {int(key): value for key, value in table.items()}


def _read_json(path):
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def read_lang(raw_dir, languages):
    """(spawns, maps, versions, missing): spawns by monster id, maps by language."""
    monsters_path = os.path.join(raw_dir, 'monsters_fr.json')
    if not os.path.exists(monsters_path):
        raise SystemExit('monsters_fr.json not found in %s' % raw_dir)
    if not os.path.exists(os.path.join(raw_dir, 'maps_fr.json')):
        raise SystemExit('maps_fr.json not found in %s' % raw_dir)
    monsters = _read_json(monsters_path)
    spawns = {}
    for monster_id, monster in _int_keys(monsters['M']).items():
        spawn = monster.get('spawn') or {}
        spawns[monster_id] = {'a': [int(i) for i in spawn.get('a') or []],
                              'm': [int(i) for i in spawn.get('m') or []]}
    versions = {'monsters_fr': monsters.get('VERSION')}
    maps = {}
    missing = []
    for language in languages:
        path = os.path.join(raw_dir, 'maps_%s.json' % language)
        if not os.path.exists(path):
            missing.append(language)
            continue
        data = _read_json(path)
        table = data['MA']
        maps[language] = {
            'm': _int_keys(table.get('m', {})),
            'sa': _int_keys(table.get('sa', {})),
            'a': _int_keys(table.get('a', {})),
        }
        versions['maps_' + language] = data.get('VERSION')
    return spawns, maps, versions, missing


def map_subareas(maps_fr):
    """{map id: subarea id}."""
    return {map_id: row['sa'] for map_id, row in maps_fr['m'].items()
            if 'sa' in row}


def subareas_with_a_map(maps_fr):
    """The subarea ids that own at least one map."""
    return set(map_subareas(maps_fr).values())


def spawn_subareas(subarea_ids, map_ids, map_subarea):
    """Sorted union of the listed subareas and the subareas of the listed maps."""
    found = set(subarea_ids)
    found.update(map_subarea[map_id] for map_id in map_ids
                 if map_id in map_subarea)
    return sorted(found)


def unplaced_spawn_maps(spawns, maps_fr):
    """(monster id, map id) for each spawn map the French maps file gives no subarea."""
    map_subarea = map_subareas(maps_fr)
    return [(monster_id, map_id) for monster_id in sorted(spawns)
            for map_id in sorted(set(spawns[monster_id]['m']))
            if map_id not in map_subarea]


def display_name(subarea_id, maps, language):
    """Name shown for a subarea; a `//` placeholder shows its area name."""
    french = maps['fr']['sa'][subarea_id]
    french_name = french['n']
    use_area = french_name.startswith('//')
    if use_area:
        french_name = maps['fr']['a'].get(french.get('a'), {}).get(
            'n', french_name[2:])
    if language == 'fr' or language not in maps:
        return french_name
    row = maps[language]['sa'].get(subarea_id)
    if row is None:
        return french_name
    if use_area:
        name = maps[language]['a'].get(
            row.get('a', french.get('a')), {}).get('n')
    else:
        name = row.get('n')
    if not name or name.startswith('//'):
        return french_name
    return name


def build_rows(spawns, maps, languages):
    """(rows, unresolved, mapless, in_french) for every monster the lang files place."""
    maps_fr = maps['fr']
    map_subarea = map_subareas(maps_fr)
    with_a_map = subareas_with_a_map(maps_fr)
    rows = []
    unresolved = []
    mapless = []
    in_french = {language: 0 for language in languages}
    for monster_id in sorted(spawns):
        spawn = spawns[monster_id]
        subarea_ids = []
        for subarea_id in spawn_subareas(spawn['a'], spawn['m'], map_subarea):
            if subarea_id not in maps_fr['sa']:
                unresolved.append((monster_id, subarea_id))
            elif subarea_id not in with_a_map:
                mapless.append((monster_id, subarea_id))
            else:
                subarea_ids.append(subarea_id)
        for language in languages:
            if language not in maps:
                continue
            seen = set()
            position = 0
            for subarea_id in subarea_ids:
                name = display_name(subarea_id, maps, language)
                if name in seen:
                    continue
                seen.add(name)
                rows.append((monster_id, language, position, name))
                position += 1
                if language != 'fr' and name == display_name(
                        subarea_id, maps, 'fr'):
                    in_french[language] += 1
    return rows, unresolved, mapless, in_french


def check_rows(rows):
    """Refuse a table too small to be the real one."""
    french = sum(1 for row in rows if row[1] == 'fr')
    if french < MIN_FR_ROWS:
        raise ValueError('only %d French subarea rows, at least %d expected'
                         % (french, MIN_FR_ROWS))


def broken_names(rows):
    """Names holding U+FFFD, a C1 control or double-encoded text."""
    broken = set()
    for row in rows:
        name = row[3]
        if REPLACEMENT_CHARACTER in name or C1_CONTROL_RE.search(name):
            broken.add(name)
            continue
        try:
            fixed = name.encode('latin-1').decode('utf-8')
        except (UnicodeEncodeError, UnicodeDecodeError):
            continue
        if fixed != name:
            broken.add(name)
    return sorted(broken)


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', default=RAW_DIR)
    parser.add_argument('--languages', nargs='+', default=list(LANGUAGES))
    args = parser.parse_args(argv)
    languages = [language for language in LANGUAGES
                 if language in args.languages]
    if 'fr' not in languages:
        languages.insert(0, 'fr')

    spawns, maps, versions, missing = read_lang(args.raw_dir, languages)
    print('monsters_fr.json VERSION %s' % versions['monsters_fr'])
    for language in languages:
        if language in missing:
            print('warning: maps_%s.json not found, no %s rows'
                  % (language, language))
        else:
            print('maps_%s.json VERSION %s'
                  % (language, versions['maps_' + language]))

    rows, unresolved, mapless, in_french = build_rows(spawns, maps, languages)
    for monster_id, subarea_id in unresolved:
        print('warning: subarea %d of monster %d is not in maps_fr.json'
              % (subarea_id, monster_id))
    for monster_id, map_id in unplaced_spawn_maps(spawns, maps['fr']):
        print('warning: map %d of monster %d has no subarea in maps_fr.json'
              % (map_id, monster_id))
    if mapless:
        print('left out %d rows whose subarea has no map: %s' % (
            len(mapless), ', '.join('%d/%d' % pair for pair in mapless)))
    check_rows(rows)
    broken = broken_names(rows)
    if broken:
        print('error: names with broken encoding: %s' % ', '.join(broken[:10]))
        return 1
    for language in languages:
        if language in maps:
            count = sum(1 for row in rows if row[1] == language)
            print('%s: %d rows, %d names in French'
                  % (language, count, in_french[language]))

    conn = sqlite3.connect(DB_PATH, isolation_level=None)
    try:
        cursor = conn.cursor()
        known_ids = {row[0] for row in cursor.execute(
            'SELECT DISTINCT monster_ankama_id FROM monster_names')}
        cursor.execute('BEGIN')
        cursor.execute('DROP TABLE IF EXISTS monster_subareas')
        cursor.execute(CREATE_TABLE)
        cursor.executemany(
            'INSERT INTO monster_subareas VALUES (?,?,?,?)', rows)
        cursor.execute('COMMIT')
    finally:
        conn.close()
    placed = {row[0] for row in rows if row[1] == 'fr'}
    print('stored %d subarea rows for %d retro monsters (%d with an '
          'encyclopedia page)' % (len(rows), len(placed),
                                  len(placed & known_ids)))

    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(DB_PATH, 'retro')
    print('retro dump refreshed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
