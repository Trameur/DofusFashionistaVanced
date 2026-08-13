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

"""Store where each Touch monster can be found into items_touch.db.

The client's SubAreas table (POST /data/map {"class": "SubAreas"}) carries per
subarea its localized nameId and the monster ids that spawn there; inverted
here into monster -> [subarea names], per language. A filtered snapshot lives
in touch_raw/SubAreas_<lang>.json.

Usage (from itemscraper/):
    python store_touch_monster_subareas.py [--download]
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
RAW_DIR = os.path.join(CURRENT_DIR, 'touch_raw')

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
KEEP_FIELDS = ('id', 'nameId', 'areaId', 'level', 'monsters')


def raw_path(lang):
    return os.path.join(RAW_DIR, 'SubAreas_%s.json' % lang)


def download():
    sys.path.insert(0, CURRENT_DIR)
    import requests
    from download_touch_data import resolve_data_url

    data_url = resolve_data_url()
    for lang in LANGUAGES:
        response = requests.post(
            '%s/data/map' % data_url,
            json={'class': 'SubAreas', 'lang': lang},
            headers={'User-Agent': 'Mozilla/5.0'}, timeout=120)
        response.raise_for_status()
        table = response.json()
        filtered = {
            key: {field: record.get(field) for field in KEEP_FIELDS}
            for key, record in table.items()
            if isinstance(record, dict)
        }
        with open(raw_path(lang), 'w', encoding='utf-8') as out:
            json.dump(filtered, out, ensure_ascii=False)
        print('%s: %d subareas saved' % (lang, len(filtered)))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true',
                        help='Refresh touch_raw/SubAreas_<lang>.json from '
                             'the live proxy first')
    args = parser.parse_args()

    if args.download or not os.path.exists(raw_path('fr')):
        download()

    conn = sqlite3.connect(DB_PATH)
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
    for lang in LANGUAGES:
        path = raw_path(lang)
        if not os.path.exists(path):
            print('WARNING: %s missing, skipping %s' % (path, lang))
            continue
        with open(path, encoding='utf-8') as fh:
            table = json.load(fh)
        per_monster = {}
        for record in sorted(table.values(), key=lambda r: r.get('id') or 0):
            name = record.get('nameId')
            if not name:
                continue
            for monster_id in record.get('monsters') or []:
                if monster_id in known_ids:
                    per_monster.setdefault(monster_id, [])
                    if name not in per_monster[monster_id]:
                        per_monster[monster_id].append(name)
        for monster_id, names in per_monster.items():
            matched.add(monster_id)
            for position, name in enumerate(names):
                cursor.execute(
                    'INSERT OR REPLACE INTO monster_subareas VALUES (?,?,?,?)',
                    (monster_id, lang, position, name))
                stored += 1
    conn.commit()
    conn.close()
    print('stored %d subarea rows for %d touch monsters' % (stored, len(matched)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
