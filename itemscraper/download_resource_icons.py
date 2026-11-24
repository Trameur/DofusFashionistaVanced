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
Each version records the source of every icon it wrote; an icon whose source
changed is fetched again and replaced when its picture differs.

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

import touch_channels

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)

DB_PATHS = [
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items.db'),
    os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_beta.db'),
]
RAW_DIRS = [CURRENT_DIR, os.path.join(CURRENT_DIR, 'beta')]
RAW_KINDS = ('resources', 'consumables', 'quest_items', 'equipment', 'cosmetics')

TOUCH_DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_touch.db')
TOUCH_CONFIG_URL = touch_channels.config_url('login')
TOUCH_FALLBACK_ASSETS_URL = ('https://dofustouch.cdn.ankama.com/assets/'
                             '3.2.4_sF,kf0I9t9aOjYb3X_EPiZJZYCo.brI5')

TOUCH_ICON_PATH = 'gfx/items/%d.png'

RETRO_DB_PATH = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp', 'items_retro.db')

SOURCE_RECORDS = {
    'dofus3': os.path.join(CURRENT_DIR, 'resource_icon_sources.json'),
    'touch': os.path.join(CURRENT_DIR, 'touch', 'resource_icon_sources.json'),
    'touchbeta': os.path.join(CURRENT_DIR, 'touchbeta', 'resource_icon_sources.json'),
    'dofus2': os.path.join(CURRENT_DIR, 'dofus2', 'resource_icon_sources.json'),
}


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


def touch_assets_url(channel=touch_channels.DEFAULT_CHANNEL):
    try:
        assets = requests.get(touch_channels.config_url(channel), timeout=30).json().get('assetsUrl')
    except Exception:
        assets = None
    return assets or TOUCH_FALLBACK_ASSETS_URL


def touch_items(channel=touch_channels.DEFAULT_CHANNEL):
    """The Items table of a channel's raw folder."""
    path = os.path.join(touch_channels.raw_dir(channel), 'Items_fr.json')
    with open(path, encoding='utf-8') as fh:
        return json.load(fh)


def touch_icon_paths(channel=touch_channels.DEFAULT_CHANNEL):
    """ankama id -> the icon path under the Touch assets, which a client update does not move."""
    return {int(item_id): TOUCH_ICON_PATH % item['iconId']
            for item_id, item in touch_items(channel).items() if item.get('iconId')}


def icons_that_differ_from_login(channel):
    """ankama id -> icon path for the rows of a channel whose (name, iconId) are not the login ones."""
    login = touch_items(touch_channels.DEFAULT_CHANNEL)
    changed = {}
    for item_id, item in touch_items(channel).items():
        if not item.get('iconId'):
            continue
        before = login.get(item_id) or {}
        if (item.get('nameId'), item['iconId']) != (before.get('nameId'), before.get('iconId')):
            changed[int(item_id)] = TOUCH_ICON_PATH % item['iconId']
    return changed


def rows_same_as_login(channel):
    """The ankama ids of a channel's rows whose (name, iconId) are the login ones, which keep the login icon."""
    login = touch_items(touch_channels.DEFAULT_CHANNEL)
    return {int(item_id) for item_id, item in touch_items(channel).items()
            if item.get('iconId') and item_id in login
            and (item.get('nameId'), item['iconId']) == (login[item_id].get('nameId'), login[item_id].get('iconId'))}


def touch_icon_urls(channel=touch_channels.DEFAULT_CHANNEL):
    assets = touch_assets_url(channel)
    return {ankama_id: '%s/%s' % (assets, path) for ankama_id, path in touch_icon_paths(channel).items()}


def read_sources(path):
    """ankama id -> the source its icon was written from; empty when nothing was recorded."""
    try:
        with open(path, encoding='utf-8') as fh:
            return {int(key): source for key, source in json.load(fh).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def write_sources(path, sources):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    partial = path + '.part'
    with open(partial, 'w', encoding='utf-8', newline='\n') as fh:
        json.dump({str(key): sources[key] for key in sorted(sources)}, fh, indent=1)
        fh.write('\n')
    os.replace(partial, path)


def http_fetch():
    session = requests.Session()

    def fetch(url):
        resp = session.get(url, timeout=30)
        return resp.status_code, resp.content
    return fetch


def icon_picture(content):
    return Image.open(io.BytesIO(content)).convert('RGBA').resize((60, 60))


def same_picture(path, picture):
    """Equal pixels whatever the encoding; colour under full transparency does not count."""
    try:
        with Image.open(path) as stored:
            stored = stored.convert('RGBA').convert('RGBa')
            return (stored.size == picture.size
                    and stored.tobytes() == picture.convert('RGBa').tobytes())
    except (OSError, ValueError):
        return False


def sync_icons(ids, urls, targets_root, sources, fetch, force=False, keys=None):
    """Fetch each icon whose recorded source changed or whose file is missing; write it where the picture differs."""
    keys = keys or urls
    counts = {'written': 0, 'same': 0, 'kept': 0, 'absent': 0, 'failed': 0}
    record = dict(sources)
    todo = sorted(i for i in ids if i in urls)
    for ankama_id in todo:
        key = keys.get(ankama_id, urls[ankama_id])
        targets = [os.path.join(t, '%d-60-60.png' % ankama_id) for t in targets_root]
        if (not force and sources.get(ankama_id) == key
                and all(os.path.exists(t) for t in targets)):
            counts['kept'] += 1
            continue
        try:
            status, content = fetch(urls[ankama_id])
            if status == 404:
                counts['absent'] += 1
                continue
            if status >= 400:
                raise IOError('HTTP %d for %s' % (status, urls[ankama_id]))
            picture = icon_picture(content)
            stale = [t for t in targets if not same_picture(t, picture)]
            for target in stale:
                picture.save(target)
            record[ankama_id] = key
            counts['written' if stale else 'same'] += 1
        except Exception as exc:
            counts['failed'] += 1
            print('failed %s: %s' % (ankama_id, exc))
        fetched = counts['written'] + counts['same']
        if fetched and fetched % 200 == 0:
            print('fetched %d/%d' % (fetched, len(todo)))
    return counts, record


def retro_icon_keys(raw_dir=None):
    """ankama id -> (type, gfx), the client clip address of each icon."""
    path = os.path.join(raw_dir or os.path.join(CURRENT_DIR, 'retro_raw'), 'items_fr.json')
    with open(path, encoding='utf-8') as fh:
        items = json.load(fh)['I']['u']
    return {int(item_id): (str(item['t']), str(item['g']))
            for item_id, item in items.items()
            if isinstance(item, dict)
            and item.get('g') is not None and item.get('t') is not None}


def run_retro(force, release='main'):
    """Render the retro ingredient icons from the client SWFs; needs java + ffdec."""
    from concurrent.futures import ThreadPoolExecutor
    from download_retro_monster_artworks import (
        download_manifest, load_fragment, find_tool, clip_differs)
    import download_retro_images as retro_items
    import retro_release
    beta = retro_release.is_beta(release)

    java = find_tool(None, 'JAVA_EXE', ['java'])
    ffdec_jar = os.environ.get('FFDEC_JAR')
    if not (java and ffdec_jar and os.path.exists(ffdec_jar)):
        print('WARNING: java + ffdec.jar (JAVA_EXE/FFDEC_JAR) are needed to '
              'render the retro icons; skipping, the committed PNGs stay.')
        return

    ids = ingredient_ids([str(retro_release.db_path(release)) if beta else RETRO_DB_PATH])
    keys = retro_icon_keys(str(retro_release.raw_dir(release)) if beta else None)
    targets_root = target_dirs(retro_release.version_key(release))
    for target in targets_root:
        os.makedirs(target, exist_ok=True)

    manifest = None
    reused = 0
    if beta:
        main_keys = retro_icon_keys()
        main_root = target_dirs('retro')[0]
        manifest = download_manifest(release)
        files, chunk_map = load_fragment(manifest, 'classic')
        main_files, _main_chunks = load_fragment(download_manifest(), 'classic')

    todo = {}
    skipped = no_key = 0
    for ankama_id in sorted(ids):
        key = keys.get(ankama_id)
        if key is None:
            no_key += 1
            continue
        if beta:
            path = '%s%s/%s.swf' % (retro_items.ICON_PREFIX, key[0], key[1])
            if (main_keys.get(ankama_id) == key
                    and os.path.exists(os.path.join(main_root, '%d-60-60.png' % ankama_id))
                    and not clip_differs(path, files, main_files)):
                reused += 1
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
    if beta:
        retro_release.notice(
            'resource icons: %d ingredients, %d clips to render for %d ids, %d reuse the icon of main, '
            '%d already rendered for the beta, %d without a clip'
            % (len(ids), len(todo), sum(len(v) for v in todo.values()), reused, skipped, no_key))
    if not todo:
        print('done: nothing to render')
        return

    if manifest is None:
        manifest = download_manifest()
        files, chunk_map = load_fragment(manifest, 'classic')
    cache_dir = (retro_release.raw_dir(release) / 'item_icons') if beta else retro_items.CACHE_DIR
    cache_dir.mkdir(parents=True, exist_ok=True)

    counts = {'ok': 0, 'missing': 0, 'empty': 0, 'error': 0}
    written = 0

    def process(key):
        type_id, gfx = key
        entry = files.get('%s%s/%s.swf'
                          % (retro_items.ICON_PREFIX, type_id, gfx))
        if entry is None:
            return key, 'missing', None
        swf_path = cache_dir / ('%s_%s.swf' % (type_id, gfx))
        try:
            if not swf_path.exists():
                retro_items.download_file(entry, chunk_map, str(swf_path))
            png = retro_items.render_icon(swf_path, java, ffdec_jar)
            return key, ('ok' if png else 'empty'), png
        except Exception as exc:
            print('  ERROR %s/%s: %s' % (type_id, gfx, exc))
            return key, 'error', None

    with ThreadPoolExecutor(max_workers=1 if beta else 6) as pool:
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
    if beta:
        retro_release.notice('resource icons rendered for the beta: %s, ids written %d' % (counts, written))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=['dofus3', 'touch', 'retro', 'retrobeta', 'dofus2'],
                        help='dofus3 (default, shared with beta), touch, retro, retrobeta or dofus2')
    parser.add_argument('--force', action='store_true',
                        help='Fetch every icon again, whatever source it was written from')
    touch_channels.add_channel_argument(parser)
    args = parser.parse_args()

    if args.channel != touch_channels.DEFAULT_CHANNEL and args.game_version != 'touch':
        parser.error('--channel early only applies to --game-version touch')

    if args.game_version in ('retro', 'retrobeta'):
        import retro_release
        run_retro(args.force, retro_release.release_of(args.game_version))
        return

    keys = None
    record_key = args.game_version
    if args.game_version == 'touch':
        record_key = touch_channels.game_version(args.channel)
        if args.channel == touch_channels.DEFAULT_CHANNEL:
            ids = ingredient_ids([TOUCH_DB_PATH])
            keys = touch_icon_paths()
        else:
            ingredients = ingredient_ids([TOUCH_DB_PATH.replace('items_touch.db', 'items_%s.db' % record_key)])
            reused = ingredients & rows_same_as_login(args.channel)
            ids = ingredients - reused
            keys = icons_that_differ_from_login(args.channel)
            print('same name and icon as login, left to the login icon: %d' % len(reused))
        assets = touch_assets_url(args.channel)
        urls = {ankama_id: '%s/%s' % (assets, path) for ankama_id, path in keys.items()}
        targets_root = target_dirs(touch_channels.static_subdir(args.channel))
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

    record_path = SOURCE_RECORDS[record_key]
    counts, record = sync_icons(ids, urls, targets_root, read_sources(record_path),
                                http_fetch(), force=args.force, keys=keys)
    write_sources(record_path, record)
    print('done: %(written)d written, %(same)d fetched with the same picture, '
          '%(kept)d kept from the same source, %(absent)d absent at source, '
          '%(failed)d failed' % counts)
    if counts['failed'] and counts['failed'] > len(todo) // 10:
        sys.exit(1)


if __name__ == '__main__':
    main()
