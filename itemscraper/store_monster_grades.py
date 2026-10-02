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

"""Store the monster stats per grade for dofus3 or beta, from the datacenter dump.

    python store_monster_grades.py --game-version dofus3|beta --tag 3.6.12.16
"""

import argparse
import os
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from store_item_obtainment import _save_db_to_dump, get_items_db_path  # noqa: E402
from store_monster_spells import RAW_ROOT, _table  # noqa: E402

VERSIONS = ('dofus3', 'beta')
MIN_ROWS = 20000

COLUMNS = ('monster_ankama_id', 'grade', 'level', 'life_points', 'action_points',
           'movement_points', 'ap_dodge', 'mp_dodge', 'earth_resistance',
           'air_resistance', 'fire_resistance', 'water_resistance',
           'neutral_resistance', 'summoner_life_percent', 'wisdom',
           'earth_flat_resistance', 'air_flat_resistance', 'fire_flat_resistance',
           'water_flat_resistance', 'neutral_flat_resistance',
           'critical_damage_reduction', 'push_damage_reduction',
           'percent_damage_bonus', 'summoner_shares')
TEXT_COLUMNS = ('summoner_shares',)
NOT_SHARED = ('grade', 'level', 'life_points', 'summoner_life_percent')
NEVER_NULL = ('ap_dodge', 'mp_dodge', 'earth_resistance', 'air_resistance',
              'fire_resistance', 'water_resistance', 'neutral_resistance', 'wisdom')

COMMON_FIELDS = {
    'grade': 'grade', 'level': 'level', 'life_points': 'lifePoints',
    'action_points': 'actionPoints', 'movement_points': 'movementPoints',
    'summoner_life_percent': 'bonusCharacteristics.lifePoints', 'wisdom': 'wisdom',
}
SCHEMAS = {
    '3.6': {
        'ap_dodge': 'paDodge', 'mp_dodge': 'pmDodge',
        'earth_resistance': 'earthResistance', 'air_resistance': 'airResistance',
        'fire_resistance': 'fireResistance', 'water_resistance': 'waterResistance',
        'neutral_resistance': 'neutralResistance',
    },
    '3.7': {
        'ap_dodge': 'paLostDodge', 'mp_dodge': 'mpLostDodge',
        'earth_resistance': 'reductionEarth', 'air_resistance': 'reductionAir',
        'fire_resistance': 'reductionFire', 'water_resistance': 'reductionWater',
        'neutral_resistance': 'reductionNeutral',
        'earth_flat_resistance': 'reductionEarthFlat', 'air_flat_resistance': 'reductionAirFlat',
        'fire_flat_resistance': 'reductionFireFlat', 'water_flat_resistance': 'reductionWaterFlat',
        'neutral_flat_resistance': 'reductionNeutralFlat',
        'critical_damage_reduction': 'criticalDamageReduction',
        'push_damage_reduction': 'pushDamageReduction',
        'percent_damage_bonus': 'percentDamageBonus',
    },
}


class UnknownGradeSchema(ValueError):
    pass


def _value(grade, key):
    for part in key.split('.'):
        grade = grade[part]
    return grade


def _has(grade, key):
    try:
        _value(grade, key)
    except (KeyError, TypeError):
        return False
    return True


def grade_fields(monster_id, grade):
    """{column: key} of the one schema whose keys the grade carries."""
    matches = []
    for fields in SCHEMAS.values():
        fields = dict(COMMON_FIELDS, **fields)
        if all(_has(grade, key) for key in fields.values()):
            matches.append(fields)
    if len(matches) != 1:
        raise UnknownGradeSchema(
            'monster %s grade %s matches %d grade schemas, keys: %s'
            % (monster_id, grade.get('grade'), len(matches), ', '.join(sorted(grade))))
    return matches[0]


def summoner_shares(grade, fields):
    """'column:percent' pairs of the summoner's stats a summon also receives, or None."""
    bonus = grade['bonusCharacteristics']
    shares = ['%s:%s' % (column, bonus[fields[column]]) for column in COLUMNS
              if column in fields and column not in NOT_SHARED and bonus.get(fields[column])]
    return ','.join(shares) or None


def grade_row(monster_id, grade):
    """The monster_grades row of one dump grade, or None for an empty grade."""
    fields = grade_fields(monster_id, grade)
    values = {column: _value(grade, key) for column, key in fields.items()}
    values['summoner_shares'] = summoner_shares(grade, fields)
    if not values['summoner_life_percent'] or values['summoner_life_percent'] < 0:
        values['summoner_life_percent'] = None
    values['life_points'] = values['life_points'] or None
    if not values['level'] or not (values['life_points'] or values['summoner_life_percent']):
        return None
    for column in ('action_points', 'movement_points'):
        if values[column] is not None and values[column] < 0:
            values[column] = None
    values['monster_ankama_id'] = monster_id
    return tuple(values.get(column) for column in COLUMNS)


def dump_grades(monster):
    grades = monster.get('grades') or {}
    if isinstance(grades, dict):
        grades = grades.get('Array') or []
    return grades


def build_rows(monsters, known_ids):
    """(rows sorted by monster and grade, empty grades dropped, unnamed monsters)."""
    rows = []
    empty = unnamed = 0
    for monster_id, monster in monsters.items():
        if monster_id not in known_ids:
            unnamed += 1
            continue
        for grade in dump_grades(monster):
            row = grade_row(monster_id, grade)
            if row is None:
                empty += 1
            else:
                rows.append(row)
    rows.sort(key=lambda row: (row[0], row[1]))
    return rows, empty, unnamed


def check_rows(rows):
    if len(rows) < MIN_ROWS:
        raise ValueError('only %d grade rows, expected at least %d' % (len(rows), MIN_ROWS))
    for column in NEVER_NULL:
        index = COLUMNS.index(column)
        missing = [row[:2] for row in rows if row[index] is None]
        if missing:
            raise ValueError('%d grade rows have no %s, first: %s'
                             % (len(missing), column, missing[:5]))


def create_table_sql():
    lines = ['            %s %s%s,'
             % (column, 'TEXT' if column in TEXT_COLUMNS else 'INTEGER',
                ' NOT NULL' if column in COLUMNS[:2] else '')
             for column in COLUMNS]
    return ('CREATE TABLE monster_grades (\n%s\n'
            '            PRIMARY KEY (monster_ankama_id, grade)\n        )'
            % '\n'.join(lines))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=VERSIONS)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args(argv)

    monsters = _table(os.path.join(RAW_ROOT, args.tag, 'monsters.json'))
    db_path = get_items_db_path(args.game_version)
    conn = sqlite3.connect(db_path)
    try:
        known_ids = {row[0] for row in conn.execute(
            'SELECT DISTINCT monster_ankama_id FROM monster_names')}
        rows, empty, unnamed = build_rows(monsters, known_ids)
        check_rows(rows)
        conn.execute('BEGIN')
        conn.execute('DROP TABLE IF EXISTS monster_grades')
        conn.execute(create_table_sql())
        conn.executemany('INSERT INTO monster_grades VALUES (%s)'
                         % ', '.join('?' * len(COLUMNS)), rows)
        conn.commit()
    finally:
        conn.close()
    _save_db_to_dump(db_path, args.game_version)
    print('[%s] monster_grades from raw/%s: %d rows for %d monsters '
          '(%d empty grades dropped, %d monsters this version does not name)'
          % (args.game_version, args.tag, len(rows), len({row[0] for row in rows}),
             empty, unnamed))
    return 0


if __name__ == '__main__':
    sys.exit(main())
