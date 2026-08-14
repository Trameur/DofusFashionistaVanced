#!/usr/bin/env python3
"""store_weapon_uses_per_turn.py - load how many times a turn may swing each
weapon into items.db and re-dump it.

    weapon_uses_per_turn (item internal id, value)

The game limits a weapon to a few attacks per turn: most swords and axes go
once, most daggers twice. Dofus 3, the beta and Dofus 2 state it as
max_cast_per_turn in the datacenter item, Touch as maxCastPerTurn; Dofus Retro
(the 1.29 branch) never limited a weapon and has no such field, so it stores
nothing and the turn stays bounded by the AP alone.

Usage (from the repo root, after the version's items/transform step):
    python itemscraper/store_weapon_uses_per_turn.py --game-version dofus3
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3  # noqa: E402

from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))

# Where each version's items/transform step leaves its equipment file.
WORK_DIR = {
    'dofus3': CURRENT_DIRECTORY,
    'beta': os.path.join(CURRENT_DIRECTORY, 'beta'),
    'dofus2': os.path.join(CURRENT_DIRECTORY, 'dofus2'),
    'touch': os.path.join(CURRENT_DIRECTORY, 'touch'),
    'retro': os.path.join(CURRENT_DIRECTORY, 'retro'),
}


def _transformed(game_version):
    path = os.path.join(WORK_DIR[game_version], 'transformed_equipment.json')
    if not os.path.exists(path):
        raise SystemExit('no transformed equipment at %s' % path)
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


def store_uses_per_turn(game_version='dofus3'):
    rows = _transformed(game_version)
    by_ankama_id = {}
    for row in rows:
        uses = row.get('uses_per_turn')
        ankama_id = row.get('ankama_id')
        if uses and ankama_id is not None:
            by_ankama_id[int(ankama_id)] = int(uses)

    items_db_path = get_items_db_path(game_version)
    # dofus3 rebuilds items.db from the dump at runtime, so the dump leads.
    if game_version == 'dofus3':
        _load_db_from_dump(items_db_path, game_version)
    conn = sqlite3.connect(items_db_path)
    try:
        cursor = conn.cursor()
        columns = [row[1] for row in cursor.execute('PRAGMA table_info(items)')]
        # One ankama id can be several internal rows (alternative conditions are
        # flattened into "(#1)" and "(#2)"), and Touch and Retro reuse ids across
        # kinds, so only equipment rows are eligible.
        query = ("SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL"
                 + (" AND ankama_type = 'equipment'"
                    if 'ankama_type' in columns else '')
                 + " ORDER BY id")
        stored = []
        for item_id, ankama_id in cursor.execute(query):
            uses = by_ankama_id.get(ankama_id)
            if uses:
                stored.append((item_id, uses))

        cursor.execute('DROP TABLE IF EXISTS weapon_uses_per_turn')
        cursor.execute('CREATE TABLE weapon_uses_per_turn '
                       '(item INTEGER, value INTEGER)')
        cursor.executemany(
            'INSERT INTO weapon_uses_per_turn (item, value) VALUES (?, ?)',
            stored)
        cursor.execute('CREATE INDEX idx_weapon_uses_per_turn_item '
                       'ON weapon_uses_per_turn (item)')
        armed = len({item for item, _value in stored})
        conn.commit()
        print('[%s] weapon_uses_per_turn: %d rows for %d items '
              '(%d weapons in the transformed file)'
              % (game_version, len(stored), armed, len(by_ankama_id)))
    finally:
        conn.close()

    _save_db_to_dump(get_items_db_path(game_version), game_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=sorted(WORK_DIR))
    args = parser.parse_args()
    store_uses_per_turn(args.game_version)


if __name__ == '__main__':
    main()
