#!/usr/bin/env python3
"""Strip the upstream "[!]" untranslated tag from a stored version.

The scrapers clean it at the point they write, so this only has to run once per
version to correct what is already shipped:

    python itemscraper/sanitize_untranslated_tags.py --game-version dofus3
    python itemscraper/sanitize_untranslated_tags.py --game-version dofus3 --check
"""
from __future__ import annotations

import argparse
import os
import sqlite3
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from store_item_obtainment import (  # noqa: E402
    _load_db_from_dump, _save_db_to_dump, get_items_db_path)
from untranslated_tag import strip_tag_everywhere, tagged_rows  # noqa: E402
from fashionistapulp.game_versions import dofus_versions  # noqa: E402

# The Dofus versions, from the registry rather than a list written out
# by hand. A version added there and missed here is a version this
# quietly skips, which is the whole failure the registry exists to end.
# Wakfu is not among them: it is not a Dofus version.
VERSIONS = tuple(dofus_versions())


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3', choices=VERSIONS)
    parser.add_argument('--check', action='store_true',
                        help='report what carries the tag, change nothing')
    args = parser.parse_args()

    db_path = get_items_db_path(args.game_version)
    # dofus3 rebuilds items.db from its dump at runtime, so start from the dump.
    if args.game_version == 'dofus3' and not args.check:
        _load_db_from_dump(db_path, args.game_version)

    conn = sqlite3.connect(db_path)
    try:
        if args.check:
            rows = tagged_rows(conn)
            for table, column, rowid, value in rows:
                print('[%s] %s.%s #%s: %s'
                      % (args.game_version, table, column, rowid, value))
            print('[%s] %d tagged rows' % (args.game_version, len(rows)))
            return 1 if rows else 0
        stripped = strip_tag_everywhere(conn)
        conn.commit()
    finally:
        conn.close()

    if stripped:
        _save_db_to_dump(db_path, args.game_version)
    print('[%s] stripped the tag from %d rows' % (args.game_version, stripped))
    return 0


if __name__ == '__main__':
    sys.exit(main())
