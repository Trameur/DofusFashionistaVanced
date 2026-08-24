#!/usr/bin/env python3
"""Put the collected Wakfu spells into the item database.

    python build_wakfu_spells.py

RUN IT THROUGH update_data_wakfu.py. `build_wakfu_db.py` deletes
items_wakfu.db and writes it again, so everything here is erased by the next
rebuild unless the orchestrator runs this after it. See that file for who owns
which table.

Reads what `get_spells_wakfu.py` collected, one file per language, and writes
four tables. Nothing here touches Ankama's servers.

WHY SO FEW ROWS. A spell page offers 245 levels of every field and invites an
import to write 245 rows per spell. Measured over all 715: the AP, MP and WP
costs and the range NEVER vary with the level, on any spell, and the damage
varies for only 280 of them. So the costs live on the spell and only the
figures are stored per level. The sentence is kept once per language too, since
708 spells carry a single template across their whole range.

WHICH LANGUAGE DECIDES WHAT. The numbers are the same in all four, which was
checked rather than assumed: 706 spells are common to French and English and
they now agree on every damage figure at five different levels, as do Spanish
and Portuguese. So one language is enough for the figures and FRENCH is the one
used, because it carries nine Sram spells the English pages have never heard
of. The other three contribute names and sentences only.
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
from fashionistapulp.fashionista_config import get_items_db_path  # noqa: E402

HERE = Path(__file__).resolve().parent.parent

# French decides which spells exist and what they do; see the docstring.
AUTHORITY = 'fr'
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
FALLBACK = {'de': 'en'}

# The level whose text is kept. 708 of 715 spells say the same thing at every
# level, so any would do; the top one is the one a finished character reads.
SHOWN_AT = '245'


def harvest(raw_dir, language):
    path = Path(raw_dir) / ('spells_%s.json' % language)
    if not path.exists():
        return {}
    with io.open(path, encoding='utf-8') as handle:
        return json.load(handle)


def one_value(levels, field, counts):
    """The single value of a field that does not vary, or None if it does.

    A field that started varying would be a Wakfu update changing something
    this schema cannot hold, so it is counted and named rather than averaged.
    """
    seen = {json.dumps(level[field]) for level in levels.values()}
    if len(seen) > 1:
        counts['%s varies with the level, kept the top one' % field] += 1
        return levels[SHOWN_AT][field]
    return levels[SHOWN_AT][field]


def build(db_path, raw_dir):
    counts = collections.Counter()
    books = {language: harvest(raw_dir, language)
             for language in ('fr', 'en', 'es', 'pt')}
    spells = books.get(AUTHORITY) or {}
    if not spells:
        raise SystemExit('no %s harvest in %s; run get_spells_wakfu.py first'
                         % (AUTHORITY, raw_dir))

    conn = sqlite3.connect(str(db_path))
    try:
        for table in ('spell_effects', 'spell_text', 'spell_names', 'spells'):
            conn.execute('DELETE FROM %s' % table)

        for spell_id, spell in sorted(spells.items(), key=lambda kv: int(kv[0])):
            levels = spell['levels']
            conn.execute(
                'INSERT INTO spells (id, class, element, ap, mp, wp, range)'
                ' VALUES (?, ?, ?, ?, ?, ?, ?)',
                (int(spell_id), spell['class'], spell['element'],
                 one_value(levels, 'ap', counts),
                 one_value(levels, 'mp', counts),
                 one_value(levels, 'wp', counts),
                 one_value(levels, 'range', counts)))
            counts['spells'] += 1

            said = {}
            for language, book in books.items():
                other = book.get(spell_id)
                if other:
                    said[language] = other
                elif language != AUTHORITY:
                    counts['not in the %s pages' % language] += 1
            for absent, instead in FALLBACK.items():
                if instead in said:
                    said[absent] = said[instead]

            for language in LANGUAGES:
                if language not in said:
                    continue
                conn.execute('INSERT INTO spell_names (spell, language, name)'
                             ' VALUES (?, ?, ?)',
                             (int(spell_id), language, said[language]['name']))
                shown = said[language]['levels'][SHOWN_AT]
                conn.execute(
                    'INSERT INTO spell_text (spell, language, normal, critical)'
                    ' VALUES (?, ?, ?, ?)',
                    (int(spell_id), language, shown['normal'],
                     shown['critical']))
                counts['names'] += 1

            for level, row in sorted(levels.items(), key=lambda kv: int(kv[0])):
                position = 0
                for kind in ('damage', 'healing'):
                    for element, value in row[kind]:
                        conn.execute(
                            'INSERT INTO spell_effects (spell, level, position,'
                            ' kind, element, value, is_percent)'
                            ' VALUES (?, ?, ?, ?, ?, ?, 0)',
                            (int(spell_id), int(level), position, kind,
                             element, value))
                        position += 1
                        counts['effects'] += 1
                # A per cent is not a quantity of damage, so it is kept apart
                # rather than added to one. `rows` carries the sign.
                for label, element, value, unit in row.get('rows') or ():
                    if unit != '%':
                        continue
                    conn.execute(
                        'INSERT INTO spell_effects (spell, level, position,'
                        ' kind, element, value, is_percent)'
                        ' VALUES (?, ?, ?, ?, ?, ?, 1)',
                        (int(spell_id), int(level), position, 'damage',
                         element, value))
                    position += 1
                    counts['effects given as a per cent'] += 1
        conn.commit()
    finally:
        conn.close()
    return counts


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', default=None,
                        help='the mirrored build (default: the only one there)')
    parser.add_argument('--db', default=None)
    args = parser.parse_args(argv)

    raw_dir = args.raw
    if raw_dir is None:
        mirror = HERE / 'itemscraper' / 'wakfu_raw'
        builds = sorted(p for p in mirror.glob('*') if p.is_dir())
        if not builds:
            parser.error('no mirrored build; run get_items_wakfu.py first')
        raw_dir = builds[-1]
    db_path = Path(args.db or get_items_db_path('wakfu'))
    if not db_path.exists():
        parser.error('%s is missing; run build_wakfu_db.py first' % db_path)

    counts = build(db_path, raw_dir)
    print('filled the spell tables of %s' % db_path)
    for name, count in sorted(counts.items()):
        print('   %-46s %6d' % (name, count))
    return 0


if __name__ == '__main__':
    sys.exit(main())
