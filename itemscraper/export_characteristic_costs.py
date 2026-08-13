#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""export_characteristic_costs.py - what each game charges for a stat point.

    dofus3, beta, dofus2  itemscraper/raw/<build>/breeds.json  statsPointsFor*
    touch                 itemscraper/touch_raw/Breeds_fr.json statsPointsFor*
    retro                 itemscraper/retro_raw/classes_fr.json b10..b15

    python itemscraper/export_characteristic_costs.py

The inputs are downloaded, not committed. The result goes to
characteristic_costs.json, which the test suite checks the constants against.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, 'fashionistapulp'))

OUT_NAME = 'characteristic_costs.json'

# The model stores six upper bounds, one per cost tier, in this order. A tier
# that does not exist has zero width; None means it runs on forever.
TIERS = (0.5, 1, 2, 3, 4, 5)

STAT_BY_FIELD = {
    'statsPointsForStrength': 'str',
    'statsPointsForIntelligence': 'int',
    'statsPointsForChance': 'cha',
    'statsPointsForAgility': 'agi',
    'statsPointsForVitality': 'vit',
    'statsPointsForWisdom': 'wis',
}

# 1.29 characteristic ids: the Iop's cheap stat is b10, the Feca's is b15.
STAT_BY_RETRO_KEY = {'b10': 'str', 'b11': 'vit', 'b12': 'wis',
                     'b13': 'cha', 'b14': 'agi', 'b15': 'int'}

RETRO_CLASS_BY_ID = {
    1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor',
    6: 'Ecaflip', 7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida',
    11: 'Sacrier', 12: 'Pandawa',
}

# Every class shares one table here, so it is stored once.
SHARED = '*'


def bounds(rows):
    """The game's [cost, floor] rows as the six upper bounds the model wants.

    A three wide row is [gain, cost, floor]: the Sacrier's vitality, one
    capital point for two, the model's 0.5 tier.
    """
    by_cost = {}
    for row in rows:
        if len(row) == 3:
            gain, cost, floor = row
            by_cost[float(cost) / float(gain)] = int(floor)
        else:
            cost, floor = row
            by_cost[float(cost)] = int(floor)
    dearest = max(by_cost)
    out, previous, ended = [], 0, False
    for tier in TIERS:
        if ended:
            out.append(0)
        elif tier not in by_cost:
            out.append(previous)
        elif tier == dearest:
            out.append(None)
            ended = True
        else:
            previous = by_cost[min(c for c in by_cost if c > tier)]
            out.append(previous)
    return out


def _unity_rows(field):
    """dofus3 and beta ship the tables as nested Unity arrays."""
    return [entry['values']['Array'] for entry in field['Array']]


def from_breeds(path):
    """A modern or Dofus 2 breeds.json -> {stat: bounds}, one shared table.

    Rows come as [floor, cost] here, the other way round from Retro.
    """
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if isinstance(data, dict) and 'references' in data:
        breeds = [ref['data'] for ref in data['references']['RefIds']]
        raw_rows = _unity_rows
    else:
        breeds = list(data.values()) if isinstance(data, dict) else data
        raw_rows = lambda field: field

    def rows_of(field):
        return [[cost, floor] for floor, cost in raw_rows(field)]
    tables = {}
    for breed in breeds:
        table = {stat: bounds(rows_of(breed[field]))
                 for field, stat in STAT_BY_FIELD.items()}
        if tables and table != tables[SHARED]:
            raise SystemExit('%s: the classes no longer share one table' % path)
        tables[SHARED] = table
    if not tables:
        raise SystemExit('%s: no breed in the file' % path)
    return tables


def from_retro(path):
    """Retro charges each class differently, so every class is written out."""
    with open(path, encoding='utf-8') as fh:
        classes = json.load(fh)['G']
    tables = {}
    for class_id, name in sorted(RETRO_CLASS_BY_ID.items()):
        entry = classes.get(str(class_id))
        if not entry:
            raise SystemExit('%s: no class %d' % (path, class_id))
        tables[name] = {stat: bounds(entry[key])
                        for key, stat in STAT_BY_RETRO_KEY.items()}
    return tables


def sources():
    import fashionista_version as ours
    raw = os.path.join(_HERE, 'raw')
    return [
        ('dofus3', os.path.join(raw, ours.FASHIONISTA_VERSION, 'breeds.json'),
         from_breeds),
        ('beta', os.path.join(raw, ours.FASHIONISTA_BETA_VERSION, 'breeds.json'),
         from_breeds),
        ('dofus2', os.path.join(raw, ours.FASHIONISTA_DOFUS2_VERSION,
                                'breeds.json'), from_breeds),
        ('touch', os.path.join(_HERE, 'touch_raw', 'Breeds_fr.json'),
         from_breeds),
        ('retro', os.path.join(_HERE, 'retro_raw', 'classes_fr.json'),
         from_retro),
    ]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', default=os.path.join(_HERE, OUT_NAME))
    args = parser.parse_args(argv)

    with open(args.out, encoding='utf-8') as fh:
        stored = json.load(fh)

    missing = []
    for version, path, reader in sources():
        if not os.path.exists(path):
            missing.append('%s (%s)' % (version, path))
            continue
        stored[version] = reader(path)
        print('%-7s %d table(s) from %s'
              % (version, len(stored[version]), os.path.relpath(path, _ROOT)))
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(stored, fh, indent=1, sort_keys=True)
        fh.write('\n')
    if missing:
        print('kept as they were, no source on this machine: %s'
              % ', '.join(missing))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
