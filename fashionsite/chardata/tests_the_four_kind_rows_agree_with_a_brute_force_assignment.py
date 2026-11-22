# -*- coding: utf-8 -*-
"""The four Hall rows hold exactly when an assignment of runes to copies exists."""
import itertools

from django.test import SimpleTestCase

from fashionistapulp.transcendence_terms import (hall_rows, rows_hold,
                                                 rune_allowed_on)

KINDS = (None, 'element', 'resistance', 'power')
STATS = ('int', 'earthdam', 'fireresper', 'pow', 'dam', 'neutdam', 'vit')


def _feasible(copy_kinds, demand):
    def place(index, left):
        if not any(left.values()):
            return True
        if index == len(copy_kinds):
            return False
        if place(index + 1, left):
            return True
        for stat in STATS:
            if left[stat] and rune_allowed_on(copy_kinds[index], stat):
                left[stat] -= 1
                found = place(index + 1, left)
                left[stat] += 1
                if found:
                    return True
        return False

    return place(0, dict(demand))


class TheRowsAgreeWithABruteForceTests(SimpleTestCase):

    def test_the_rows_are_the_four_expected_ones(self):
        self.assertEqual([row[0] for row in hall_rows()],
                         ['T1', 'T2', 'T3', 'T4'])

    def test_every_split_and_demand_gives_the_same_verdict(self):
        checked = 0
        for size in range(4):
            splits = itertools.combinations_with_replacement(KINDS, size)
            for copy_kinds in splits:
                draco = {kind: copy_kinds.count(kind)
                         for kind in KINDS if kind}
                for counts in itertools.product(range(3), repeat=len(STATS)):
                    demand = dict(zip(STATS, counts))
                    self.assertEqual(
                        rows_hold(size, draco, demand),
                        _feasible(copy_kinds, demand),
                        (copy_kinds, counts))
                    checked += 1
        self.assertGreater(checked, 10000)
