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

"""Download monster artwork as 96px WebP, named by Ankama id.

Usage: python download_monster_images.py [--game-version dofus3|touch]

dofus3 artwork comes from the DofusDB mirror, touch from the official Touch
assets CDN, which indexes by monster id. Retro artwork is handled by
download_retro_monster_artworks.py.
"""

import argparse
import io
import os
import sqlite3
import sys
from concurrent.futures import ThreadPoolExecutor

import requests
from PIL import Image

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

DB_PATHS = [
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items.db'),
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_beta.db'),
]
TOUCH_DB_PATHS = [
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_touch.db'),
]
# DofusDB names the artwork file by gfxId, not by monster id, so the id -> img
# mapping has to come from the monsters API.
DOFUSDB_MONSTERS_URL = 'https://api.dofusdb.fr/monsters?%%24limit=%d&%%24skip=%d'
PAGE_SIZE = 50
TOUCH_CONFIG_URL = 'https://dt-proxy-production-login.ankama-games.com/config.json'
TOUCH_FALLBACK_ASSETS_URL = ('https://dofustouch.cdn.ankama.com/assets/'
                             '3.2.4_sF,kf0I9t9aOjYb3X_EPiZJZYCo.brI5')
SIZE = 96


def target_dirs(version_subdir=''):
    parts = ['monsters'] + ([version_subdir] if version_subdir else []) + ['96']
    return [
        os.path.join(ROOT, 'fashionsite', 'chardata', 'static', 'chardata', *parts),
        os.path.join(ROOT, 'fashionsite', 'staticfiles', 'chardata', *parts),
    ]


def monster_ids(db_paths):
    ids = set()
    for db_path in db_paths:
        if not os.path.exists(db_path):
            continue
        con = sqlite3.connect(db_path)
        try:
            rows = con.execute(
                'SELECT DISTINCT monster_ankama_id FROM monster_names').fetchall()
        except sqlite3.OperationalError:
            rows = []
        con.close()
        ids.update(r[0] for r in rows)
    return ids


def image_urls(session):
    """id -> artwork URL for every monster DofusDB knows."""
    urls = {}
    skip = 0
    while True:
        resp = session.get(DOFUSDB_MONSTERS_URL % (PAGE_SIZE, skip), timeout=60)
        resp.raise_for_status()
        rows = resp.json().get('data', [])
        if not rows:
            break
        for row in rows:
            if row.get('id') is not None and row.get('img'):
                urls[row['id']] = row['img']
        skip += PAGE_SIZE
    return urls


def fetch_one(session, monster_id, url, dirs):
    name = '%d.webp' % monster_id
    if all(os.path.exists(os.path.join(d, name)) for d in dirs):
        return 'skip'
    if not url:
        return 'missing'
    try:
        resp = session.get(url, timeout=30)
    except requests.RequestException:
        return 'error'
    if resp.status_code != 200 or not resp.content:
        return 'missing'
    try:
        image = Image.open(io.BytesIO(resp.content))
        image.thumbnail((SIZE, SIZE), Image.LANCZOS)
        buffer = io.BytesIO()
        image.save(buffer, 'WEBP', quality=82, method=6)
    except Exception:
        return 'error'
    for directory in dirs:
        with open(os.path.join(directory, name), 'wb') as fh:
            fh.write(buffer.getvalue())
    return 'ok'


def touch_image_urls(session, ids):
    try:
        assets = session.get(TOUCH_CONFIG_URL, timeout=30).json().get('assetsUrl')
    except Exception:
        assets = None
    assets = assets or TOUCH_FALLBACK_ASSETS_URL
    return {mid: '%s/gfx/monsters/%d.png' % (assets, mid) for mid in ids}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-version', default='dofus3',
                        choices=['dofus3', 'touch'])
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()

    subdir = 'touch' if args.game_version == 'touch' else ''
    dirs = target_dirs(subdir)
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)

    db_paths = TOUCH_DB_PATHS if args.game_version == 'touch' else DB_PATHS
    ids = sorted(monster_ids(db_paths))
    print('monsters to check: %d' % len(ids))
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (DofusFashionista asset sync)'

    if args.game_version == 'touch':
        urls = touch_image_urls(session, ids)
        print('touch cdn candidates: %d (missing ones just 403/404)' % len(urls))
    else:
        urls = image_urls(session)
        print('dofusdb knows artwork for %d monsters' % len(urls))

    counts = {'ok': 0, 'skip': 0, 'missing': 0, 'error': 0}
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for result in pool.map(
                lambda mid: fetch_one(session, mid, urls.get(mid), dirs), ids):
            counts[result] += 1
            done = sum(counts.values())
            if done % 500 == 0:
                print('  %d/%d (%s)' % (done, len(ids), counts))
    print('done: %s' % counts)
    return 0 if counts['error'] == 0 else 1


if __name__ == '__main__':
    sys.exit(main())
