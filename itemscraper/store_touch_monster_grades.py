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

"""Store the official Touch monster stats per grade into items_touch.db.

Source: the Touch backend Monsters table (touch_raw/Monsters_fr.json). A monster
carries up to five grades, and the numbers are language-neutral, so one raw file
is enough.

Usage (from itemscraper/):
    python store_touch_monster_grades.py [--raw-dir touch_raw]
"""

import argparse
import json
import os
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                       'items_touch.db')

GRADE_FIELDS = (
    ('level', 'level'),
    ('lifePoints', 'life_points'),
    ('actionPoints', 'action_points'),
    ('movementPoints', 'movement_points'),
    ('paDodge', 'ap_dodge'),
    ('pmDodge', 'mp_dodge'),
    ('earthResistance', 'earth_resistance'),
    ('airResistance', 'air_resistance'),
    ('fireResistance', 'fire_resistance'),
    ('waterResistance', 'water_resistance'),
    ('neutralResistance', 'neutral_resistance'),
)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--raw-dir', default=os.path.join(CURRENT_DIR, 'touch_raw'))
    args = parser.parse_args()

    raw_path = os.path.join(args.raw_dir, 'Monsters_fr.json')
    with open(raw_path, encoding='utf-8') as fh:
        monsters = json.load(fh)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
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

    stored = empty = 0
    for monster in monsters.values():
        monster_id = monster.get('id')
        for grade in monster.get('grades') or []:
            row = [monster_id, grade.get('grade')]
            row.extend(grade.get(source) for source, _column in GRADE_FIELDS)
            # The backend ships placeholder monsters whose grades carry no life
            # points, and some no level either. They rendered as a table of
            # dashes. A row we cannot fill is worse than no row.
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
    count = cursor.execute(
        'SELECT COUNT(DISTINCT monster_ankama_id) FROM monster_grades').fetchone()[0]
    conn.close()
    print('stored %d grade rows for %d monsters, %d empty dropped'
          % (stored, count, empty))
    # The pipeline's load-db rebuilds the db from the dump.
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(DB_PATH, 'touch')
    print('touch dump refreshed')
    return 0


if __name__ == '__main__':
    sys.exit(main())
