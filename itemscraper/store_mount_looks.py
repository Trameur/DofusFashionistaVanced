#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Store the skeleton, colours and scale behind each Dofus 3 / Beta mount, from the datacenter dump.

    python store_mount_looks.py --game-version dofus3|beta --tag 3.7.14.18
"""

import argparse
import os
import re
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from store_item_obtainment import _save_db_to_dump, get_items_db_path  # noqa: E402
from store_monster_spells import RAW_ROOT, _labels, _table  # noqa: E402
from untranslated_tag import clean_display_name  # noqa: E402

VERSIONS = ('dofus3', 'beta')
LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')
MIN_ROWS = 200
FILES = ('mounts.json', 'items.json') + tuple('%s.json' % language for language in LANGUAGES)

CREATE_TABLE = """
        CREATE TABLE mount_looks (
            item INTEGER PRIMARY KEY,
            bone INTEGER NOT NULL,
            colors TEXT NOT NULL,
            scale INTEGER NOT NULL,
            FOREIGN KEY(item) REFERENCES items(id)
        )"""


def parse_look(look):
    """(bone, colour hexes in slot order, scale) from a {bone|skins|colours|scale} look, or None."""
    if not look or not look.startswith('{') or not look.endswith('}'):
        return None
    fields = look[1:-1].split('|')
    if len(fields) < 4:
        return None
    bone, colours, scales = fields[0], fields[2], fields[3]
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
        if value.startswith('#') and re.fullmatch(r'#[0-9A-Fa-f]{6}', value):
            packed.append((int(index), int(value[1:], 16)))
        elif value.lstrip('-').isdigit():
            packed.append((int(index), int(value)))
    packed.sort()
    hexes = ['%06x' % (value & 0xFFFFFF) for _, value in packed]
    scale = int(scales) if scales.strip().lstrip('-').isdigit() else 100
    return int(bone), hexes, scale


def name_key(labels, name_id):
    """The cleaned lowercase name in each language, in LANGUAGES order."""
    return tuple((clean_display_name(labels[language].get(str(name_id))) or '').strip().lower()
                 for language in LANGUAGES)


def read_dump(dump_dir):
    """({mount id: (name key, look)}, {item id: name key}) from one dump folder."""
    missing = [name for name in FILES if not os.path.isfile(os.path.join(dump_dir, name))]
    if missing:
        raise SystemExit('%s lacks %s' % (dump_dir, ', '.join(missing)))
    labels = _labels(dump_dir)
    mounts = {mount_id: (name_key(labels, mount.get('nameId')), mount.get('look'))
              for mount_id, mount in _table(os.path.join(dump_dir, 'mounts.json')).items()}
    items = {item_id: name_key(labels, item.get('nameId'))
             for item_id, item in _table(os.path.join(dump_dir, 'items.json')).items()}
    return mounts, items


def build_rows(mounts, item_names, our_items):
    """(rows, notices): one row per item whose five dump names are those of exactly one mount."""
    by_key = {}
    for mount_id, (key, _look) in mounts.items():
        by_key.setdefault(key, []).append(mount_id)
    claimed = {}
    for ankama_id in our_items:
        key = item_names.get(ankama_id)
        if key and any(key) and len(by_key.get(key, ())) == 1:
            claimed.setdefault(by_key[key][0], []).append(ankama_id)
    rows, notices = [], []
    for mount_id, ankama_ids in sorted(claimed.items()):
        if len(ankama_ids) > 1:
            notices.append('warning: mount %d has the names of items %s, no look stored'
                           % (mount_id, sorted(ankama_ids)))
            continue
        parsed = parse_look(mounts[mount_id][1])
        if parsed is None:
            notices.append('warning: mount %d has an unsupported look %r' % (mount_id, mounts[mount_id][1]))
            continue
        bone, colours, scale = parsed
        rows.append((our_items[ankama_ids[0]], bone, ','.join(colours), scale))
    for key, mount_ids in sorted(by_key.items()):
        if any(key) and len(mount_ids) > 1 and any(item_names.get(ankama_id) == key for ankama_id in our_items):
            notices.append('warning: mounts %s share one name, no look stored' % sorted(mount_ids))
    paired = {mounts[mount_id][0] for mount_id in claimed}
    for ankama_id in sorted(our_items):
        key = item_names.get(ankama_id)
        if not key or not any(key) or key in paired or len(by_key.get(key, ())) > 1:
            continue
        for mount_id, (mount_key, _look) in sorted(mounts.items()):
            same = [language for language, ours, theirs in zip(LANGUAGES, key, mount_key) if ours and ours == theirs]
            if same:
                notices.append('warning: item %d and mount %d share their %s name only, no look stored'
                               % (ankama_id, mount_id, ', '.join(same)))
    rows.sort()
    return rows, notices


def check_rows(rows):
    """Refuse to replace the table with fewer than MIN_ROWS rows."""
    if len(rows) < MIN_ROWS:
        raise ValueError('only %d mount looks, fewer than %d: table left as it was' % (len(rows), MIN_ROWS))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=VERSIONS)
    parser.add_argument('--tag', required=True)
    args = parser.parse_args(argv)

    mounts, item_names = read_dump(os.path.join(RAW_ROOT, args.tag))
    db_path = get_items_db_path(args.game_version)
    conn = sqlite3.connect(db_path)
    try:
        our_items = dict(conn.execute("SELECT ankama_id, id FROM items WHERE ankama_type = 'mounts'"))
        rows, notices = build_rows(mounts, item_names, our_items)
        check_rows(rows)
        conn.execute('BEGIN')
        conn.execute('DROP TABLE IF EXISTS mount_looks')
        conn.execute(CREATE_TABLE)
        conn.executemany('INSERT INTO mount_looks VALUES (?, ?, ?, ?)', rows)
        conn.commit()
    finally:
        conn.close()
    _save_db_to_dump(db_path, args.game_version)
    for line in notices:
        print(line)
    bones = {}
    for _item, bone, _colours, _scale in rows:
        bones[bone] = bones.get(bone, 0) + 1
    print('stored %d mount looks from raw/%s: %d mount items have none, %d mounts.json entries pair with no item'
          % (len(rows), args.tag, len(our_items) - len(rows), len(mounts) - len(rows)))
    print('skeletons: %s' % ', '.join('%d x%d' % pair for pair in sorted(bones.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
