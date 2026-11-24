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

"""Store where each Touch monster can be found into items_touch.db, from the client's SubAreas table; python store_touch_monster_subareas.py [--download] from itemscraper/."""

import argparse
import json
import os
import sqlite3
import sys

import touch_channels

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
KEEP_FIELDS = ('id', 'nameId', 'areaId', 'level', 'monsters')


def raw_path(lang, channel=touch_channels.DEFAULT_CHANNEL):
    return os.path.join(touch_channels.raw_dir(channel), 'SubAreas_%s.json' % lang)


def db_path(channel=touch_channels.DEFAULT_CHANNEL):
    return os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                        'items_%s.db' % touch_channels.game_version(channel))


def download(channel=touch_channels.DEFAULT_CHANNEL):
    sys.path.insert(0, CURRENT_DIR)
    import requests
    from download_touch_data import resolve_data_url, served_languages

    data_url = resolve_data_url('fr', channel)
    # Touch answers a language it no longer serves with English and no marker; an empty served set means unreadable, and nothing is skipped
    served = served_languages('fr', channel)
    for lang in LANGUAGES:
        if served and lang not in served:
            print('%s: not served by the %s channel, keeping the file on disk'
                  % (lang, channel))
            continue
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
        os.makedirs(touch_channels.raw_dir(channel), exist_ok=True)
        with open(raw_path(lang, channel), 'w', encoding='utf-8') as out:
            json.dump(filtered, out, ensure_ascii=False)
        print('%s: %d subareas saved' % (lang, len(filtered)))
    if channel != touch_channels.DEFAULT_CHANNEL:
        import seed_unserved_language
        seed_unserved_language.seed(channel, ['SubAreas'])


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--download', action='store_true',
                        help='Refresh touch_raw/SubAreas_<lang>.json from '
                             'the live proxy first')
    touch_channels.add_channel_argument(parser)
    args = parser.parse_args()
    channel = args.channel
    key = touch_channels.game_version(channel)

    if args.download or not os.path.exists(raw_path('fr', channel)):
        download(channel)

    conn = sqlite3.connect(db_path(channel))
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
        path = raw_path(lang, channel)
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
    print('stored %d subarea rows for %d %s monsters' % (stored, len(matched), key))
    # The pipeline's load-db rebuilds the db from the dump.
    sys.path.insert(0, CURRENT_DIR)
    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(db_path(channel), key)
    print('%s dump refreshed' % key)
    return 0


if __name__ == '__main__':
    sys.exit(main())
