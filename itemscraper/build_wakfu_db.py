#!/usr/bin/env python3
"""Turn the decoded Wakfu build into an items database the site can read.

    python build_wakfu_db.py [--dump itemscraper/transformed_wakfu.json]

Run `get_items_wakfu.py` first: this reads what that writes and never touches
Ankama's servers.

The schema is the one the five Dofus versions already share, copied table for
table from `items.db`, because the parts that differ between games are ROWS and
not columns: `stats` names the characteristics, `item_types` the slots,
`item_flags` the marks. Wakfu's 34 characteristics and 12 slots are therefore
rows in a database of its own, and no Dofus version is touched.

Two facts have nowhere to sit in that schema, so `wakfu_db.py` adds one small
table each, and both exist only here: the rarity tier, and how many elements a
mastery line spreads over. See that module for why neither fits `stats_of_item`.

Sets are filled from what `get_sets_wakfu.py` recovered, because the CDN
publishes no set file: only the NAME comes from the encyclopedia, never the
bonus total it prints, which is stale. A set whose page has gone (three of
them) keeps its items and simply has no name to show.

German is absent from Wakfu entirely; `get_items_wakfu.py` and
`get_sets_wakfu.py` both fall it back to English, and that is what lands here.
"""

from __future__ import annotations

import argparse
import collections
import io
import json
import os
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), 'fashionistapulp'))
from fashionistapulp.wakfu_db import create_tables  # noqa: E402
from fashionistapulp.wakfu_slots import RARITIES, SLOTS  # noqa: E402
from fashionistapulp.wakfu_stats import WAKFU_STATS  # noqa: E402

HERE = Path(__file__).resolve().parent.parent
DOFUS_DB = HERE / 'fashionistapulp' / 'fashionistapulp' / 'items.db'
WAKFU_DB = HERE / 'fashionistapulp' / 'fashionistapulp' / 'items_wakfu.db'

# The site reads names in these five; the data only carries four, and the
# decoder has already put English under 'de'.
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')

# A slot a build fills. The rest (pets, mounts, costumes) is kept out of the
# item table rather than carried and then filtered everywhere downstream.
GEAR = set(SLOTS)


def dofus_schema():
    """Every CREATE statement of the shared schema, read from items.db."""
    conn = sqlite3.connect('file:%s?mode=ro' % DOFUS_DB, uri=True)
    try:
        rows = conn.execute(
            "SELECT sql FROM sqlite_master"
            " WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%'").fetchall()
    finally:
        conn.close()
    return [sql for (sql,) in rows]


def stat_name(key):
    """A readable name for a characteristic the client only names in caps."""
    return key.replace('_PERCENT', '').replace('_', ' ').title()


def read_sets(out_dir, version):
    """{set id: {language: name}} from get_sets_wakfu.py, or nothing yet."""
    path = Path(out_dir) / version / 'sets.json'
    if not path.exists():
        return {}
    with io.open(path, encoding='utf-8') as handle:
        return {int(key): names for key, names in json.load(handle).items()}


def build(dump_path, db_path, out_dir='itemscraper/wakfu_raw'):
    with io.open(dump_path, encoding='utf-8') as handle:
        dump = json.load(handle)
    sets = read_sets(out_dir, dump['version'])

    if db_path.exists():
        db_path.unlink()
    conn = sqlite3.connect(str(db_path))
    for statement in dofus_schema():
        conn.execute(statement)
    create_tables(conn)

    # The two vocabularies, as rows. Sorted so a rebuild gives the same ids and
    # a diff of two builds says something.
    slot_ids = {}
    for number, slot in enumerate(sorted(GEAR), start=1):
        slot_ids[slot] = number
        conn.execute('INSERT INTO item_types (id, name) VALUES (?, ?)',
                     (number, slot))
    stat_ids = {}
    for number, key in enumerate(sorted(WAKFU_STATS), start=1):
        stat_ids[key] = number
        conn.execute('INSERT INTO stats (id, name, key) VALUES (?, ?, ?)',
                     (number, stat_name(key), key.lower()))

    for set_id, names in sorted(sets.items()):
        conn.execute('INSERT INTO sets (id, name, ankama_id, dofustouch)'
                     ' VALUES (?, ?, ?, 0)',
                     (set_id, names.get('en'), set_id))
        for language, name in sorted(names.items()):
            conn.execute('INSERT INTO set_names (item_set, language, name)'
                         ' VALUES (?, ?, ?)', (set_id, language, name))

    counts = collections.Counter()
    for item in dump['equipment']:
        positions = [p for p in item['positions'] if p in GEAR]
        if not positions:
            counts['not gear'] += 1
            continue
        # A ring names both hands; the slot it is filed under is the first one
        # the game lists, and the model reads `item_flags` to know it fits the
        # other hand too.
        item_id = item['id']
        # A set the encyclopedia no longer has a page for keeps its items
        # and simply goes unnamed, rather than the items losing their set.
        set_id = item.get('set_id')
        if set_id and set_id not in sets:
            counts['set with no page'] += 1
            set_id = None
        conn.execute(
            'INSERT INTO items (id, name, level, type, item_set, ankama_id,'
            ' ankama_type, removed, dofustouch, skin)'
            ' VALUES (?, ?, ?, ?, ?, ?, ?, 0, 0, NULL)',
            (item_id, item['name'].get('en'), item['level'],
             slot_ids[positions[0]], set_id, item_id, positions[0]))
        counts['items'] += 1
        if set_id:
            counts['items in a set'] += 1

        for language in LANGUAGES:
            name = item['name'].get(language)
            if name:
                conn.execute('INSERT INTO item_names (item, language, name)'
                             ' VALUES (?, ?, ?)', (item_id, language, name))

        for flag in ('two_handed', 'relic', 'epic'):
            if flag == 'two_handed' and item['two_handed']:
                conn.execute('INSERT INTO item_flags (item, flag)'
                             ' VALUES (?, ?)', (item_id, flag))
            elif item['exclusive'] == flag:
                conn.execute('INSERT INTO item_flags (item, flag)'
                             ' VALUES (?, ?)', (item_id, flag))
        if len(positions) > 1:
            conn.execute('INSERT INTO item_flags (item, flag) VALUES (?, ?)',
                         (item_id, 'both_hands'))

        if item['rarity'] is not None:
            conn.execute('INSERT INTO item_rarity (item, rarity)'
                         ' VALUES (?, ?)', (item_id, item['rarity']))
            counts['rarity %s' % RARITIES.get(item['rarity'], '?')] += 1

        for line_number, line in enumerate(item['lines']):
            key = line.get('stat')
            if not key:
                counts['line: %s' % line.get('not_a_stat')] += 1
                continue
            value = int(line['value'])
            if not value:
                counts['line worth nothing'] += 1
                continue
            conn.execute(
                'INSERT INTO stats_of_item (item, stat, value, min_value,'
                ' max_value) VALUES (?, ?, ?, ?, ?)',
                (item_id, stat_ids[key], value, value, value))
            counts['stat lines'] += 1
            if line.get('elements'):
                # Named in full so structure.py can check the two tables
                # against each other instead of trusting a row order.
                conn.execute(
                    'INSERT INTO stat_element_count (item, line, stat, value,'
                    ' elements) VALUES (?, ?, ?, ?, ?)',
                    (item_id, line_number, stat_ids[key], value,
                     line['elements']))
                counts['spread over elements'] += 1

    conn.commit()
    conn.close()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dump', default='itemscraper/transformed_wakfu.json')
    parser.add_argument('--db', default=str(WAKFU_DB))
    parser.add_argument('--out', default='itemscraper/wakfu_raw',
                        help='where get_sets_wakfu.py wrote the set names')
    args = parser.parse_args(argv)

    dump_path = Path(args.dump)
    if not dump_path.exists():
        parser.error('%s is missing; run itemscraper/get_items_wakfu.py first'
                     % dump_path)
    counts = build(dump_path, Path(args.db), args.out)
    print('wrote %s' % args.db)
    for name, count in sorted(counts.items()):
        print('   %-28s %6d' % (name, count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
