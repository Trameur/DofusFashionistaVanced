#!/usr/bin/env python3
"""Write the four Wakfu spell tables from what get_spells_wakfu.py collected; costs and range live on the spell, only the figures vary per level."""

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
try:
    from itemscraper.wakfu_mirror import current_build_dir  # noqa: E402
except ImportError:
    from wakfu_mirror import current_build_dir  # noqa: E402

HERE = Path(__file__).resolve().parent.parent

# French decides which spells exist and what they do; see the docstring.
AUTHORITY = 'fr'

# The same vocabulary the harvester uses to tell a damage row from a heal.
DAMAGE_WORDS = frozenset((
    'dommage', 'dommages', 'damage', 'damages',
    'dano', 'danos', 'daño', 'daños'))
HEAL_WORDS = frozenset((
    'soin', 'soins', 'heal', 'heals', 'healing',
    'cura', 'curas', 'curação', 'curación'))
LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
FALLBACK = {'de': 'en'}

# The level whose text is kept. 708 of 715 spells say the same thing at every
# level, so any would do; the top one is the one a finished character reads.
SHOWN_AT = '245'

# What the patch notes changed where the French page agrees; 'lands': some damage lands on every cast
# https://www.wakfu.com/fr/mmorpg/actualites/maj/1771795-mise-jour-1-93/details
NOTED = {
    '1.93': {
        4703: {'ap': 4, 'wp': 1, 'range': '1 - 4'},       # Tournee Generale
        4711: {'ap': 4, 'wp': 1, 'range': '1 - 5'},       # Fontaine de Laiqueur
        4714: {'ap': 3, 'wp': None, 'range': '1 - 4'},    # Frappe Fut
        4715: {'ap': 4, 'wp': None, 'range': '1 - 4',     # Lucha L'ambree
               'text': '+5 % par PM, 30 % max'},
        5030: {'lands': False},                            # Furie sanguinaire
        5037: {'ap': 4, 'wp': None, 'range': '0 - 2',     # Colonnades
               'lands': True},
        5040: {'lands': False},                            # Assaut
        5041: {'lands': False},                            # Projection
        5042: {'lands': False},                            # Fulgurance
        6463: {'ap': 4},                                   # Barbrule
        6465: {'ap': 3},                                   # Execution
        6466: {'ap': 2},                                   # Croisement
        6467: {'ap': 5, 'wp': 1},                          # Perforation
        6468: {'ap': 2},                                   # Mitraille
        6469: {'ap': 3},                                   # Tromblon
        6470: {'ap': 4},                                   # Balle plombante
        6475: {'ap': 4},                                   # Espingole
        6478: {'ap': 5},                                   # Longue lame
    },
}


def harvest(raw_dir, language):
    path = Path(raw_dir) / ('spells_%s.json' % language)
    if not path.exists():
        return {}
    with io.open(path, encoding='utf-8') as handle:
        return json.load(handle)


def one_value(levels, field, counts):
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
                # Straight from `rows`, which carries the label, the per cent
                # sign and whether the row is conditional. Reading the derived
                # `damage` and `healing` lists instead would lose both marks,
                # and a build shown the sum of alternatives is a build shown a
                # number the game never deals.
                position = 0
                for label, element, value, unit, conditional in (
                        row.get('rows') or ()):
                    words = {word.lower() for word in label.split()}
                    if words & DAMAGE_WORDS:
                        kind = 'damage'
                    elif words & HEAL_WORDS:
                        kind = 'healing'
                    else:
                        counts['row labelled %s, not stored' % label.lower()] += 1
                        continue
                    conn.execute(
                        'INSERT INTO spell_effects (spell, level, position,'
                        ' kind, element, value, is_percent, conditional)'
                        ' VALUES (?, ?, ?, ?, ?, ?, ?, ?)',
                        (int(spell_id), int(level), position, kind,
                         element, value, 1 if unit == '%' else 0,
                         1 if conditional else 0))
                    position += 1
                    counts['effects'] += 1
                    counts['effects that only land sometimes'] += bool(conditional)
                    counts['effects given as a per cent'] += unit == '%'
        conn.commit()
    finally:
        conn.close()
    return counts


def noted_for(build):
    """{spell id: what the tables must hold} from the patch notes of `build`."""
    for version, spells in NOTED.items():
        if build == version or build.startswith(version + '.'):
            return version, spells
    return None, {}


def noted_mismatches(conn, build):
    """One line per figure the tables hold against the patch notes of `build`."""
    version, spells = noted_for(build)
    out = []
    for spell_id, noted in sorted(spells.items()):
        row = conn.execute('SELECT ap, wp, range FROM spells WHERE id = ?',
                           (spell_id,)).fetchone()
        if row is None:
            out.append('mismatch: spell %d, which the %s notes change, is not '
                       'in the tables' % (spell_id, version))
            continue
        held = dict(zip(('ap', 'wp', 'range'), row))
        text = conn.execute(
            'SELECT normal FROM spell_text WHERE spell = ? AND language = ?',
            (spell_id, AUTHORITY)).fetchone()
        held['text'] = text[0] if text else None
        flags = [flag for (flag,) in conn.execute(
            "SELECT conditional FROM spell_effects WHERE spell = ? AND level = ?"
            " AND kind = 'damage'", (spell_id, int(SHOWN_AT)))]
        held['lands'] = (0 in flags) if flags else None
        for field, wanted in sorted(noted.items()):
            if field == 'text':
                agrees = wanted in (held['text'] or '')
            else:
                agrees = held[field] == wanted
            if not agrees:
                out.append('mismatch: spell %d %s is %r, the %s notes say %r'
                           % (spell_id, field, held[field], version, wanted))
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--raw', default=None,
                        help='the mirrored build (default: the one in transformed_wakfu.json)')
    parser.add_argument('--db', default=None)
    args = parser.parse_args(argv)

    raw_dir = args.raw
    if raw_dir is None:
        raw_dir = current_build_dir()
        if raw_dir is None:
            parser.error('no mirrored build; run get_items_wakfu.py first')
    db_path = Path(args.db or get_items_db_path('wakfu'))
    if not db_path.exists():
        parser.error('%s is missing; run build_wakfu_db.py first' % db_path)

    counts = build(db_path, raw_dir)
    print('filled the spell tables of %s' % db_path)
    for name, count in sorted(counts.items()):
        print('   %-46s %6d' % (name, count))

    conn = sqlite3.connect(str(db_path))
    try:
        mismatches = noted_mismatches(conn, Path(raw_dir).name)
    finally:
        conn.close()
    for line in mismatches:
        print(line)
    print('   %d spells checked against the patch notes of %s'
          % (len(noted_for(Path(raw_dir).name)[1]), Path(raw_dir).name))
    return 0


if __name__ == '__main__':
    sys.exit(main())
