#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Sanity check: every game-version item dump must contain weapon hit data.

Loads each per-version SQL dump (and the built items.db for dofus3) into an
in-memory SQLite DB and reports the row counts of the critical weapon tables.
A version with zero ``weapon_hits`` means the optimizer cannot value any
weapon's damage for that version (this exact regression hit Dofus 2: its dump
was stale and shipped with 0 weapon_hits while every other version had them).

Exit code is non-zero if any version is missing weapon hit data, so this can be
wired into the data pipeline / pre-deploy checks. It is a read-only diagnostic:
it never modifies any dump, database or application data.

Usage:
    python check_version_weapon_data.py
"""

import os
import sqlite3
import sys

DUMP_DIR = os.path.join('fashionistapulp', 'fashionistapulp')

# version label -> dump filename (mirrors _DUMP_FILES in fashionista_config.py)
DUMPS = {
    'dofus3': 'item_db_dumped.dump',
    'beta':   'item_db_dumped_beta.dump',
    'dofus2': 'item_db_dumped_dofus2.dump',
    'retro':  'item_db_dumped_retro.dump',
    'touch':  'item_db_dumped_touch.dump',
}

# Tables that must not be empty for weapon optimization to work.
CRITICAL_WEAPON_TABLES = ['weapon_hits', 'weapon_ap', 'weapon_crit_hits']


def _load(path):
    con = sqlite3.connect(':memory:')
    with open(path, 'r', encoding='utf-8', errors='replace') as fh:
        con.executescript(fh.read())
    return con


def _count(cur, table):
    try:
        return cur.execute('SELECT COUNT(*) FROM %s' % table).fetchone()[0]
    except sqlite3.OperationalError:
        return None  # table missing


def main():
    failures = []
    for version, filename in DUMPS.items():
        path = os.path.join(DUMP_DIR, filename)
        if not os.path.exists(path):
            print('%-7s MISSING DUMP: %s' % (version, path))
            failures.append('%s (dump file missing)' % version)
            continue
        try:
            con = _load(path)
        except Exception as exc:  # pragma: no cover - defensive
            print('%-7s LOAD ERROR: %s' % (version, exc))
            failures.append('%s (load error)' % version)
            continue
        cur = con.cursor()
        counts = {t: _count(cur, t) for t in CRITICAL_WEAPON_TABLES}
        con.close()
        summary = '  '.join('%s=%s' % (t, counts[t]) for t in CRITICAL_WEAPON_TABLES)
        hits = counts.get('weapon_hits')
        status = 'OK' if hits else 'FAIL'
        print('%-7s [%s]  %s' % (version, status, summary))
        if not hits:
            failures.append('%s (weapon_hits empty)' % version)

    print()
    if failures:
        print('FAILED: missing weapon data for: %s' % ', '.join(failures))
        print('Fix: regenerate the affected version dump '
              '(e.g. `python update_data_<version>.py`).')
        return 1
    print('OK: all versions have weapon hit data.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
