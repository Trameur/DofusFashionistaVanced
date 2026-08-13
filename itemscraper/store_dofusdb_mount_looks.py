#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Store the skeleton, colours and scale behind each mount, from the DofusDB
mounts endpoint.

    python itemscraper/store_dofusdb_mount_looks.py [--game-version dofus3|beta]

Our mount items carry synthetic ankama_ids, so DofusDB's certificateId matches
nothing: mounts are paired on their name in all five languages.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
import urllib.request

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
sys.path.insert(0, CURRENT_DIR)

BASES = {
    'dofus3': 'https://api.dofusdb.fr',
    'beta': 'https://api.beta.dofusdb.fr',
}
DB_FILES = {
    'dofus3': 'items.db',
    'beta': 'items_beta.db',
}
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
PAGE_SIZE = 50


def fetch(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    return json.load(urllib.request.urlopen(request, timeout=60))


def iter_mounts(base_url):
    skip = 0
    while True:
        page = fetch('%s/mounts?$limit=%d&$skip=%d' % (base_url, PAGE_SIZE, skip))
        rows = page.get('data') or []
        if not rows:
            return
        for row in rows:
            yield row
        skip += PAGE_SIZE
        if skip >= page.get('total', 0):
            return


def parse_look(look):
    """`{bone||1=colour,2=colour|scale}` -> (bone, [hex colours], scale percent)."""
    if not look or not look.startswith('{') or not look.endswith('}'):
        return None
    fields = look[1:-1].split('|')
    if len(fields) < 4:
        return None
    bone, _skins, colours, scales = fields[0], fields[1], fields[2], fields[3]
    if not bone.isdigit():
        return None
    packed = []
    for part in colours.split(','):
        if '=' not in part:
            continue
        index, _, value = part.partition('=')
        value = value.strip()
        if not index.strip().isdigit():
            continue
        # A colour comes as a decimal or as #RRGGBB. A bare decimal like 498894
        # also reads as six hex digits, so hex only counts behind the sigil.
        if value.startswith('#') and re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            packed.append((int(index), int(value[1:], 16)))
        elif value.lstrip('-').isdigit():
            packed.append((int(index), int(value)))
    packed.sort()
    hexes = ['%06x' % (value & 0xFFFFFF) for _, value in packed]
    scale = int(scales) if scales.strip().lstrip('-').isdigit() else 100
    return int(bone), hexes, scale


def our_mounts(cursor):
    """Our mount items keyed by the tuple of their names in the five languages.

    English is the item's own name column; item_names only holds translations.
    """
    names = {}
    for item_id, name in cursor.execute(
            "SELECT id, name FROM items WHERE ankama_type = 'mounts'"):
        names[item_id] = {'en': (name or '').strip().lower()}
    for item_id, language, name in cursor.execute("""
            SELECT n.item, n.language, n.name FROM item_names n
            JOIN items i ON i.id = n.item
            WHERE i.ankama_type = 'mounts'"""):
        if item_id in names:
            names[item_id][language] = (name or '').strip().lower()
    keyed = {}
    for item_id, by_language in names.items():
        if all(by_language.get(language) for language in LANGUAGES):
            keyed[tuple(by_language[language] for language in LANGUAGES)] = item_id
    return keyed


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=sorted(BASES))
    args = parser.parse_args()

    db_path = os.path.join(ROOT, 'fashionistapulp', 'fashionistapulp',
                           DB_FILES[args.game_version])
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    keyed = our_mounts(cursor)
    print('%s: %d mount items with a name in all five languages'
          % (args.game_version, len(keyed)))

    cursor.execute('DROP TABLE IF EXISTS mount_looks')
    cursor.execute("""
        CREATE TABLE mount_looks (
            item INTEGER PRIMARY KEY,
            bone INTEGER NOT NULL,
            colors TEXT NOT NULL,
            scale INTEGER NOT NULL,
            FOREIGN KEY(item) REFERENCES items(id)
        )""")

    seen = matched = unparsed = 0
    bones = {}
    for mount in iter_mounts(BASES[args.game_version]):
        seen += 1
        parsed = parse_look(mount.get('look'))
        if parsed is None:
            unparsed += 1
            continue
        bone, colours, scale = parsed
        names = mount.get('name') or {}
        key = tuple((names.get(language) or '').strip().lower()
                    for language in LANGUAGES)
        item_id = keyed.get(key)
        if item_id is None:
            continue
        cursor.execute('INSERT OR REPLACE INTO mount_looks VALUES (?, ?, ?, ?)',
                       (item_id, bone, ','.join(colours), scale))
        bones[bone] = bones.get(bone, 0) + 1
        matched += 1

    uncovered = {}
    for item_id, name in cursor.execute(
            "SELECT i.id, i.name FROM items i WHERE i.ankama_type = 'mounts' "
            "AND i.id NOT IN (SELECT item FROM mount_looks)"):
        family = next((word for word in ('Seemyool', 'Dragoturkey', 'Rhineetle',
                                         'Kolophant', 'Skrot')
                       if word in name), 'other')
        uncovered[family] = uncovered.get(family, 0) + 1
    if uncovered:
        print('mount items left without a look: %d (%s)'
              % (sum(uncovered.values()),
                 ', '.join('%s %d' % pair for pair in sorted(uncovered.items()))))
    conn.commit()
    conn.close()

    from store_item_obtainment import _save_db_to_dump
    _save_db_to_dump(db_path, args.game_version)
    print('%d mounts read, %d paired on all five names, %d looks unreadable'
          % (seen, matched, unparsed))
    print('skeletons in use: %s' % dict(sorted(bones.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
