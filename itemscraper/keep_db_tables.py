#!/usr/bin/env python3
"""keep_db_tables.py - the tables of an items db that a partial rebuild does not
write, kept from a copy of the db taken before it.

    python itemscraper/keep_db_tables.py --game-version beta --save before.db
    python itemscraper/keep_db_tables.py --game-version beta --restore before.db
    python itemscraper/keep_db_tables.py --game-version touch --retire before.db
"""
from __future__ import annotations

import argparse
import os
import shutil
import sqlite3
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
for path in (PROJECT_ROOT, CURRENT_DIR, os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

from fashionistapulp.fashionista_config import get_items_db_path  # noqa: E402


def tables(conn, schema='main'):
    return {name: sql for name, sql in conn.execute(
        "SELECT name, sql FROM %s.sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%%'" % schema)}


def keep_missing_tables(previous, current):
    """Copies into current every table of previous that current lacks, with its indexes; returns their names."""
    conn = sqlite3.connect(current)
    try:
        conn.execute('ATTACH DATABASE ? AS previous', (previous,))
        have = tables(conn)
        kept = sorted(name for name in tables(conn, 'previous') if name not in have)
        old = tables(conn, 'previous')
        for name in kept:
            conn.execute(old[name])
            conn.execute('INSERT INTO "%s" SELECT * FROM previous."%s"' % (name, name))
        for name in kept:
            for (sql,) in conn.execute("SELECT sql FROM previous.sqlite_master WHERE type = 'index' "
                                       "AND tbl_name = ? AND sql IS NOT NULL", (name,)).fetchall():
                conn.execute(sql)
        conn.commit()
        conn.execute('DETACH DATABASE previous')
    finally:
        conn.close()
    return kept


def keep_retired_items(previous, current):
    """Copies into current, hidden, every item of previous whose id current lacks, with its rows; returns their ids."""
    if not os.path.exists(previous):
        return []
    conn = sqlite3.connect(current)
    try:
        conn.execute('ATTACH DATABASE ? AS previous', (previous,))
        retired = [item for (item,) in conn.execute(
            'SELECT id FROM previous.items WHERE id NOT IN (SELECT id FROM main.items) ORDER BY id')]
        if retired:
            marks = ','.join('?' * len(retired))
            old = tables(conn, 'previous')
            for name in sorted(tables(conn)):
                if name not in old:
                    continue
                ours = [row[1] for row in conn.execute('PRAGMA main.table_info("%s")' % name)]
                theirs = {row[1] for row in conn.execute('PRAGMA previous.table_info("%s")' % name)}
                key = 'id' if name == 'items' else 'item'
                if key not in ours:
                    continue
                shared = ', '.join('"%s"' % column for column in ours if column in theirs)
                conn.execute('INSERT OR IGNORE INTO main."%s" (%s) SELECT %s FROM previous."%s" WHERE "%s" IN (%s)'
                             % (name, shared, shared, name, key, marks), retired)
            conn.execute('UPDATE items SET removed = 1 WHERE id IN (%s)' % marks, retired)
            conn.execute('UPDATE items SET item_set = NULL WHERE id IN (%s) AND item_set NOT IN (SELECT id FROM sets)'
                         % marks, retired)
        conn.commit()
        conn.execute('DETACH DATABASE previous')
    finally:
        conn.close()
    return retired


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--save', metavar='PATH', help='copy the db there before the rebuild')
    action.add_argument('--restore', metavar='PATH', help='bring back the tables the rebuild did not write')
    action.add_argument('--retire', metavar='PATH', help='bring back, hidden, the items the rebuild no longer has')
    args = parser.parse_args(argv)
    database = get_items_db_path(args.game_version)
    if args.save:
        if not os.path.exists(database):
            print('%s: no database to save yet' % args.game_version)
            return 0
        shutil.copyfile(database, args.save)
        print('%s: saved to %s' % (args.game_version, args.save))
        return 0
    if args.retire:
        retired = keep_retired_items(args.retire, database)
        print('%s: %d item(s) no longer in the game files, kept hidden for saved builds: %s'
              % (args.game_version, len(retired), ', '.join(map(str, retired)) or 'none'))
        return 0
    kept = keep_missing_tables(args.restore, database)
    print('%s: %d table(s) kept as they were: %s' % (args.game_version, len(kept), ', '.join(kept) or 'none'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
