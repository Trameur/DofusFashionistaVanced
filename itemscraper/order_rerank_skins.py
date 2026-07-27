#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Keep the skin matches the release order backs up.

Item ids and skin ids both come from counters that advance with time, so the
matches that are already sure trace a curve, and an item's skin id can be
guessed from where its neighbours landed. A pick the picture is unsure about
but that lands on the curve anyway has two independent things saying the same
thing, which is enough to keep it.

    python itemscraper/order_rerank_skins.py --candidates item_skins_topk.json \
        --input item_skins.json --out item_skins_backed.json

--candidates is what match_item_skins.py writes with --candidates. Picks that
already clear their margin are passed through untouched.
"""
from __future__ import annotations

import argparse
import bisect
import json
import os
import statistics
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from item_skin_margins import MIN_MARGIN  # noqa: E402

WINDOW = 20

# How close to the curve a pick has to land, judged on sheets of icon against
# render. Weapons hold up to 0.04 and fall off after it. Cloaks are left out
# whatever the width: their curve scatters four times wider than the others.
BAND = {'Hat': 0.02, 'Shield': 0.02, 'Weapon': 0.04}


def _rank(values, value):
    return bisect.bisect_left(values, value) / max(len(values) - 1, 1)


def _margin(top):
    return top[0][1] - top[1][1] if len(top) > 1 else 0.0


def anchors(candidates):
    out = []
    for ankama_id, row in candidates.items():
        if _margin(row['top']) >= MIN_MARGIN.get(row['type'], 1):
            out.append((int(ankama_id), row['top'][0][0]))
    out.sort()
    return out


def expected_rank(anchor_ids, anchor_ranks, ankama_id):
    i = bisect.bisect_left(anchor_ids, ankama_id)
    lo, hi = max(0, i - WINDOW), min(len(anchor_ids), i + WINDOW)
    window = [anchor_ranks[j] for j in range(lo, hi) if anchor_ids[j] != ankama_id]
    return statistics.median(window) if len(window) >= 8 else None


def backed_by_order(candidates):
    """Ankama ids whose top pick is unsure but sits on the curve."""
    pool = sorted({skin for row in candidates.values() for skin, _score in row['top']})
    pairs = anchors(candidates)
    anchor_ids = [a for a, _s in pairs]
    anchor_ranks = [_rank(pool, s) for _a, s in pairs]
    print('%d sure matches trace the curve over %d skins' % (len(pairs), len(pool)))

    out = {}
    for ankama_id, row in candidates.items():
        band = BAND.get(row['type'])
        if band is None or _margin(row['top']) >= MIN_MARGIN.get(row['type'], 1):
            continue
        want = expected_rank(anchor_ids, anchor_ranks, int(ankama_id))
        if want is None:
            continue
        skin, score = row['top'][0]
        runner_up = row['top'][1][1] if len(row['top']) > 1 else 0.0
        if abs(_rank(pool, skin) - want) <= band:
            out[ankama_id] = {'skin': skin, 'score': round(score, 4),
                              'runner_up': round(runner_up, 4), 'name': row['name'],
                              'type': row['type'], 'backed': True}
    return out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', required=True)
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()

    with open(args.candidates, encoding='utf-8') as fh:
        candidates = json.load(fh)
    with open(args.input, encoding='utf-8') as fh:
        matched = json.load(fh)

    extra = backed_by_order(candidates)
    by_type = {}
    for row in extra.values():
        by_type[row['type']] = by_type.get(row['type'], 0) + 1
    for item_type in sorted(by_type):
        print('  %-8s %d kept on the curve' % (item_type, by_type[item_type]))

    matched.update(extra)
    with open(args.out, 'w', encoding='utf-8') as fh:
        json.dump(matched, fh, indent=1, ensure_ascii=False)
    print('wrote %d items to %s' % (len(matched), args.out))


if __name__ == '__main__':
    main()
