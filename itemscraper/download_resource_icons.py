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

Icons are stored by ANKAMA ID (not name: resource names carry characters
filenames cannot). Existing files are skipped, so the step is cheap on re-runs.

Default (dofus3, shared with beta like the root items/ directory):
ingredient ids come from item_recipe_ingredient_names in items.db and
items_beta.db; icon URLs come from the dofusdude raw files (all_*_en.json,
image_urls.icon, 64px); target is chardata/resources/60x60/.

--game-version touch: ids come from items_touch.db, icons from the official
Touch assets CDN (config.json assetsUrl + /gfx/items/<iconId>.png, iconId
from touch_raw/Items_fr.json); target is chardata/resources/touch/60x60/.
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

TOUCH_DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_touch.db')
TOUCH_CONFIG_URL = 'https://earlyproxy.touch.dofus.com/config.json'
TOUCH_FALLBACK_ASSETS_URL = ('https://dofustouch.cdn.ankama.com/assets/'
                             '3.2.1_lZbcGsQeC3PlPF-Fg,tut0oqPD5idyLwzy')


def target_dirs(version_subdir):
    parts = ['resources'] + ([version_subdir] if version_subdir else []) + ['60x60']
    return [
        os.path.join(ROOT, 'fashionsite', 'chardata', 'static', 'chardata', *parts),
        os.path.join(ROOT, 'fashionsite', 'staticfiles', 'chardata', *parts),
    ]


def ingredient_ids(db_paths):
    ids = set()
    for db_path in db_paths:
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


def touch_icon_urls():
    try:
        assets = requests.get(TOUCH_CONFIG_URL, timeout=30).json().get('assetsUrl')
    except Exception:
        assets = None
    assets = assets or TOUCH_FALLBACK_ASSETS_URL
    path = os.path.join(CURRENT_DIR, 'touch_raw', 'Items_fr.json')
    with open(path, encoding='utf-8') as fh:
        items = json.load(fh)
    return {int(item_id): '%s/gfx/items/%d.png' % (assets, item['iconId'])
            for item_id, item in items.items() if item.get('iconId')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=['dofus3', 'touch'],
                        help='dofus3 (default, shared with beta) or touch')
    parser.add_argument('--force', action='store_true',
                        help='Redownload icons that already exist')
    args = parser.parse_args()

    if args.game_version == 'touch':
        ids = ingredient_ids([TOUCH_DB_PATH])
        urls = touch_icon_urls()
        targets_root = target_dirs('touch')
    else:
        ids = ingredient_ids(DB_PATHS)
        urls = icon_urls()
        targets_root = target_dirs('')
    for target in targets_root:
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
        targets = [os.path.join(t, fname) for t in targets_root]
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
