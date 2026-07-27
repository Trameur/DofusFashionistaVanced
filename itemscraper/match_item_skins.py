#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Work out which character skin belongs to each equipment item.

The game resolves this server side, so the client data has no item to look
link. What it does ship is the art on both sides: every item icon, and every
skin. Rendering a skin part and comparing it to the icon, inside a single slot
family, recovers the mapping.

    python itemscraper/match_item_skins.py --skins <dir> --icons <bundle> \
        --icon-map icon_map.json --cache skin_features.pkl --out item_skins.json

Rendering every part takes the best part of an hour, so --cache keeps the
features and later runs reuse them.

Writes {ankama_id: {skin, score, runner_up, name, type}}. A thin lead over the
runner up means the pick is a guess; store_item_skins.py drops those.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import pickle
import re
import sqlite3
import sys
import warnings

import numpy as np
import UnityPy
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UnityPy.config.FALLBACK_UNITY_VERSION = '2022.3.0f1'
try:
    from UnityPy.exceptions import UnityVersionFallbackWarning
    warnings.simplefilter('ignore', UnityVersionFallbackWarning)
except ImportError:
    warnings.filterwarnings('ignore', message='No valid Unity version found')

FAMILY_TO_TYPE = {
    'Chapeau': 'Hat',
    'Cape': 'Cloak',
    'Bouclier': 'Shield',
    'Arme': 'Weapon',
}
MASK_SIZE = 48
BINS = 6

# Colour does most of the work. More silhouette weight made every type worse
# when measured; weapons keep a bit because their icon is drawn at an angle.
SILHOUETTE_WEIGHT = {'Hat': 0.15, 'Shield': 0.15, 'Cloak': 0.15, 'Weapon': 0.35}
ROTATIONS = {'Weapon': (0, -30, -45, -60, 30, 45, 60)}


def silhouette(crop, angle=0):
    image = Image.fromarray((crop * 255).astype(np.uint8))
    if angle:
        image = image.rotate(angle, expand=True, fillcolor=0)
        turned = np.asarray(image) > 127
        if not turned.any():
            return None
        ys, xs = np.where(turned)
        image = Image.fromarray(
            (turned[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8))
    return np.asarray(image.resize((MASK_SIZE, MASK_SIZE), Image.BILINEAR)) > 127


def features(image, angles=(0,)):
    """(silhouettes, colour histogram). (None, None) if the image is blank."""
    arr = np.asarray(image.convert('RGBA')).astype(np.int16)
    solid = arr[..., 3] > 40
    if not solid.any():
        return None, None
    ys, xs = np.where(solid)
    crop = solid[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    masks = [m for m in (silhouette(crop, a) for a in angles) if m is not None]
    quantised = (arr[..., :3] * BINS // 256)[solid]
    keys = quantised[:, 0] * BINS * BINS + quantised[:, 1] * BINS + quantised[:, 2]
    counts = np.bincount(keys, minlength=BINS ** 3).astype(np.float32)
    return masks, counts / counts.sum()


def read_skins(directory, renderer):
    by_type = collections.defaultdict(list)
    names = sorted(n for n in os.listdir(directory) if re.match(r'skin_\d+\.bundle$', n))
    for done, name in enumerate(names, 1):
        skin_id = int(re.match(r'skin_(\d+)\.', name).group(1))
        try:
            skin = renderer.Skin(os.path.join(directory, name))
        except Exception:
            continue
        families = {re.sub(r'_\d+$', '', p) for p in skin.part_names()}
        family = next((f for f in families if f in FAMILY_TO_TYPE), None)
        if family is None:
            continue
        parts = []
        for part in skin.part_names():
            if not part.startswith(family):
                continue
            image = renderer.rasterise(skin, part, size=(220, 300), scale=6.0)
            if image is None:
                continue
            masks, colour = features(image)
            if masks:
                parts.append((masks[0], colour))
        if parts:
            by_type[FAMILY_TO_TYPE[family]].append((skin_id, parts))
        if done % 250 == 0:
            print('%d/%d skins read' % (done, len(names)), flush=True)
    return dict(by_type)


def read_icons(bundle_path):
    env = UnityPy.load(bundle_path)
    out = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        data = obj.read()
        if data.m_Name.isdigit():
            out[int(data.m_Name)] = data.image
    return out


def visible_items(db_path):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute("""
            SELECT i.ankama_id, i.name, t.name FROM items i
            JOIN item_types t ON t.id = i.type
            WHERE t.name IN ('Hat', 'Cloak', 'Shield', 'Weapon')
            """).fetchall()
    finally:
        conn.close()


def rank_skins(icon_masks, icon_colour, candidates, weight):
    scored = []
    for skin_id, parts in candidates:
        best = 0.0
        for mask, colour in parts:
            overlap = max(float((m & mask).sum()) / max(float((m | mask).sum()), 1.0)
                          for m in icon_masks)
            best = max(best, weight * overlap
                       + (1 - weight) * float(np.minimum(icon_colour, colour).sum()))
        scored.append((best, skin_id))
    scored.sort(reverse=True)
    return scored


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skins')
    parser.add_argument('--icons', required=True)
    parser.add_argument('--icon-map', required=True)
    parser.add_argument('--db', default='fashionistapulp/fashionistapulp/items.db')
    parser.add_argument('--renderer', default='skinmesh')
    parser.add_argument('--cache', help='where the rendered features are kept')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    if args.cache and os.path.exists(args.cache):
        with open(args.cache, 'rb') as fh:
            by_type = pickle.load(fh)
        print('features read from %s' % args.cache, flush=True)
    else:
        if not args.skins:
            raise SystemExit('--skins is needed when there is no cache')
        by_type = read_skins(args.skins, __import__(args.renderer))
        if args.cache:
            with open(args.cache, 'wb') as fh:
                pickle.dump(by_type, fh, protocol=4)
    for item_type, entries in sorted(by_type.items()):
        print('  %-8s %d skins' % (item_type, len(entries)), flush=True)

    icons = read_icons(args.icons)
    icon_of = {int(k): v for k, v in json.load(open(args.icon_map)).items()}

    result, unmatched = {}, 0
    items = visible_items(args.db)
    for done, (ankama_id, name, item_type) in enumerate(items, 1):
        image = icons.get(icon_of.get(ankama_id))
        candidates = by_type.get(item_type)
        if image is None or not candidates:
            unmatched += 1
            continue
        icon_masks, icon_colour = features(image, ROTATIONS.get(item_type, (0,)))
        if not icon_masks:
            unmatched += 1
            continue
        scored = rank_skins(icon_masks, icon_colour, candidates,
                            SILHOUETTE_WEIGHT.get(item_type, 0.15))
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        result[ankama_id] = {'skin': scored[0][1], 'score': round(scored[0][0], 4),
                             'runner_up': round(runner_up, 4), 'name': name,
                             'type': item_type}
        if done % 200 == 0:
            print('%d/%d items matched' % (done, len(items)), flush=True)

    json.dump(result, open(args.out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    print('matched %d items, %d without an icon or candidate' % (len(result), unmatched))


if __name__ == '__main__':
    main()
