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

"""Download the official icons of every recipe ingredient (resource pages).

Ingredient ids come from item_recipe_ingredient_names in items.db and
items_beta.db; icon URLs come from the dofusdude raw files (all_*_en.json,
image_urls.icon, 64px). Icons are stored by ANKAMA ID (not name: resource
names carry characters filenames cannot) under chardata/resources/60x60/,
shared by dofus3 and beta like the root items/ directory. Existing files are
skipped, so the step is cheap on re-runs.
"""

import argparse
import io
import json
import os
import sqlite3
import sys

import requests
from PIL import Image

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

DB_PATHS = [
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items.db'),
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_beta.db'),
]
RAW_DIRS = [CURRENT_DIR, os.path.join(CURRENT_DIR, 'beta')]
RAW_KINDS = ('resources', 'consumables', 'quest_items', 'equipment', 'cosmetics')

TARGET_DIRS = [
    os.path.join(ROOT, 'fashionsite', 'chardata', 'static', 'chardata', 'resources', '60x60'),
    os.path.join(ROOT, 'fashionsite', 'staticfiles', 'chardata', 'resources', '60x60'),
]


def ingredient_ids():
    ids = set()
    for db_path in DB_PATHS:
        if not os.path.exists(db_path):
            continue
        con = sqlite3.connect(db_path)
        try:
            rows = con.execute(
                'SELECT DISTINCT ingredient_ankama_id FROM item_recipe_ingredient_names').fetchall()
        except sqlite3.OperationalError:
            rows = []
        con.close()
        ids.update(r[0] for r in rows)
    return ids


def icon_urls():
    urls = {}
    for raw_dir in RAW_DIRS:
        for kind in RAW_KINDS:
            path = os.path.join(raw_dir, 'all_%s_en.json' % kind)
            if not os.path.exists(path):
                continue
            with open(path, encoding='utf-8') as fh:
                data = json.load(fh)
            items = data.get('items') if isinstance(data, dict) else data
            for item in items or []:
                if not isinstance(item, dict):
                    continue
                url = (item.get('image_urls') or {}).get('icon')
                if url and item.get('ankama_id') not in urls:
                    urls[item['ankama_id']] = url
    return urls


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--force', action='store_true',
                        help='Redownload icons that already exist')
    args = parser.parse_args()

    ids = ingredient_ids()
    urls = icon_urls()
    for target in TARGET_DIRS:
        os.makedirs(target, exist_ok=True)

    todo = sorted(i for i in ids if i in urls)
    missing = sorted(i for i in ids if i not in urls)
    print('ingredients: %d | with icon url: %d | without: %d'
          % (len(ids), len(todo), len(missing)))
    if missing:
        print('no icon url (left without image): %s%s'
              % (missing[:20], '...' if len(missing) > 20 else ''))

    done = skipped = failed = 0
    session = requests.Session()
    for ankama_id in todo:
        fname = '%d-60-60.png' % ankama_id
        targets = [os.path.join(t, fname) for t in TARGET_DIRS]
        if not args.force and all(os.path.exists(t) for t in targets):
            skipped += 1
            continue
        try:
            resp = session.get(urls[ankama_id], timeout=30)
            resp.raise_for_status()
            img = Image.open(io.BytesIO(resp.content)).convert('RGBA')
            img = img.resize((60, 60))
            for target in targets:
                img.save(target)
            done += 1
        except Exception as exc:
            failed += 1
            print('failed %s: %s' % (ankama_id, exc))
        if done and done % 200 == 0:
            print('downloaded %d/%d' % (done, len(todo)))
    print('done: %d downloaded, %d already present, %d failed' % (done, skipped, failed))
    if failed and failed > len(todo) // 10:
        sys.exit(1)


if __name__ == '__main__':
    main()
