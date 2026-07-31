#!/usr/bin/env python3
"""store_item_skins.py - fill items.skin from the item to skin matching.

The character preview needs the skin behind each visible piece. That link is
not in the game data, so match_item_skins.py works it out from the art; this
writes the result into the version database and back into the dump.

    python itemscraper/store_item_skins.py --game-version dofus3 --input item_skins_dofus3.json

Only Hat, Cloak, Shield and Weapon carry a skin: nothing else shows on the
character. A match whose margin over the runner up is thin is skipped unless
--min-margin says otherwise, because a wrong skin is worse than none.

The matching takes hours, so the decisions it reached are kept in the repo as
`item_skins.json` and replayed with --input like any other run. Rebuilding a
database no longer means matching again.

    python itemscraper/store_item_skins.py --game-version dofus3 --export itemscraper/item_skins.json
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from item_skin_margins import MIN_MARGIN  # noqa: E402
from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)

VISIBLE_TYPES = ('Hat', 'Cloak', 'Shield', 'Weapon')


def add_column(conn):
    columns = [row[1] for row in conn.execute('PRAGMA table_info(items)')]
    if 'skin' not in columns:
        conn.execute('ALTER TABLE items ADD COLUMN skin INTEGER')


def clear_skins(conn):
    """Without this a match dropped by a later run keeps the old run's skin."""
    conn.execute("""
        UPDATE items SET skin = NULL WHERE type IN (
            SELECT id FROM item_types WHERE name IN (%s))"""
                 % ','.join('?' * len(VISIBLE_TYPES)), VISIBLE_TYPES)


def export(conn, path):
    """The decisions as they stand, ready to be replayed into a fresh database."""
    rows = conn.execute("""
        SELECT i.ankama_id, i.skin FROM items i JOIN item_types t ON t.id = i.type
        WHERE i.skin IS NOT NULL AND t.name IN (%s)
        ORDER BY i.ankama_id""" % ','.join('?' * len(VISIBLE_TYPES)),
                        VISIBLE_TYPES).fetchall()
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump({str(ankama_id): skin for ankama_id, skin in rows}, fh,
                  indent=1, sort_keys=True)
        fh.write('\n')
    return len(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3')
    parser.add_argument('--input')
    parser.add_argument('--export', help='write the stored skins out and stop')
    parser.add_argument('--min-margin', type=float,
                        help='one floor for every type; default is per type')
    args = parser.parse_args()

    if bool(args.input) == bool(args.export):
        parser.error('give either --input or --export')

    if args.export:
        conn = sqlite3.connect(get_items_db_path(args.game_version))
        try:
            print('%s: %d skins written to %s'
                  % (args.game_version, export(conn, args.export), args.export))
        finally:
            conn.close()
        return

    matches = json.load(open(args.input, encoding='utf-8'))
    db_path = get_items_db_path(args.game_version)
    if args.game_version == 'dofus3':
        _load_db_from_dump(db_path, args.game_version)

    conn = sqlite3.connect(db_path)
    try:
        add_column(conn)
        clear_skins(conn)
        known = {row[0]: (row[1], row[2]) for row in conn.execute("""
            SELECT i.ankama_id, i.id, t.name FROM items i JOIN item_types t ON t.id = i.type
            WHERE t.name IN (%s)""" % ','.join('?' * len(VISIBLE_TYPES)), VISIBLE_TYPES)}
        written = thin = absent = 0
        for ankama_id, match in matches.items():
            entry = known.get(int(ankama_id))
            if entry is None:
                absent += 1
                continue
            item_id, item_type = entry
            # A bare number is a decision already taken, with nothing left to
            # weigh; the matcher's own output carries the scores behind it.
            if isinstance(match, int):
                conn.execute('UPDATE items SET skin = ? WHERE id = ?', (match, item_id))
                written += 1
                continue
            floor = args.min_margin
            if floor is None:
                floor = MIN_MARGIN.get(item_type, 0.10)
            if not match.get('backed') and match['score'] - match['runner_up'] < floor:
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
