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

The other versions replay those same decisions by ankama id, but they renumbered
part of their catalogue, so `item_skins_by_name.json` keys the same decisions by
type and name and --names picks up what the ids miss.

    python itemscraper/store_item_skins.py --game-version dofus3 --export-names itemscraper/item_skins_by_name.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from item_skin_margins import MIN_MARGIN  # noqa: E402
from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)

VISIBLE_TYPES = ('Hat', 'Cloak', 'Shield', 'Weapon')

# Our own numbering of same-named items, which is not part of the game name.
DISAMBIGUATION = re.compile(r'\s*\(#\d+\)\s*$')


def same_item(name, other):
    """Ankama ids are only shared where the versions share an item.

    Dofus 2 does share them: 974 of its 1029 matches carry the exact Dofus 3
    name and the rest differ only by our numbering. Touch does not: 55 of its
    667 are a different item under the same id, Karne Rider Blade against
    Gob-Trotter Blade, so the name is what decides.
    """
    if not name or not other:
        return False
    return (DISAMBIGUATION.sub('', name).casefold()
            == DISAMBIGUATION.sub('', other).casefold())


def flat_name(name):
    """Names differ only by our numbering and by case across versions."""
    return DISAMBIGUATION.sub('', name or '').casefold().strip()


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


def names_index(conn):
    """The same decisions keyed by type and name, for a renumbered catalogue.

    A name carrying two different skins is left out rather than guessed at; in
    the Dofus 3 catalogue there is none.
    """
    rows = conn.execute("""
        SELECT t.name, i.name, i.skin FROM items i JOIN item_types t ON t.id = i.type
        WHERE i.skin IS NOT NULL AND t.name IN (%s)""" % ','.join('?' * len(VISIBLE_TYPES)),
                        VISIBLE_TYPES).fetchall()
    seen = {}
    for item_type, name, skin in rows:
        seen.setdefault(item_type, {}).setdefault(flat_name(name), set()).add(skin)
    return {item_type: {name: skins.pop()
                        for name, skins in names.items() if len(skins) == 1}
            for item_type, names in seen.items()}


def export_names(conn, path):
    index = names_index(conn)
    with open(path, 'w', encoding='utf-8') as fh:
        json.dump(index, fh, indent=1, sort_keys=True, ensure_ascii=False)
        fh.write('\n')
    return sum(len(names) for names in index.values())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3')
    parser.add_argument('--input')
    parser.add_argument('--export', help='write the stored skins out and stop')
    parser.add_argument('--export-names', help='write them keyed by name and stop')
    parser.add_argument('--min-margin', type=float,
                        help='one floor for every type; default is per type')
    parser.add_argument('--names',
                        help='skins by type and name, for the items whose ankama'
                             ' id this version renumbered')
    args = parser.parse_args()

    written = args.export or args.export_names
    if bool(args.input) == bool(written):
        parser.error('give either --input or --export/--export-names')

    if written:
        conn = sqlite3.connect(get_items_db_path(args.game_version))
        try:
            count = (export(conn, args.export) if args.export
                     else export_names(conn, args.export_names))
            print('%s: %d skins written to %s' % (args.game_version, count, written))
        finally:
            conn.close()
        return

    matches = json.load(open(args.input, encoding='utf-8'))
    by_name = (json.load(open(args.names, encoding='utf-8'))
               if args.names else {})
    db_path = get_items_db_path(args.game_version)
    if args.game_version == 'dofus3':
        _load_db_from_dump(db_path, args.game_version)

    conn = sqlite3.connect(db_path)
    try:
        add_column(conn)
        clear_skins(conn)
        known = {row[0]: (row[1], row[2], row[3]) for row in conn.execute("""
            SELECT i.ankama_id, i.id, t.name, i.name FROM items i
            JOIN item_types t ON t.id = i.type
            WHERE t.name IN (%s)""" % ','.join('?' * len(VISIBLE_TYPES)), VISIBLE_TYPES)}
        def decided(match, item_type, item_name):
            """The skin this mapping stands behind for the item, or None."""
            if match is None:
                return None
            if isinstance(match, int):  # already decided, no margin to weigh
                return match
            if not same_item(item_name, match.get('name')):
                return None             # another item under the same ankama id
            floor = args.min_margin
            if floor is None:
                floor = MIN_MARGIN.get(item_type, 0.10)
            if not match.get('backed') and match['score'] - match['runner_up'] < floor:
                return None             # the lead is too thin to trust
            return match['skin']

        from_id = from_name = 0
        for ankama_id, (item_id, item_type, item_name) in known.items():
            skin = decided(matches.get(str(ankama_id)), item_type, item_name)
            if skin is not None:
                from_id += 1
            else:
                skin = by_name.get(item_type, {}).get(flat_name(item_name))
                if skin is None:
                    continue
                from_name += 1
            conn.execute('UPDATE items SET skin = ? WHERE id = ?', (skin, item_id))
        conn.commit()
    finally:
        conn.close()

    _save_db_to_dump(db_path, args.game_version)
    print('%s: %d skins written (%d by ankama id, %d by name), %d items left bare'
          % (args.game_version, from_id + from_name, from_id, from_name,
             len(known) - from_id - from_name))


if __name__ == '__main__':
    main()
