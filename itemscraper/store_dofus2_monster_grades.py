#!/usr/bin/env python
# coding=utf-8

"""store_dofus2_monster_grades.py: monster stats per grade for Dofus 2.

Source: the dofusdude 2.73 archive's monsters.json, which carries the same
grade records the other versions use (level, life, AP, MP, dodges and the five
resistances). It is the only version whose encyclopedia monster pages showed a
name and drops but no level range at all, because nothing ever filled the
table: `monster_grades` was absent from items_dofus2.db entirely.

The numbers are language-neutral, so one archive is enough.

Usage (from itemscraper/):
    python store_dofus2_monster_grades.py [--raw-dir raw/2.73.3.9]
"""

import argparse
import json
import os
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
for path in (ROOT, CURRENT_DIR):
    if path not in sys.path:
        sys.path.append(path)

from store_item_obtainment import (  # noqa: E402  (sys.path set above)
    get_items_db_path, _save_db_to_dump)

GAME_VERSION = 'dofus2'

GRADE_FIELDS = (
    'level', 'lifePoints', 'actionPoints', 'movementPoints',
    'paDodge', 'pmDodge', 'earthResistance', 'airResistance',
    'fireResistance', 'waterResistance', 'neutralResistance',
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw-dir',
                        default=os.path.join(CURRENT_DIR, 'raw', '2.73.3.9'))
    args = parser.parse_args()

    raw_path = os.path.join(args.raw_dir, 'monsters.json')
    with open(raw_path, encoding='utf-8') as in_file:
        monsters = json.load(in_file)
    if isinstance(monsters, dict):
        monsters = list(monsters.values())

    conn = sqlite3.connect(get_items_db_path(GAME_VERSION))
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

    known = {row[0] for row in
             cursor.execute('SELECT DISTINCT monster_ankama_id FROM monster_names')}
    stored = skipped = empty = 0
    for monster in monsters:
        if not isinstance(monster, dict):
            continue
        monster_id = monster.get('id')
        # Only monsters the version actually names: the archive carries entries
        # this release never shipped, and an unnamed row shows on no page.
        if monster_id not in known:
            skipped += 1
            continue
        for grade in monster.get('grades') or []:
            row = [monster_id, grade.get('grade')]
            row.extend(grade.get(field) for field in GRADE_FIELDS)
            # The 2.73 archive carries the same empty shells the later versions
            # do. A row with no level or no life points renders as dashes.
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
    _save_db_to_dump(get_items_db_path(GAME_VERSION), GAME_VERSION)
    print('[dofus2] monster_grades: %d rows for %d monsters (%d archive entries '
          'this version does not name, %d empty rows dropped)'
          % (stored, count, skipped, empty))
    return 0


if __name__ == '__main__':
    sys.exit(main())
