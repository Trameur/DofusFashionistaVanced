#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sqlite3

conn = sqlite3.connect('fashionistapulp/fashionistapulp/items.db')
c = conn.cursor()

# Get all item IDs from items table
items = set([row[0] for row in c.execute('SELECT id FROM items')])
print(f'Items in items table: {len(items)}')
print()

# Check all tables that reference items
tables_to_check = [
    ('stats_of_item', 'item'),
    ('min_stat_to_equip', 'item'),
    ('max_stat_to_equip', 'item'),
    ('weird_conditions', 'item'),
    ('extra_lines', 'item'),
    ('weapon_hits', 'item'),
    ('item_names', 'item'),
]

for table, column in tables_to_check:
    try:
        referenced_items = set([row[0] for row in c.execute(f'SELECT DISTINCT {column} FROM {table}')])
        orphaned = referenced_items - items
        print(f'{table}:')
        print(f'  Referenced items: {len(referenced_items)}')
        print(f'  Orphaned references: {len(orphaned)}')
        if orphaned:
            print(f'  First 10 orphaned IDs: {sorted(list(orphaned))[:10]}')
        print()
    except sqlite3.OperationalError as e:
        print(f'{table}: Table does not exist or error: {e}')
        print()

conn.close()
