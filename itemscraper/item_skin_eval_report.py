#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Score the stored skins against the hand-labelled pairs.

    python itemscraper/item_skin_eval_report.py --candidates item_skins_topk.json

Labels are R (the pick is right), W (wrong) and U (could not tell by eye).
U pairs are counted apart: they are the ones worth looking at again first.
Run this before and after moving a floor or a band.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from item_skin_margins import MIN_MARGIN  # noqa: E402
from order_rerank_skins import (BAND, WIDE_BAND, backed_by_order,  # noqa: E402
                                mutual_best)

EVAL = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'item_skin_eval.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--candidates', required=True)
    args = parser.parse_args()

    with open(args.candidates, encoding='utf-8') as fh:
        candidates = json.load(fh)
    with open(EVAL, encoding='utf-8') as fh:
        labelled = json.load(fh)

    backed = backed_by_order(candidates)
    unclaimed = mutual_best(candidates)
    counts = defaultdict(lambda: defaultdict(int))
    for row in labelled:
        entry = candidates.get(str(row['ankama_id']))
        if entry is None or entry['top'][0][0] != row['skin']:
            counts[row['type']]['stale'] += 1
            continue
        top = entry['top']
        margin = top[0][1] - top[1][1] if len(top) > 1 else 0.0
        if margin >= MIN_MARGIN.get(row['type'], 1):
            kept = 'margin'
        elif str(row['ankama_id']) in backed:
            kept = 'order'
        else:
            kept = 'dropped'
        counts[row['type']]['%s %s' % (kept, row['label'])] += 1
        side = 'unclaimed' if str(row['ankama_id']) in unclaimed else 'claimed'
        counts[row['type']]['%s %s' % (side, row['label'])] += 1

    print()
    print('%-8s %s' % ('', 'bands ' + str(BAND)))
    print('%-8s %s' % ('', 'wide bands, unclaimed picks only ' + str(WIDE_BAND)))
    for item_type in sorted(counts):
        line = counts[item_type]
        right = line['margin R'] + line['order R']
        wrong = line['margin W'] + line['order W']
        unsure = line['margin U'] + line['order U']
        total = right + wrong
        print('%-8s kept %2d right, %2d wrong, %2d unsure%s   dropped %d'
              % (item_type, right, wrong, unsure,
                 '  (%d%% right)' % round(100.0 * right / total) if total else '',
                 line['dropped R'] + line['dropped W'] + line['dropped U']))
        if line['dropped R']:
            print('         %d of the dropped ones were right' % line['dropped R'])
        if line['stale']:
            print('         %d labels no longer name the top pick' % line['stale'])
        for side in ('unclaimed', 'claimed'):
            decided = line['%s R' % side] + line['%s W' % side]
            if decided:
                print('         %-9s %2dR %2dW (%d%% right)'
                      % (side, line['%s R' % side], line['%s W' % side],
                         round(100.0 * line['%s R' % side] / decided)))


if __name__ == '__main__':
    main()
