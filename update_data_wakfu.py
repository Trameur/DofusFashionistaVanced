#!/usr/bin/env python3
"""
update_data_wakfu.py - DofusFashionista data pipeline for Wakfu.

Usage:
    python update_data_wakfu.py                 # full rebuild from Ankama's CDN
    python update_data_wakfu.py --skip-images   # leave the artwork alone
    python update_data_wakfu.py --skip-mirror   # reuse the local mirror as it is

Wakfu is NOT a Dofus version. It has its own stats, slots, item types and
rules, and its data comes from a feed of its own; nothing here is shared with
update_data.py and its siblings beyond the shape of this file.

Steps:
    data/mirror    get_items_wakfu.py       -> wakfu_raw/<build>/ + transformed_wakfu.json
    data/sets      get_sets_wakfu.py        -> wakfu_raw/<build>/sets.json
    data/spells    get_spells_wakfu.py      -> wakfu_raw/<build>/spells_<lang>.json
    items/build-db build_wakfu_db.py        -> items_wakfu.db
    items/recipes  build_wakfu_recipes.py   -> the four crafting tables
    items/spells   build_wakfu_spells.py    -> the four spell tables
    item-images    get_item_images_wakfu.py -> static/chardata/items/wakfu/64/
    items/dump     dump_item_db.py          -> item_db_dumped_wakfu.dump

THE ORDER IS NOT A STYLE CHOICE, and this is the reason this file exists.

`build_wakfu_db.py` DELETES items_wakfu.db and builds it again from scratch.
That makes it the owner of every row in that database, and it makes every
other writer a guest that must run AFTER it. The five Dofus versions have had
an orchestrator each since the beginning; Wakfu did not, and without one a
later step that filled, say, the recipe tables would have its work erased by
the next routine rebuild, silently, and `dump_item_db.py` would then commit
the erasure.

So: WHICH TABLES BELONG TO WHOM.

    build_wakfu_db.py owns, and rewrites on every run:
        items, item_names, item_flags, item_types, item_type_names,
        item_type_position, item_rarity, item_picture, stats,
        stats_of_item, stat_element_count, sets, set_names

    build_wakfu_recipes.py owns, and rewrites on every run:
        item_recipes, item_recipe_ingredient_names, item_craft_jobs,
        job_names

    build_wakfu_spells.py owns, and rewrites on every run:
        spells, spell_names, spell_effects, spell_text

    Nothing else writes to items_wakfu.db today. A future step that does MUST
    be added to this file between items/build-db and items/dump, and MUST name
    the tables it owns right here. A writer that is not in this list is a
    writer whose work does not survive the next rebuild.

data/sets sits between the mirror and the build because it needs the decoded
dump to know which set ids exist, and the build needs its output to name them.

data/spells writes into the MIRROR and touches no table, so it is not in the
ownership list above and its position does not matter for safety. It is here
so that one command still rebuilds everything Wakfu. It only fetches spells it
does not already have, which is what makes it affordable at all: a first run
is 715 pages of half a megabyte per language, a second is 18.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
import time
from pathlib import Path

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent
ITEMSCRAPER = ROOT / 'itemscraper'
PY = sys.executable

NOTICE_KEYWORDS = ['attention', 'warning', 'could not', 'missing', 'not found',
                   'failed', 'mismatch', 'error', 'unresolved', 'no page']
NOISE_PATTERNS = [
    r'^\s*$', r'^\s*ok\b', r'^done', r'^wrote \d+', r'unchanged$',
    r'^\s+\d+ of \d+', r'^\s{3}\w',
]


def _is_noise(line):
    low = line.lower()
    return any(re.search(pattern, low) for pattern in NOISE_PATTERNS)


# "0 unresolved" is the good news, not a warning. A keyword that a zero counts
# is not a notice; the same keyword anywhere else still is.
_ZERO_COUNTED = re.compile(r'\b(?:0|no)\s+$')


def _is_notice(line):
    low = line.lower()
    for word in NOTICE_KEYWORDS:
        start = 0
        while True:
            at = low.find(word, start)
            if at < 0:
                break
            if not _ZERO_COUNTED.search(low[:at]):
                return True
            start = at + len(word)
    return False


def get_env():
    env = os.environ.copy()
    # Both spellings: the package root and the repository root. Scripts here
    # disagree about which one they import through.
    env['PYTHONPATH'] = os.pathsep.join(
        [str(ROOT), str(ROOT / 'fashionistapulp')])
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def run_step(label, cmd, cwd=None):
    print('\n[%s]' % label)
    started = time.time()
    process = subprocess.Popen(cmd, cwd=str(cwd or ROOT), env=get_env(),
                               stdout=subprocess.PIPE,
                               stderr=subprocess.STDOUT,
                               text=True, encoding='utf-8', errors='replace')
    lines = []
    for raw in process.stdout:
        line = raw.rstrip()
        lines.append(line)
        if not _is_noise(line):
            print('  %s' % line)
    process.wait()
    ok = process.returncode == 0
    print('  %s (%.1fs)' % ('ok' if ok else 'FAILED', time.time() - started))
    return ok, lines


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='DofusFashionista data pipeline for Wakfu',
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument('--skip-images', action='store_true',
                        help="don't fetch the item artwork from Ankama")
    parser.add_argument('--skip-mirror', action='store_true',
                        help='reuse the local mirror instead of asking the CDN')
    parser.add_argument('--skip-sets', action='store_true',
                        help='reuse the set names already recovered')
    parser.add_argument('--skip-spells', action='store_true',
                        help='reuse the spells already collected')
    args = parser.parse_args(argv)

    started = time.time()
    notices = []
    failed = []

    print('\n' + '-' * 60)
    print('  DofusFashionista update - WAKFU')
    print('-' * 60)

    def step(label, cmd, cwd=None):
        ok, lines = run_step(label, cmd, cwd)
        notices.extend(line.strip() for line in lines if _is_notice(line))
        if not ok:
            failed.append(label)
        return ok

    if not args.skip_mirror:
        step('data/mirror', [PY, 'itemscraper/get_items_wakfu.py'])
    if not args.skip_sets:
        step('data/sets', [PY, 'itemscraper/get_sets_wakfu.py'])
    if not args.skip_spells:
        for language in ('fr', 'en'):
            step('data/spells %s' % language,
                 [PY, 'itemscraper/get_spells_wakfu.py', '--lang', language])

    # Everything below writes into items_wakfu.db, and this step deletes it
    # first. Nothing that fills a table may move above this line.
    built = step('items/build-db', [PY, 'itemscraper/build_wakfu_db.py'])
    if built:
        step('items/recipes', [PY, 'itemscraper/build_wakfu_recipes.py'])
        step('items/spells', [PY, 'itemscraper/build_wakfu_spells.py'])

    if not args.skip_images:
        step('item-images', [PY, 'itemscraper/get_item_images_wakfu.py'])

    if built:
        step('items/dump', [PY, 'dump_item_db.py', '--game-version', 'wakfu'])
    else:
        print('\n[items/dump] skipped: the database was not built, and dumping'
              ' a stale one would publish it as if it were fresh')
        failed.append('items/dump (skipped)')

    print('\n' + '-' * 60)
    print('  done in %.1fs' % (time.time() - started))
    if notices:
        print('  %d notices:' % len(notices))
        for line in notices[:40]:
            print('     %s' % line)
    if failed:
        print('  FAILED: %s' % ', '.join(failed))
        return 1
    print('  every step ok')
    return 0


if __name__ == '__main__':
    sys.exit(main())
