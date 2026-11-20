#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add the game's own looks and default colours to breed_looks.json.

The client carries the colours per breed and per gender in breeds.json. Six of
them, one per ColorGray slot the art uses; the preview was inventing five, so
every piece in slot 6 stayed grey.

When the dump also holds heads.json (the client's HeadsDataRoot), every breed
and gender gets its look too: skeleton, body skin and scale from the breed's
maleLook or femaleLook, the head of order 0 and the number of heads.

    python itemscraper/store_breed_colors.py [--tag 3.6.8.8]
"""
from __future__ import annotations

import argparse
import io
import json
import os
import sys

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(CURRENT_DIR)
if CURRENT_DIR not in sys.path:
    sys.path.append(CURRENT_DIR)

from version_tags import latest_tag as _latest_tag  # noqa: E402  (sys.path set above)

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


def parse_breed_look(raw):
    """`{1|6245||50}` -> (bones, body skin, scale), or None."""
    fields = (raw or '').strip('{}').split('|')
    if len(fields) < 4 or not fields[0].isdigit() or not fields[1].isdigit():
        return None
    return int(fields[0]), int(fields[1]), fields[3]


def breed_looks(breeds, heads):
    """{'<breed>-<gender>': look} for every breed and gender with a look and a head."""
    looks = {}
    for breed_id, breed in breeds.items():
        for gender, field in ((0, 'maleLook'), (1, 'femaleLook')):
            parsed = parse_breed_look(breed.get(field))
            choices = sorted((head for head in heads.values()
                              if head.get('breed') == breed_id and head.get('gender') == gender),
                             key=lambda head: head.get('order', 0))
            if parsed is None or not choices or not str(choices[0].get('skins', '')).isdigit():
                continue
            bones, body, scale = parsed
            looks['%d-%d' % (breed_id, gender)] = {
                'bones': bones, 'body': body, 'scale': scale,
                'head': int(choices[0]['skins']), 'heads': len(choices)}
    return looks


def latest_tag():
    return _latest_tag(RAW_ROOT)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tag', help='datacenter dump to read, default the latest')
    args = parser.parse_args()

    dump = os.path.join(RAW_ROOT, args.tag or latest_tag())
    breeds = _table(os.path.join(dump, 'breeds.json'))
    with io.open(LOOKS, encoding='utf-8') as handle:
        looks = json.load(handle)

    heads_path = os.path.join(dump, 'heads.json')
    if os.path.isfile(heads_path):
        found = breed_looks(breeds, _table(heads_path))
        added = sorted(set(found) - set(looks))
        for key, look in found.items():
            looks.setdefault(key, {}).update(look)
        print('%d looks read from the client, added %s' % (len(found), ', '.join(added) or 'none'))

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
