#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Store which spells are the two faces of one variant, into spell_variants.json.

    python store_spell_variants.py --game-version dofus3|beta

A Dofus 3 class spell comes as a pair and the player arms one of the two before
the fight, so a turn can never hold both. The datacenter says which two:
spell_variants.json is a list of {breedId, id, spellIds: [a, b]}. Dofus 2, Touch
and Retro never had variants, and simply have no such file.
"""
import argparse
import json
import os
import sys

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(CURRENT_DIRECTORY)
for path in (PROJECT_ROOT, CURRENT_DIRECTORY):
    if path not in sys.path:
        sys.path.append(path)

import fashionista_version  # noqa: E402

RAW_ROOT = os.path.join(CURRENT_DIRECTORY, 'raw')
# Beta and Dofus 3 share raw/, one directory per build.
ARCHIVE_TAG = {
    'dofus3': fashionista_version.FASHIONISTA_VERSION,
    'beta': fashionista_version.FASHIONISTA_BETA_VERSION,
}
OUTPUT = os.path.join(PROJECT_ROOT, 'fashionsite', 'chardata',
                      'spell_variants.json')


def _rows(payload):
    rows = payload.get('references', payload)
    rows = rows.get('RefIds', rows) if isinstance(rows, dict) else rows
    return list(rows.values()) if isinstance(rows, dict) else rows


def read_variants(tag):
    """{spell id: variant id} for one datacenter dump."""
    path = os.path.join(RAW_ROOT, tag, 'spell_variants.json')
    if not os.path.exists(path):
        raise SystemExit('no spell_variants.json at %s' % path)
    with open(path, encoding='utf-8') as handle:
        payload = json.load(handle)
    by_spell = {}
    for row in _rows(payload):
        data = row.get('data', row)
        variant = data.get('id')
        spell_ids = (data.get('spellIds') or {}).get('Array') or []
        if variant is None or len(spell_ids) < 2:
            continue
        for spell_id in spell_ids:
            by_spell[str(spell_id)] = variant
    return by_spell


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--game-version', default='dofus3',
                        choices=sorted(ARCHIVE_TAG))
    parser.add_argument('--tag', default=None)
    args = parser.parse_args()

    stored = {}
    if os.path.exists(OUTPUT):
        with open(OUTPUT, encoding='utf-8') as handle:
            stored = json.load(handle)

    by_spell = read_variants(args.tag or ARCHIVE_TAG[args.game_version])
    stored[args.game_version] = by_spell
    with open(OUTPUT, 'w', encoding='utf-8', newline='') as handle:
        json.dump(stored, handle, ensure_ascii=False, indent=1, sort_keys=True)
    print('%s: %d spells in %d variants'
          % (args.game_version, len(by_spell), len(set(by_spell.values()))))


if __name__ == '__main__':
    main()
