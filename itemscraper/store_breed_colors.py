#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add the game's own default colours to breed_looks.json.

The client carries them per breed and per gender in breeds.json. Six of them,
one per ColorGray slot the art uses; the preview was inventing five, so every
piece in slot 6 stayed grey.

    python itemscraper/store_breed_colors.py [--tag 3.6.8.8]
"""
from __future__ import annotations

import argparse
import io
import json
import os

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
RAW_ROOT = os.path.join(CURRENT_DIR, 'raw')
LOOKS = os.path.join(ROOT, 'fashionsite', 'chardata', 'data', 'breed_looks.json')


def _table(path):
    with io.open(path, encoding='utf-8') as handle:
        data = json.load(handle)
    refs = {ref['rid']: ref['data'] for ref in data['references']['RefIds']}
    keys = data['objectsById']['m_keys']['Array']
    values = data['objectsById']['m_values']['Array']
    return {key: refs[value['rid']] for key, value in zip(keys, values)
            if value['rid'] in refs}


def hex_colours(raw):
    """The client stores them as packed ints; -1 means the slot has no colour."""
    out = []
    for value in (raw or {}).get('Array') or []:
        out.append(None if value < 0 else '%06x' % (value & 0xFFFFFF))
    return out


def latest_tag():
    tags = [name for name in os.listdir(RAW_ROOT)
            if os.path.isdir(os.path.join(RAW_ROOT, name))]
    return sorted(tags)[-1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', help='datacenter dump to read, default the latest')
    args = parser.parse_args()

    dump = os.path.join(RAW_ROOT, args.tag or latest_tag())
    breeds = _table(os.path.join(dump, 'breeds.json'))
    with io.open(LOOKS, encoding='utf-8') as handle:
        looks = json.load(handle)

    written = missing = 0
    for key, entry in looks.items():
        breed_id, gender = (int(part) for part in key.split('-'))
        breed = breeds.get(breed_id)
        if not breed:
            missing += 1
            continue
        colours = hex_colours(breed.get('femaleColors' if gender
                                        else 'maleColors'))
        if not colours:
            missing += 1
            continue
        entry['colors'] = colours
        written += 1

    with io.open(LOOKS, 'w', encoding='utf-8', newline='') as handle:
        json.dump(looks, handle, indent=1, sort_keys=True)
        handle.write('\n')
    print('%d looks given their colours, %d without' % (written, missing))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
