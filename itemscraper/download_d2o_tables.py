#!/usr/bin/env python3
"""Fill the gaps the dofusdude mirror leaves in a raw dump, from Ankama's CDN.

The mirror publishes 52 files for Dofus 2 2.73.3.14 and `spell_levels.json` is
not among them, so `get_spells.py` had nothing to read and the Dofus 2 spell
damage stayed frozen on the values Dofus 3 launched with. Ankama's own CDN
carries `data/common/SpellLevels.d2o` for that same version: the numbers were
never missing from the game, only from the mirror.

This fetches those tables straight from the CDN, decodes them with `d2o.py` and
writes them beside the mirror's files, in the same plain-list shape, so nothing
downstream can tell where a table came from. Decoded this way, `Spells.d2o`
reproduces the mirror's `spells.json` on all 15655 records field for field,
which is what says the two shapes really are interchangeable.

Usage:
    python download_d2o_tables.py --game-version dofus2 SpellLevels
    python download_d2o_tables.py --game-version dofus2 --tag 2.73.3.14 \
        SpellLevels SpellVariants
"""

import argparse
import json
import os
import re
import sys

import cytrus_cdn
import d2o

RAW_ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'raw')


def _snake(name):
    """SpellLevels -> spell_levels, so the file sits with the mirror's own."""
    return re.sub(r'(?<!^)(?=[A-Z])', '_', name).lower()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tables', nargs='+',
                        help='CDN table names, e.g. SpellLevels')
    parser.add_argument('--game-version', default='dofus2',
                        choices=sorted(cytrus_cdn.RELEASES))
    parser.add_argument('--tag', help='raw dump to write into; default is the '
                                      'version the CDN currently serves')
    parser.add_argument('--raw-root', default=RAW_ROOT)
    args = parser.parse_args()

    tag = args.tag
    if not tag:
        # cytrus names it "6.0_2.73.3.14"; the dump is named for the game part.
        tag = cytrus_cdn.get_version(args.game_version).split('_')[-1]
    dest = os.path.join(args.raw_root, tag)
    if not os.path.isdir(dest):
        raise SystemExit('no such dump: %s' % dest)

    manifest = cytrus_cdn.download_manifest(args.game_version)
    for table in args.tables:
        name = 'data/common/%s.d2o' % table
        entry = cytrus_cdn.find_file(manifest, name)
        if entry is None:
            raise SystemExit('%s: not in the %s manifest'
                             % (name, args.game_version))
        blob = cytrus_cdn.fetch_file(entry)
        raw_path = os.path.join(dest, '%s.d2o' % table)
        with open(raw_path, 'wb') as handle:
            handle.write(blob)
        rows = d2o.load_rows(raw_path)
        os.remove(raw_path)
        out_path = os.path.join(dest, '%s.json' % _snake(table))
        with open(out_path, 'w', encoding='utf-8', newline='\n') as handle:
            json.dump(rows, handle, ensure_ascii=False)
        print('%s -> %s (%d rows)' % (name, out_path, len(rows)))
    return 0


if __name__ == '__main__':
    sys.exit(main())
