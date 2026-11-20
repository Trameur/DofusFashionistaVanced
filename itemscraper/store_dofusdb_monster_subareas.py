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

"""Store where each Dofus 3 / Beta monster can be found, from the DofusDB API or a raw dump.

Commit both the db and its dump: structure.py rebuilds the db from the dump.

Usage (from itemscraper/):
    python store_dofusdb_monster_subareas.py [--game-version dofus3|beta] [--tag 3.8.2.3]

With --tag the subareas are read from raw/<tag> (monsters.json, subareas.json
and the five lang files) and nothing is downloaded.
"""

import argparse
import json
import os
import sqlite3
import sys
import time
import urllib.request

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from store_monster_spells import RAW_ROOT, _labels, _table  # noqa: E402
from untranslated_tag import clean_display_name  # noqa: E402

BASES = {
    'dofus3': 'https://api.dofusdb.fr',
    'beta': 'https://api.beta.dofusdb.fr',
}
DB_FILES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
}
LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
PAGE = 50


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch_paged(base, path, selects):
    """Every record of a Feathers endpoint, paged by $limit/$skip."""
    select_query = ''.join('&%%24select%%5B%%5D=%s' % field
                           for field in selects)
    records = []
    skip = 0
    while True:
        url = ('%s%s?%%24limit=%d&%%24skip=%d' % (base, path, PAGE, skip)
               + select_query)
        data = fetch(url)
        page = data.get('data') or []
        records.extend(page)
        skip += len(page)
        if not page or skip >= (data.get('total') or 0):
            break
        time.sleep(0.1)
    return records


def from_api(base):
    """({subarea id: {language: name}}, {monster id: [subarea id]}) from DofusDB."""
    subarea_names = {}
    for record in fetch_paged(base, '/subareas', ('id', 'name')):
        name = record.get('name') or {}
        if isinstance(name, dict):
            subarea_names[record['id']] = name
    monster_subareas = {}
    for record in fetch_paged(base, '/monsters', ('id', 'subareas')):
        ids = record.get('subareas') or []
        if ids:
            monster_subareas[record['id']] = ids
    return subarea_names, monster_subareas


def from_raw(dump_dir):
    """Same pair, read from a datacenter dump."""
    labels = _labels(dump_dir)
    subarea_names = {}
    for subarea_id, subarea in _table(os.path.join(dump_dir, 'subareas.json')).items():
        key = str(subarea.get('nameId'))
        subarea_names[subarea_id] = {language: labels[language].get(key)
                                     for language in LANGUAGES}
    monster_subareas = {}
    for monster_id, monster in _table(os.path.join(dump_dir, 'monsters.json')).items():
        ids = (monster.get('subareas') or {}).get('Array') or []
        if ids:
            monster_subareas[monster_id] = ids
    return subarea_names, monster_subareas


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-version', default='dofus3',
                        choices=sorted(BASES))
    parser.add_argument('--tag', help='datacenter dump under raw/ to read instead of DofusDB')
    args = parser.parse_args()

    if args.tag:
        dump_dir = os.path.join(RAW_ROOT, args.tag)
        if not os.path.isdir(dump_dir):
            raise SystemExit('no such dump: %s' % dump_dir)
        print('%s: reading %s' % (args.game_version, dump_dir))
        subarea_names, monster_subareas = from_raw(dump_dir)
    else:
        subarea_names, monster_subareas = from_api(BASES[args.game_version])
    print('%s: %d subareas with names' % (args.game_version, len(subarea_names)))
    print('%s: %d monsters with subareas' % (args.game_version, len(monster_subareas)))

    db_path = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                           DB_FILES[args.game_version])
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    known_ids = {row[0] for row in cursor.execute(
        'SELECT DISTINCT monster_ankama_id FROM monster_names')}
    cursor.execute('DROP TABLE IF EXISTS monster_subareas')
    cursor.execute(
        """
        CREATE TABLE monster_subareas (
            monster_ankama_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            PRIMARY KEY (monster_ankama_id, language, position)
        )
        """)
    stored = 0
    matched = set()
    for monster_id, subarea_ids in sorted(monster_subareas.items()):
        if monster_id not in known_ids:
            continue
        for lang in LANGUAGES:
            names = []
            for subarea_id in subarea_ids:
                name = clean_display_name((subarea_names.get(subarea_id) or {}).get(lang))
                if name and name not in names:
                    names.append(name)
            for position, name in enumerate(names):
                cursor.execute(
                    'INSERT OR REPLACE INTO monster_subareas VALUES (?,?,?,?)',
                    (monster_id, lang, position, name))
                stored += 1
            if names:
                matched.add(monster_id)
    conn.commit()
    conn.close()
    # Keep the dump in sync: load-db rebuilds the db from it
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(db_path, args.game_version)
    print('stored %d subarea rows for %d %s monsters'
          % (stored, len(matched), args.game_version))
    return 0


if __name__ == '__main__':
    sys.exit(main())
