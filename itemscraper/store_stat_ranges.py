#!/usr/bin/env python3
"""store_stat_ranges.py - fill stats_of_item.min_value / max_value from the
scraped source, so the encyclopedia can show "7 to 10 Strength".

The transform already carries both ends of every roll; the dump only kept the
best one because that is what the solver optimises on. get_equipments3.py now
writes both, but rebuilding a dump from scratch would drop the recipe, drop and
description tables that later pipeline steps add on top, so this fills the
columns in place instead.

    python itemscraper/store_stat_ranges.py --game-version dofus3
    python itemscraper/store_stat_ranges.py --game-version beta --input-dir itemscraper/beta
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

STAT_NAME_TO_KEY = None  # filled from get_equipments3 so the ids match exactly


def _stat_index():
    """stat name -> stats_of_item.stat id, the same mapping the dump uses."""
    import importlib.util
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'get_equipments3.py')
    source = open(path, encoding='utf-8').read()
    namespace = {}
    start = source.index('STAT_NAME_TO_KEY_LOCAL = {')
    end = source.index('\n}', start) + 2
    exec(source[start:end], namespace)
    names = list(namespace['STAT_NAME_TO_KEY_LOCAL'])
    return {name: i + 1 for i, name in enumerate(names)}


def _ranges_from_source(input_dir, stat_index):
    """(ankama_id, stat_id) -> (low, high) for every stat that really is a range."""
    path = os.path.join(input_dir, 'transformed_equipment.json')
    with open(path, encoding='utf-8') as fh:
        items = json.load(fh)
    ranges = {}
    for item in items:
        ankama_id = item.get('ankama_id')
        if ankama_id is None:
            continue
        for low, high, name in item.get('stats', []):
            stat_id = stat_index.get(name)
            if stat_id is None or low is None or high is None or low == high:
                continue
            ranges[(ankama_id, stat_id)] = (min(low, high), max(low, high))
    return ranges


def store(game_version, input_dir):
    db_path = get_items_db_path(game_version)
    if game_version == 'dofus3':
        # dofus3 rebuilds items.db from the dump at runtime, so start from it.
        _load_db_from_dump(db_path, game_version)
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        columns = {row[1] for row in cursor.execute('PRAGMA table_info(stats_of_item)')}
        for column in ('min_value', 'max_value'):
            if column not in columns:
                cursor.execute('ALTER TABLE stats_of_item ADD COLUMN %s INTEGER' % column)
        cursor.execute('UPDATE stats_of_item SET min_value = NULL, max_value = NULL')

        ranges = _ranges_from_source(input_dir, _stat_index())
        # An item with OR conditions is split into several rows sharing one
        # ankama_id, and they all roll the same range.
        by_item = {}
        for item_id, ankama_id in cursor.execute(
                'SELECT id, ankama_id FROM items WHERE ankama_id IS NOT NULL'):
            by_item.setdefault(ankama_id, []).append(item_id)

        updates = []
        for (ankama_id, stat_id), (low, high) in ranges.items():
            for item_id in by_item.get(ankama_id, ()):
                updates.append((low, high, item_id, stat_id))
        cursor.executemany(
            'UPDATE stats_of_item SET min_value = ?, max_value = ? '
            'WHERE item = ? AND stat = ?', updates)
        conn.commit()
        filled = cursor.execute(
            'SELECT COUNT(*) FROM stats_of_item WHERE min_value IS NOT NULL').fetchone()[0]
        total = cursor.execute('SELECT COUNT(*) FROM stats_of_item').fetchone()[0]
        print('[%s] %d/%d stat rows now carry a range' % (game_version, filled, total))
    finally:
        conn.close()
    _save_db_to_dump(db_path, game_version)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3')
    parser.add_argument('--input-dir', default=None,
                        help='where transformed_equipment.json lives '
                             '(default: the itemscraper directory)')
    args = parser.parse_args()
    input_dir = args.input_dir or os.path.dirname(os.path.abspath(__file__))
    store(args.game_version, input_dir)


if __name__ == '__main__':
    main()
