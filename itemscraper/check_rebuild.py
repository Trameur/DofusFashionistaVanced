#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""What did a rebuild change that nobody asked it to?

A rebuild is the riskiest thing in this repo and it reports success either way.
Three times in one week it changed something silently: the Retro drop tables
went to zero when the source moved its markup, the Touch pet variants lost the
drops they inherit, and the synthesized Gelano row took a different id because
it is numbered from the highest id in the data. Only a diff against what is
committed catches any of that.

    python itemscraper/check_rebuild.py             # every version
    python itemscraper/check_rebuild.py --only retro
    python itemscraper/check_rebuild.py --tolerance 0.05
    python itemscraper/check_rebuild.py --since HEAD~20   # before a bad commit

Two questions are asked of each version:

  rows     did any table lose more than the tolerance? A table that empties is
           the shape the drop scrape failed in.
  ids      did an item keep its ankama id and name but change its row id? A
           build stores row ids, and one that no longer resolves empties that
           slot without a word.

Exit code is 1 when either question has an answer.
"""
from __future__ import annotations

import argparse
import os
import re
import sqlite3
import subprocess
import sys
import tempfile

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIR)
for path in (PROJECT_ROOT, CURRENT_DIR, os.path.join(PROJECT_ROOT, 'fashionistapulp')):
    if path not in sys.path:
        sys.path.append(path)

from fashionistapulp.fashionista_config import get_items_db_path  # noqa: E402
from fashionistapulp.game_versions import dofus_versions

# The Dofus versions, from the registry rather than a list written out
# by hand. A version added there and missed here is a version this
# quietly skips, which is the whole failure the registry exists to end.
# Wakfu is not among them: it is not a Dofus version.
VERSIONS = tuple(dofus_versions())
# dofus3 keeps its committed copy in the dump and builds items.db from it.
COMMITTED = {
    'dofus3': 'fashionistapulp/fashionistapulp/item_db_dumped.dump',
    'beta': 'fashionistapulp/fashionistapulp/items_beta.db',
    'dofus2': 'fashionistapulp/fashionistapulp/items_dofus2.db',
    'touch': 'fashionistapulp/fashionistapulp/items_touch.db',
    'retro': 'fashionistapulp/fashionistapulp/items_retro.db',
}
INSERT = re.compile(r'INSERT INTO "?(\w+)"? VALUES\((\d+)')


def committed_bytes(path, rev='HEAD'):
    try:
        return subprocess.run(['git', 'show', '%s:%s' % (rev, path)],
                              cwd=PROJECT_ROOT, capture_output=True,
                              check=True).stdout
    except subprocess.CalledProcessError:
        return None


def _items_columns(text):
    """Column names of the items table, in order, from the dump's own schema.

    Reading the schema rather than counting from the end is the point: the old
    parser guessed a position, the `skin` column arrived, and the guess landed
    on `removed` without anyone noticing.
    """
    start = text.find('CREATE TABLE "items" (')
    if start < 0:
        return []
    body = text[start + len('CREATE TABLE "items" ('):text.find(');', start)]
    names = []
    for piece in body.split(','):
        piece = piece.strip()
        if not piece or piece.upper().startswith('FOREIGN KEY'):
            continue
        names.append(piece.split()[0].strip('`"'))
    return names


def _unquote(value):
    """A dumped text field keeps its quotes and doubles any apostrophe."""
    if len(value) >= 2 and value.startswith("'") and value.endswith("'"):
        return value[1:-1].replace("''", "'")
    return value


def _sql_values(payload):
    """Split an INSERT payload on its top-level commas.

    Item names carry commas and doubled quotes, so str.split is not enough.
    """
    values, buffer, quoted, i = [], [], False, 0
    while i < len(payload):
        char = payload[i]
        if quoted:
            if char == "'":
                if payload[i + 1:i + 2] == "'":
                    buffer.append("''")
                    i += 2
                    continue
                quoted = False
            buffer.append(char)
        elif char == "'":
            quoted = True
            buffer.append(char)
        elif char == ',':
            values.append(''.join(buffer))
            buffer = []
        elif char == ')':
            break
        else:
            buffer.append(char)
        i += 1
    values.append(''.join(buffer))
    return values


def read_committed(version, rev='HEAD'):
    """{table: row count} and {(ankama_id, name): id} as that revision has them."""
    raw = committed_bytes(COMMITTED[version], rev)
    if raw is None:
        return None, None
    if COMMITTED[version].endswith('.dump'):
        text = raw.decode('utf-8', 'replace')
        counts = {}
        for table, _first in INSERT.findall(text):
            counts[table] = counts.get(table, 0) + 1
        columns = _items_columns(text)
        items = {}
        for line in text.splitlines():
            if not line.startswith('INSERT INTO "items" VALUES('):
                continue
            values = _sql_values(line.split('VALUES(', 1)[1])
            if len(values) != len(columns):
                continue
            row = dict(zip(columns, values))
            items[(_unquote(row['ankama_id']), _unquote(row['name']))] = \
                int(row['id'])
        return counts, items

    handle, temp = tempfile.mkstemp(suffix='.db')
    os.write(handle, raw)
    os.close(handle)
    try:
        return read_db(temp)
    finally:
        os.unlink(temp)


def read_db(path):
    connection = sqlite3.connect('file:%s?mode=ro' % path, uri=True)
    try:
        counts = {}
        for (table,) in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"):
            counts[table] = connection.execute(
                'SELECT COUNT(*) FROM "%s"' % table).fetchone()[0]
        items = {(str(ankama), name): row_id for row_id, name, ankama
                 in connection.execute('SELECT id, name, ankama_id FROM items')}
        return counts, items
    finally:
        connection.close()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--only', help='one game version')
    parser.add_argument('--tolerance', type=float, default=0.03,
                        help='share of rows a table may lose without a word')
    # Once a bad dump is committed it becomes the reference and HEAD sees
    # nothing. The Touch pet numbering went that way: broken on the 15th,
    # committed the same hour, and only a comparison with the day before
    # showed the 82 pets that had changed owner.
    parser.add_argument('--since', default='HEAD', metavar='REV',
                        help='compare against this revision instead of HEAD')
    args = parser.parse_args(argv)

    versions = [v for v in VERSIONS if not args.only or v == args.only]
    findings = 0
    for version in versions:
        path = get_items_db_path(version)
        if not os.path.exists(path):
            print('%-8s no database on this machine' % version)
            continue
        was_counts, was_items = read_committed(version, args.since)
        if was_counts is None:
            print('%-8s nothing committed at %s to compare against'
                  % (version, args.since))
            continue
        now_counts, now_items = read_db(path)

        lost = []
        for table, before in sorted(was_counts.items()):
            after = now_counts.get(table)
            if after is None:
                lost.append((table, before, 'gone'))
            elif before and after < before * (1 - args.tolerance):
                lost.append((table, before, after))

        moved = []
        for key, before in was_items.items():
            after = now_items.get(key)
            if after is not None and after != before:
                moved.append((key[1], before, after))

        print('%-8s %-24s %s' % (
            version,
            'tables short: %d' % len(lost),
            'items whose row id moved: %d' % len(moved)))
        for table, before, after in lost[:8]:
            print('         %-28s %s -> %s' % (table, before, after))
        for name, before, after in moved[:8]:
            print('         %-28s id %s -> %s' % (name[:28], before, after))
        findings += len(lost) + len(moved)

    print()
    print('%d thing(s) a rebuild changed on its own' % findings)
    return 1 if findings else 0


if __name__ == '__main__':
    sys.exit(main())
