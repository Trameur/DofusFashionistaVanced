#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Work out which character skin belongs to each equipment item.

The game resolves this server side, so the client data has no item to look
link. What it does ship is the art on both sides: every item icon, and every
skin. Rendering a skin part and comparing it to the icon, inside a single slot
family, recovers the mapping. Silhouette and colour are scored together
because neither alone separates similar pieces.

    python itemscraper/match_item_skins.py --skins <dir> --icons <bundle> \
        --icon-map icon_map.json --out item_skins.json

Writes {ankama_id: {skin, score, runner_up, name}}. A thin margin over the
runner up means the pick is a guess; store_item_skins.py drops those.
"""
from __future__ import annotations

import argparse
import collections
import json
import os
import re
import sqlite3
import sys

import numpy as np
import UnityPy
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

UnityPy.config.FALLBACK_UNITY_VERSION = '2022.3.0f1'

FAMILY_TO_TYPE = {
    'Chapeau': 'Hat',
    'Cape': 'Cloak',
    'Bouclier': 'Shield',
    'Arme': 'Weapon',
}
MASK_SIZE = 48
BINS = 6
SILHOUETTE_WEIGHT = 0.5


def features(image):
    """(silhouette normalised to a square, colour histogram) or (None, None)."""
    arr = np.asarray(image.convert('RGBA')).astype(np.int16)
    solid = arr[..., 3] > 40
    if not solid.any():
        return None, None
    ys, xs = np.where(solid)
    crop = Image.fromarray(
        (solid[ys.min():ys.max() + 1, xs.min():xs.max() + 1] * 255).astype(np.uint8))
    mask = np.asarray(crop.resize((MASK_SIZE, MASK_SIZE), Image.BILINEAR)) > 127
    quantised = (arr[..., :3] * BINS // 256)[solid]
    keys = quantised[:, 0] * BINS * BINS + quantised[:, 1] * BINS + quantised[:, 2]
    counts = np.bincount(keys, minlength=BINS ** 3).astype(np.float64)
    return mask, counts / counts.sum()


def score(icon, candidate):
    mask_a, colour_a = icon
    mask_b, colour_b = candidate
    union = float((mask_a | mask_b).sum())
    iou = float((mask_a & mask_b).sum()) / union if union else 0.0
    overlap = float(np.minimum(colour_a, colour_b).sum())
    return SILHOUETTE_WEIGHT * iou + (1 - SILHOUETTE_WEIGHT) * overlap


def read_skins(directory, renderer):
    """{item type: [(skin id, features per part)]}, keeping only wearable art."""
    by_type = collections.defaultdict(list)
    names = sorted(n for n in os.listdir(directory) if re.match(r'skin_\d+\.bundle$', n))
    for done, name in enumerate(names, 1):
        skin_id = int(re.match(r'skin_(\d+)\.', name).group(1))
        path = os.path.join(directory, name)
        try:
            skin = renderer.Skin(path)
        except Exception:
            continue
        families = {re.sub(r'_\d+$', '', p) for p in skin.part_names()}
        item_type = next((FAMILY_TO_TYPE[f] for f in families if f in FAMILY_TO_TYPE), None)
        if item_type is None:
            continue
        family = next(f for f in families if f in FAMILY_TO_TYPE)
        parts = []
        for part in skin.part_names():
            if not part.startswith(family):
                continue
            image = renderer.rasterise(skin, part, size=(220, 300), scale=6.0)
            if image is None:
                continue
            mask, colour = features(image)
            if mask is not None:
                parts.append((mask, colour))
        if parts:
            by_type[item_type].append((skin_id, parts))
        if done % 250 == 0:
            print('%d/%d skins read' % (done, len(names)), flush=True)
    return by_type


def read_icons(bundle_path):
    env = UnityPy.load(bundle_path)
    out = {}
    for obj in env.objects:
        if obj.type.name != 'Texture2D':
            continue
        data = obj.read()
        if not data.m_Name.isdigit():
            continue
        mask, colour = features(data.image)
        if mask is not None:
            out[int(data.m_Name)] = (mask, colour)
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skins', required=True)
    parser.add_argument('--icons', required=True)
    parser.add_argument('--icon-map', required=True)
    parser.add_argument('--db', default='fashionistapulp/fashionistapulp/items.db')
    parser.add_argument('--renderer', default='skinmesh',
                        help='module exposing Skin and rasterise')
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    renderer = __import__(args.renderer)

    print('reading skins', flush=True)
    by_type = read_skins(args.skins, renderer)
    for item_type, entries in sorted(by_type.items()):
        print('  %-8s %d skins' % (item_type, len(entries)), flush=True)

    print('reading icons', flush=True)
    icons = read_icons(args.icons)
    icon_of = {int(k): v for k, v in json.load(open(args.icon_map)).items()}
    print('%d icons' % len(icons), flush=True)

    result, unmatched = {}, 0
    items = visible_items(args.db)
    for done, (ankama_id, name, item_type) in enumerate(items, 1):
        icon = icons.get(icon_of.get(ankama_id))
        candidates = by_type.get(item_type)
        if icon is None or not candidates:
            unmatched += 1
            continue
        scored = sorted(((max(score(icon, part) for part in parts), skin_id)
                         for skin_id, parts in candidates), reverse=True)
        best = scored[0]
        runner_up = scored[1][0] if len(scored) > 1 else 0.0
        result[ankama_id] = {'skin': best[1], 'score': round(best[0], 4),
                             'runner_up': round(runner_up, 4), 'name': name}
        if done % 200 == 0:
            print('%d/%d items matched' % (done, len(items)), flush=True)

    json.dump(result, open(args.out, 'w', encoding='utf-8'), indent=1, ensure_ascii=False)
    thin = sum(1 for r in result.values() if r['score'] - r['runner_up'] < 0.05)
    print('matched %d items, %d without an icon or candidate' % (len(result), unmatched))
    print('%d have a margin under 0.05 and need review' % thin)


if __name__ == '__main__':
    main()
