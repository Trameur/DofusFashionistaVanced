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

"""Store where each Dofus 3 / Beta monster can be found, from the datacenter dump.

    python store_monster_subareas.py --game-version dofus3|beta --tag 3.7.14.18
"""

import argparse
import os
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from store_item_obtainment import _save_db_to_dump, get_items_db_path  # noqa: E402
from store_monster_spells import RAW_ROOT, _labels, _table  # noqa: E402
from untranslated_tag import clean_display_name  # noqa: E402

VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
MIN_ROWS = 12000
FILES = ('monsters.json', 'subareas.json') + tuple('%s.json' % language for language in LANGUAGES)

CREATE_TABLE = """
        CREATE TABLE monster_subareas (
            monster_ankama_id INTEGER NOT NULL,
            language TEXT NOT NULL,
            position INTEGER NOT NULL,
            name TEXT NOT NULL,
            PRIMARY KEY (monster_ankama_id, language, position)
        )
        """


def read_dump(dump_dir):
    """({subarea id: {language: name}}, {monster id: [subarea id]}) from a datacenter dump."""
    missing = [name for name in FILES if not os.path.isfile(os.path.join(dump_dir, name))]
    if missing:
        raise SystemExit('%s lacks %s' % (dump_dir, ', '.join(missing)))
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


def build_rows(subarea_names, monster_subareas, known_ids):
    """(rows, unresolved): the table rows in game order and the (monster, subarea) pairs the dump does not name."""
    rows = []
    unresolved = []
    for monster_id, subarea_ids in sorted(monster_subareas.items()):
        if monster_id not in known_ids:
            continue
        unresolved.extend((monster_id, subarea_id) for subarea_id in subarea_ids
                          if subarea_id not in subarea_names)
        for language in LANGUAGES:
            names = []
            for subarea_id in subarea_ids:
                name = clean_display_name((subarea_names.get(subarea_id) or {}).get(language))
                if name and name not in names:
                    names.append(name)
            rows.extend((monster_id, language, position, name)
                        for position, name in enumerate(names))
    return rows, unresolved


def check_rows(rows):
    """Refuse a table too small to be the real one."""
    if len(rows) < MIN_ROWS:
        raise ValueError('only %d monster_subareas rows, expected at least %d'
                         % (len(rows), MIN_ROWS))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=VERSIONS)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args(argv)

    subarea_names, monster_subareas = read_dump(os.path.join(RAW_ROOT, args.tag))
    db_path = get_items_db_path(args.game_version)
    conn = sqlite3.connect(db_path)
    try:
        known_ids = {row[0] for row in conn.execute(
            'SELECT DISTINCT monster_ankama_id FROM monster_names')}
        rows, unresolved = build_rows(subarea_names, monster_subareas, known_ids)
        check_rows(rows)
        conn.execute('BEGIN')
        conn.execute('DROP TABLE IF EXISTS monster_subareas')
        conn.execute(CREATE_TABLE)
        conn.executemany('INSERT INTO monster_subareas VALUES (?, ?, ?, ?)', rows)
        conn.commit()
    finally:
        conn.close()
    _save_db_to_dump(db_path, args.game_version)
    for monster_id, subarea_id in unresolved:
        print('subarea %d of monster %d not found in raw/%s/subareas.json'
              % (subarea_id, monster_id, args.tag))
    print('stored %d subarea rows for %d %s monsters'
          % (len(rows), len({row[0] for row in rows}), args.game_version))
    return 0


if __name__ == '__main__':
    sys.exit(main())
