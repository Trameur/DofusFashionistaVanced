#!/usr/bin/env python3
"""keep_db_tables.py - the tables of an items db that a partial rebuild does not
write, kept from a copy of the db taken before it.

    python itemscraper/keep_db_tables.py --game-version beta --save before.db
    python itemscraper/keep_db_tables.py --game-version beta --restore before.db
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


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', required=True)
    action = parser.add_mutually_exclusive_group(required=True)
    action.add_argument('--save', metavar='PATH', help='copy the db there before the rebuild')
    action.add_argument('--restore', metavar='PATH', help='bring back the tables the rebuild did not write')
    args = parser.parse_args(argv)
    database = get_items_db_path(args.game_version)
    if args.save:
        shutil.copyfile(database, args.save)
        print('%s: saved to %s' % (args.game_version, args.save))
        return 0
    kept = keep_missing_tables(args.restore, database)
    print('%s: %d table(s) kept as they were: %s' % (args.game_version, len(kept), ', '.join(kept) or 'none'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
