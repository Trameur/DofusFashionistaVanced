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

"""Download the icons of every recipe ingredient into chardata/resources/.

Icons are named by Ankama id: resource names carry characters filenames cannot.

Usage (from itemscraper/):
    python download_resource_icons.py [--game-version dofus3|touch|retro|dofus2]
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
TOUCH_CONFIG_URL = 'https://dt-proxy-production-login.ankama-games.com/config.json'
TOUCH_FALLBACK_ASSETS_URL = ('https://dofustouch.cdn.ankama.com/assets/'
                             '3.2.4_sF,kf0I9t9aOjYb3X_EPiZJZYCo.brI5')

RETRO_DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_retro.db')


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


def icon_urls(raw_dirs=RAW_DIRS):
    urls = {}
    for raw_dir in raw_dirs:
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


def retro_icon_keys():
    """ankama id -> (type, gfx), the client clip address of each icon."""
    path = os.path.join(CURRENT_DIR, 'retro_raw', 'items_fr.json')
    with open(path, encoding='utf-8') as fh:
        items = json.load(fh)['I']['u']
    return {int(item_id): (str(item['t']), str(item['g']))
            for item_id, item in items.items()
            if isinstance(item, dict)
            and item.get('g') is not None and item.get('t') is not None}


def run_retro(force):
    """Render the retro ingredient icons from the client SWFs; needs java + ffdec."""
    from concurrent.futures import ThreadPoolExecutor
    from download_retro_monster_artworks import (
        download_manifest, load_fragment, find_tool)
    import download_retro_images as retro_items

    java = find_tool(None, 'JAVA_EXE', ['java'])
    ffdec_jar = os.environ.get('FFDEC_JAR')
    if not (java and ffdec_jar and os.path.exists(ffdec_jar)):
        print('WARNING: java + ffdec.jar (JAVA_EXE/FFDEC_JAR) are needed to '
              'render the retro icons; skipping, the committed PNGs stay.')
        return

    ids = ingredient_ids([RETRO_DB_PATH])
    keys = retro_icon_keys()
    targets_root = target_dirs('retro')
    for target in targets_root:
        os.makedirs(target, exist_ok=True)

    todo = {}
    skipped = no_key = 0
    for ankama_id in sorted(ids):
        key = keys.get(ankama_id)
        if key is None:
            no_key += 1
            continue
        targets = [os.path.join(t, '%d-60-60.png' % ankama_id)
                   for t in targets_root]
        if not force and all(os.path.exists(t) for t in targets):
            skipped += 1
            continue
        todo.setdefault(key, []).append(ankama_id)
    print('ingredients: %d | to render: %d icons for %d ids | already '
          'present: %d | no type/gfx: %d'
          % (len(ids), len(todo), sum(len(v) for v in todo.values()),
             skipped, no_key))
    if not todo:
        print('done: nothing to render')
        return

    manifest = download_manifest()
    files, chunk_map = load_fragment(manifest, 'classic')
    retro_items.CACHE_DIR.mkdir(parents=True, exist_ok=True)

    counts = {'ok': 0, 'missing': 0, 'empty': 0, 'error': 0}
    written = 0

    def process(key):
        type_id, gfx = key
        entry = files.get('%s%s/%s.swf'
                          % (retro_items.ICON_PREFIX, type_id, gfx))
        if entry is None:
            return key, 'missing', None
        swf_path = retro_items.CACHE_DIR / ('%s_%s.swf' % (type_id, gfx))
        try:
            if not swf_path.exists():
                retro_items.download_file(entry, chunk_map, str(swf_path))
            png = retro_items.render_icon(swf_path, java, ffdec_jar)
            return key, ('ok' if png else 'empty'), png
        except Exception as exc:
            print('  ERROR %s/%s: %s' % (type_id, gfx, exc))
            return key, 'error', None

    with ThreadPoolExecutor(max_workers=6) as pool:
        for key, status, png in pool.map(process, sorted(todo)):
            counts[status] += 1
            if png:
                for ankama_id in todo[key]:
                    for target in targets_root:
                        with open(os.path.join(
                                target, '%d-60-60.png' % ankama_id),
                                'wb') as fh:
                            fh.write(png)
                    written += 1
            done = sum(counts.values())
            if done % 250 == 0:
                print('  %d/%d %s' % (done, len(todo), counts))
    print('done: renders=%s ids written=%d' % (counts, written))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=['dofus3', 'touch', 'retro', 'dofus2'],
                        help='dofus3 (default, shared with beta), touch, retro or dofus2')
    parser.add_argument('--force', action='store_true',
                        help='Redownload icons that already exist')
    args = parser.parse_args()

    if args.game_version == 'retro':
        run_retro(args.force)
        return

    if args.game_version == 'touch':
        ids = ingredient_ids([TOUCH_DB_PATH])
        urls = touch_icon_urls()
        targets_root = target_dirs('touch')
    elif args.game_version == 'dofus2':
        dofus2_db = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_dofus2.db')
        ids = ingredient_ids([dofus2_db])
        urls = icon_urls([os.path.join(CURRENT_DIR, 'dofus2')])
        targets_root = target_dirs('dofus2')
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

    done = skipped = failed = absent = 0
    session = requests.Session()
    for ankama_id in todo:
        fname = '%d-60-60.png' % ankama_id
        targets = [os.path.join(t, fname) for t in targets_root]
        if not args.force and all(os.path.exists(t) for t in targets):
            skipped += 1
            continue
        try:
            resp = session.get(urls[ankama_id], timeout=30)
            if resp.status_code == 404:
                # 404 means the source has no icon for this item, not an error
                absent += 1
                continue
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
    print('done: %d downloaded, %d already present, %d absent at source, %d failed'
          % (done, skipped, absent, failed))
    if failed and failed > len(todo) // 10:
        sys.exit(1)


if __name__ == '__main__':
    main()
