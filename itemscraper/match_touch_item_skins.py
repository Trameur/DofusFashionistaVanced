#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Work out which Touch skin belongs to each Touch equipment item.

Same problem as match_item_skins.py solves for Dofus 3, and the same answer:
the game ships no item-to-skin link, but it ships the art on both sides, so
rendering a skin and comparing it to the item icon recovers the mapping. The
scoring is imported from that module rather than copied.

What differs is only the sources, and Touch makes both easy:

  skins : itemscraper/skins_touch/<id>.png, flat atlases of 64x64 tiles, so a
          frame is a crop and no Unity rendering is involved
  icons : <assetsUrl>/gfx/items/<iconId>.png, one request each, cached on disk

"skins/" holds every sprite the game draws, so most of the 3823 files are
scenery or monsters and will never match an item. They are left in the
candidate pool on purpose: dropping them by id band would bake in a guess,
whereas a wrong skin simply scores low and the margin floor in
store_item_skins.py already refuses a thin lead.

    python itemscraper/match_touch_item_skins.py --out item_skins_touch.json

Writes {ankama_id: {skin, score, runner_up, name, type}}, the shape
store_item_skins.py replays with --input.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
import urllib.request
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from match_item_skins import (  # noqa: E402  (sys.path set above)
    ROTATIONS, SILHOUETTE_WEIGHT, features, rank_skins)

CONFIG_URL = "https://dt-proxy-production-login.ankama-games.com/config.json"
FALLBACK_ASSETS_URL = ("https://dofustouch.cdn.ankama.com/assets/"
                       "3.2.11_XmqR,JLRxKAo0jK41tA_EnsXKrTBc47Z")
USER_AGENT = "Mozilla/5.0 Chrome/120"
VISIBLE_TYPES = ('Hat', 'Cloak', 'Shield', 'Weapon')
FRAMES_PER_SKIN = 6


def _get(url):
    request = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        return response.read()


def resolve_assets_url():
    try:
        return json.loads(_get(CONFIG_URL + '?lang=fr')).get(
            'assetsUrl') or FALLBACK_ASSETS_URL
    except Exception:  # noqa
        return FALLBACK_ASSETS_URL


def icon_image(assets_url, cache, icon_id):
    path = cache / ('%d.png' % icon_id)
    if not path.exists():
        try:
            path.write_bytes(_get('%s/gfx/items/%d.png' % (assets_url, icon_id)))
        except Exception:  # noqa
            return None
    try:
        return Image.open(path)
    except Exception:  # noqa
        return None


def skin_frames(path, limit=FRAMES_PER_SKIN):
    """The fullest cells of the atlas: the emptier ones show a sliver of art."""
    image = Image.open(path).convert('RGBA')
    width, height = image.size
    cells = []
    for row in range(height // 64):
        for column in range(width // 64):
            cell = image.crop((column * 64, row * 64,
                               column * 64 + 64, row * 64 + 64))
            solid = int((np.asarray(cell)[..., 3] > 40).sum())
            if solid:
                cells.append((solid, cell))
    cells.sort(key=lambda entry: -entry[0])
    return [cell for _solid, cell in cells[:limit]]


def load_candidates(skins_dir):
    candidates = []
    names = sorted((name for name in os.listdir(skins_dir)
                    if name.endswith('.png')),
                   key=lambda name: int(name[:-4]))
    for name in names:
        parts = []
        for frame in skin_frames(Path(skins_dir) / name):
            masks, colour = features(frame)
            if masks:
                parts.append((masks[0], colour))
        if parts:
            candidates.append((int(name[:-4]), parts))
    return candidates


def visible_items(db_path):
    conn = sqlite3.connect('file:%s?mode=ro' % db_path, uri=True)
    try:
        return conn.execute(
            "SELECT i.ankama_id, i.name, t.name FROM items i"
            " JOIN item_types t ON t.id = i.type"
            " WHERE t.name IN (%s) AND COALESCE(i.removed, 0) = 0"
            % ','.join('?' * len(VISIBLE_TYPES)), VISIBLE_TYPES).fetchall()
    finally:
        conn.close()


def icon_ids(raw_dir):
    with open(Path(raw_dir) / 'Items_fr.json', encoding='utf-8') as handle:
        raw = json.load(handle)
    rows = raw if isinstance(raw, list) else list(raw.values())
    return {row['id']: row.get('iconId') for row in rows
            if isinstance(row, dict) and 'id' in row}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skins', default=str(HERE / 'skins_touch'))
    parser.add_argument('--raw-dir', default=str(HERE / 'touch_raw'))
    parser.add_argument('--icon-cache', default=str(HERE / 'icons_touch'))
    parser.add_argument('--db', default=str(
        HERE.parent / 'fashionistapulp' / 'fashionistapulp' / 'items_touch.db'))
    parser.add_argument('--out', default=str(HERE / 'item_skins_touch.json'))
    parser.add_argument('--limit', type=int, help='stop after N items (a dry run)')
    args = parser.parse_args()

    cache = Path(args.icon_cache)
    cache.mkdir(parents=True, exist_ok=True)
    assets_url = resolve_assets_url()
    print('assets: %s' % assets_url)

    candidates = load_candidates(args.skins)
    print('%d skins, %d with drawable frames' %
          (len(os.listdir(args.skins)), len(candidates)))

    icons = icon_ids(args.raw_dir)
    items = visible_items(args.db)
    if args.limit:
        items = items[:args.limit]

    matches = {}
    no_icon = blank = 0
    for index, (ankama_id, name, type_name) in enumerate(items, 1):
        icon_id = icons.get(ankama_id)
        if not icon_id:
            no_icon += 1
            continue
        image = icon_image(assets_url, cache, icon_id)
        if image is None:
            no_icon += 1
            continue
        masks, colour = features(image, ROTATIONS.get(type_name, (0,)))
        if not masks:
            blank += 1
            continue
        scored = rank_skins(masks, colour, candidates,
                            SILHOUETTE_WEIGHT.get(type_name, 0.2))
        best, skin_id = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        matches[str(ankama_id)] = {
            'skin': skin_id, 'score': round(float(best), 4),
            'runner_up': round(float(runner_up), 4),
            'name': name, 'type': type_name,
        }
        if index % 100 == 0:
            print('  %d/%d' % (index, len(items)))

    with open(args.out, 'w', encoding='utf-8') as handle:
        json.dump(matches, handle, ensure_ascii=False, indent=1, sort_keys=True)
        handle.write('\n')
    print('matched %d items (%d without a usable icon, %d blank) -> %s'
          % (len(matches), no_icon, blank, args.out))


if __name__ == '__main__':
    sys.exit(main())
