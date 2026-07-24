#!/usr/bin/env python3
"""rename_or_item_names.py - retag the OR-condition branches of an item as
"Name (#1)" / "Name (#2)" in an already-built items DB.

An item whose equip conditions are an OR ("Agility > 249 OR Strength > 249")
is split by get_equipments2.py into one row per branch. structure.py groups
those branches back under the plain name, but only when they carry the "(#N)"
tag; the old " 1" / " 2" naming left them ungrouped, so the player saw the same
item twice and the solver could equip two branches at once.

get_equipments2.py now writes "(#N)", so a full rebuild produces the right
names. This script brings the DBs that were built before that fix in line
without throwing away the recipe / drop / description tables that later
pipeline steps added on top.

    python itemscraper/rename_or_item_names.py --game-version dofus3
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)

NUMBERED = re.compile(r'^(?P<base>.+) (?P<n>\d+)$')


def find_or_groups(cursor):
    """ankama_id -> {item id: branch number}, for the groups that really are
    the branches of one item: several rows on the same ankama_id, all named
    "<same base> <n>" with n running 1..len."""
    rows = cursor.execute(
        "SELECT id, ankama_id, name FROM items WHERE ankama_id IS NOT NULL "
        "ORDER BY id").fetchall()
    by_ankama = {}
    for item_id, ankama_id, name in rows:
        by_ankama.setdefault(ankama_id, []).append((item_id, name))

    groups = {}
    for ankama_id, members in by_ankama.items():
        if len(members) < 2:
            continue
        parsed = [(item_id, NUMBERED.match(name)) for item_id, name in members]
        if any(m is None for _, m in parsed):
            continue
        bases = {m.group('base') for _, m in parsed}
        numbers = sorted(int(m.group('n')) for _, m in parsed)
        if len(bases) != 1 or numbers != list(range(1, len(members) + 1)):
            continue
        groups[ankama_id] = {item_id: int(m.group('n')) for item_id, m in parsed}
    return groups


def rename(game_version, dry_run=False):
    db_path = get_items_db_path(game_version)
    if game_version == 'dofus3':
        # dofus3 rebuilds items.db from the dump at runtime, so start from it.
        _load_db_from_dump(db_path, game_version)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        groups = find_or_groups(cursor)
        renamed = 0
        for members in groups.values():
            for item_id, number in members.items():
                for table, key in (('items', 'id'), ('item_names', 'item')):
                    for (name,) in cursor.execute(
                            "SELECT name FROM %s WHERE %s = ?" % (table, key),
                            (item_id,)).fetchall():
                        m = NUMBERED.match(name)
                        if m is None:
                            continue
                        new_name = '%s (#%d)' % (m.group('base'), number)
                        if not dry_run:
                            cursor.execute(
                                "UPDATE %s SET name = ? WHERE %s = ? AND name = ?"
                                % (table, key), (new_name, item_id, name))
                        renamed += 1
        print("[%s] %d OR groups, %d names retagged%s"
              % (game_version, len(groups), renamed, ' (dry run)' if dry_run else ''))
        if dry_run:
            conn.rollback()
            return
        conn.commit()
    finally:
        conn.close()
    _save_db_to_dump(db_path, game_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-version", default="dofus3")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    rename(args.game_version, args.dry_run)


if __name__ == "__main__":
    main()
