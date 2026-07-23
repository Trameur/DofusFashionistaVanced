#!/usr/bin/env python3
"""store_item_corrections.py - apply item_corrections.json to items.db.

Last pipeline step of every update_data*.py: hand-verified fixes for upstream
data errors, keyed by ankama_id per game version, so they survive re-scrapes.

Usage (from itemscraper/):
    python store_item_corrections.py --game-version dofus3
"""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_item_obtainment import (  # noqa: E402
    _save_db_to_dump, get_items_db_path)

CORRECTIONS_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), 'item_corrections.json')


def apply_corrections(conn, corrections):
    """Apply {ankama_id: fix} entries. Returns the number of changes."""
    cursor = conn.cursor()
    stat_ids = {key: sid for sid, key in
                cursor.execute('SELECT id, key FROM stats')}
    changes = 0
    for ankama_id_str, fix in corrections.items():
        if not fix.get('note') or not fix.get('source'):
            raise ValueError('correction %s needs note and source'
                             % ankama_id_str)
        item_ids = [r[0] for r in cursor.execute(
            'SELECT id FROM items WHERE ankama_id = ?', (int(ankama_id_str),))]
        if not item_ids:
            print('  warning: no item with ankama_id %s, skipped' % ankama_id_str)
            continue
        for item_id in item_ids:
            level = fix.get('level')
            if level is not None:
                cursor.execute('UPDATE items SET level = ? WHERE id = ? AND level != ?',
                               (int(level), item_id, int(level)))
                changes += cursor.rowcount
            for stat_key, value in (fix.get('stats') or {}).items():
                if stat_key not in stat_ids:
                    raise ValueError('unknown stat key %r in correction %s'
                                     % (stat_key, ankama_id_str))
                stat_id = stat_ids[stat_key]
                if value is None:
                    cursor.execute('DELETE FROM stats_of_item WHERE item = ? AND stat = ?',
                                   (item_id, stat_id))
                    changes += cursor.rowcount
                    continue
                cursor.execute(
                    'UPDATE stats_of_item SET value = ? WHERE item = ? AND stat = ? '
                    'AND value != ?', (value, item_id, stat_id, value))
                if cursor.rowcount:
                    changes += cursor.rowcount
                    continue
                cursor.execute('SELECT 1 FROM stats_of_item WHERE item = ? AND stat = ?',
                               (item_id, stat_id))
                if cursor.fetchone() is None:
                    cursor.execute(
                        'INSERT INTO stats_of_item (item, stat, value) VALUES (?, ?, ?)',
                        (item_id, stat_id, value))
                    changes += 1
    return changes


def store_corrections(game_version='dofus3'):
    with open(CORRECTIONS_PATH, encoding='utf-8') as fh:
        corrections = json.load(fh).get(game_version) or {}
    if not corrections:
        print('[%s] no manual corrections' % game_version)
        return
    items_db_path = get_items_db_path(game_version)
    conn = sqlite3.connect(items_db_path)
    try:
        changes = apply_corrections(conn, corrections)
        conn.commit()
    finally:
        conn.close()
    print('[%s] %d corrections listed, %d changes applied'
          % (game_version, len(corrections), changes))
    if changes:
        _save_db_to_dump(items_db_path, game_version)


def main():
    parser = argparse.ArgumentParser(description='Apply manual item corrections')
    parser.add_argument('--game-version', default='dofus3')
    args = parser.parse_args()
    store_corrections(args.game_version)


if __name__ == '__main__':
    main()
