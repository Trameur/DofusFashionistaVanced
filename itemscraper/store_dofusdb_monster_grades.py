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

"""Store the monster stats per grade for dofus3 or beta, from the DofusDB API.

Usage (from itemscraper/):
    python store_dofusdb_monster_grades.py [--game-version dofus3|beta]
"""

import argparse
import json
import os
import sqlite3
import sys
import urllib.request

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

BASES = {
    'dofus3': 'https://api.dofusdb.fr',
    'beta': 'https://api.beta.dofusdb.fr',
}
DB_FILES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
}
PAGE_SIZE = 50

GRADE_FIELDS = ('level', 'lifePoints', 'actionPoints', 'movementPoints',
                'paDodge', 'pmDodge', 'earthResistance', 'airResistance',
                'fireResistance', 'waterResistance', 'neutralResistance')


def fetch(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(req, timeout=60))


def iter_monster_grades(base_url):
    skip = 0
    while True:
        url = ('%s/monsters?%%24limit=%d&%%24skip=%d'
               '&%%24select%%5B%%5D=id&%%24select%%5B%%5D=grades'
               % (base_url, PAGE_SIZE, skip))
        rows = fetch(url).get('data', [])
        if not rows:
            return
        for row in rows:
            if row.get('id') is not None:
                yield row['id'], row.get('grades') or []
        skip += PAGE_SIZE


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-version', default='dofus3',
                        choices=sorted(BASES))
    args = parser.parse_args()

    db_path = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                           DB_FILES[args.game_version])
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    known_ids = {row[0] for row in cursor.execute(
        'SELECT DISTINCT monster_ankama_id FROM monster_names')}
    print('%s: %d monsters in db' % (args.game_version, len(known_ids)))

    cursor.execute('DROP TABLE IF EXISTS monster_grades')
    cursor.execute(
        """
        CREATE TABLE monster_grades (
            monster_ankama_id INTEGER NOT NULL,
            grade INTEGER NOT NULL,
            level INTEGER,
            life_points INTEGER,
            action_points INTEGER,
            movement_points INTEGER,
            ap_dodge INTEGER,
            mp_dodge INTEGER,
            earth_resistance INTEGER,
            air_resistance INTEGER,
            fire_resistance INTEGER,
            water_resistance INTEGER,
            neutral_resistance INTEGER,
            PRIMARY KEY (monster_ankama_id, grade)
        )
        """)

    stored = matched = empty = 0
    for monster_id, grades in iter_monster_grades(BASES[args.game_version]):
        if monster_id not in known_ids:
            continue
        matched += 1
        for grade in grades:
            row = [monster_id, grade.get('grade')]
            row.extend(grade.get(field) for field in GRADE_FIELDS)
            if row[1] is None:
                continue
            # DofusDB keeps unused duplicates of real monsters, all grades at
            # level 1 with no life points: Arachnee is both id 52 (16-20,
            # 90-120 hp) and id 246 (empty). Storing the empty one published a
            # grade table of dashes. A row we cannot fill is worse than no row.
            if not row[2] or not row[3]:
                empty += 1
                continue
            # -1 and -100 turn up in the AP and MP columns: the client's
            # way of saying a creature does not move, not a value a player
            # ever sees. Store the absence and let the page print a dash.
            for i in (4, 5):
                if row[i] is not None and row[i] < 0:
                    row[i] = None
            cursor.execute(
                'INSERT OR REPLACE INTO monster_grades VALUES (%s)'
                % ','.join('?' * len(row)), row)
            stored += 1
    conn.commit()
    conn.close()
    # Keep the dump in sync: load-db rebuilds the db from it
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(db_path, args.game_version)
    print('stored %d grade rows for %d monsters, %d empty dropped'
          % (stored, matched, empty))
    return 0


if __name__ == '__main__':
    sys.exit(main())
