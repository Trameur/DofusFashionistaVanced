#!/usr/bin/env python3
"""store_item_skins.py - fill items.skin from the item to skin matching.

The character preview needs the skin behind each visible piece. That link is
not in the game data, so match_item_skins.py works it out from the art; this
writes the result into the version database and back into the dump.

    python itemscraper/store_item_skins.py --game-version dofus3 --input item_skins_dofus3.json

Only Hat, Cloak, Shield and Weapon carry a skin: nothing else shows on the
character. A match whose margin over the runner up is thin is skipped unless
--min-margin says otherwise, because a wrong skin is worse than none.
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)

VISIBLE_TYPES = ('Hat', 'Cloak', 'Shield', 'Weapon')


def add_column(conn):
    columns = [row[1] for row in conn.execute('PRAGMA table_info(items)')]
    if 'skin' not in columns:
        conn.execute('ALTER TABLE items ADD COLUMN skin INTEGER')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3')
    parser.add_argument('--input', required=True)
    parser.add_argument('--min-margin', type=float, default=0.05)
    args = parser.parse_args()

    matches = json.load(open(args.input, encoding='utf-8'))
    db_path = get_items_db_path(args.game_version)
    if args.game_version == 'dofus3':
        _load_db_from_dump(db_path, args.game_version)

    conn = sqlite3.connect(db_path)
    try:
        add_column(conn)
        known = {row[0]: row[1] for row in conn.execute("""
            SELECT i.ankama_id, i.id FROM items i JOIN item_types t ON t.id = i.type
            WHERE t.name IN (%s)""" % ','.join('?' * len(VISIBLE_TYPES)), VISIBLE_TYPES)}
        written = thin = absent = 0
        for ankama_id, match in matches.items():
            item_id = known.get(int(ankama_id))
            if item_id is None:
                absent += 1
                continue
            if match['score'] - match['runner_up'] < args.min_margin:
                thin += 1
                continue
            conn.execute('UPDATE items SET skin = ? WHERE id = ?', (match['skin'], item_id))
            written += 1
        conn.commit()
    finally:
        conn.close()

    if args.game_version == 'dofus3':
        _save_db_to_dump(db_path, args.game_version)
    print('%s: %d skins written, %d too close to call, %d not in this version'
          % (args.game_version, written, thin, absent))


if __name__ == '__main__':
    main()
