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

"""Download the artwork of every monster that has an encyclopedia page.

Images are stored by ANKAMA ID as 96px WebP (artwork sources are 128px PNG,
WebP keeps the whole set in the tens of megabytes). Existing files are
skipped, so the step is cheap on re-runs.

Default (dofus3, shared with beta like the root items/ directory): monster
ids come from monster_names in items.db and items_beta.db; artwork comes from
the DofusDB asset mirror (api.dofusdb.fr/img/monsters/<id>.png, the same
source our spell audits already trust). Monsters missing there just stay
without a file and the site renders them without an image.

Other versions are NOT handled yet: Touch and Retro have their own asset
sources (Touch CDN gfx/monsters, Cyberia for 1.29) and must be wired
separately, never by pointing them at dofus3 artwork.
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
# The image file name is the monster's gfxId, NOT its id (monster 46 renders
# img/monsters/12.png): the id -> img mapping must come from the monsters API.
DOFUSDB_MONSTERS_URL = 'https://api.dofusdb.fr/monsters?%%24limit=%d&%%24skip=%d'
PAGE_SIZE = 50
SIZE = 96


def target_dirs():
    parts = ['monsters', '96']
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
    """id -> artwork URL for every monster DofusDB knows, via the paged API."""
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--game-version', default='dofus3', choices=['dofus3'])
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()

    dirs = target_dirs()
    for directory in dirs:
        os.makedirs(directory, exist_ok=True)

    ids = sorted(monster_ids(DB_PATHS))
    print('monsters to check: %d' % len(ids))
    session = requests.Session()
    session.headers['User-Agent'] = 'Mozilla/5.0 (DofusFashionista asset sync)'

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
