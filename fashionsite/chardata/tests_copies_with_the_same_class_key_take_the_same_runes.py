# -*- coding: utf-8 -*-
"""Two copies with the same class key get the same runes, and lower tiers only for capped upper stats."""
from django.test import SimpleTestCase

from fashionistapulp.transcendence_terms import (class_key, class_runes,
                                                 runes_by_stat)


def _rune(rune_id, stat, rank, bonus, weight, density):
    return {'id': rune_id, 'stat_key': stat, 'rank': rank, 'bonus': bonus,
            'weight': weight, 'density': density}


RUNES = [_rune(1, 'int', 1, 10, 20, 1), _rune(2, 'int', 2, 20, 40, 1),
         _rune(3, 'int', 3, 30, 60, 1),
         _rune(4, 'fireresper', 1, 5, 20, 1), _rune(5, 'fireresper', 2, 8, 40, 1)]
BY_STAT = runes_by_stat(RUNES)


class CopiesWithTheSameClassKeyTests(SimpleTestCase):

    def test_equal_keys_give_equal_runes_whatever_the_other_lines(self):
        upper = {'int'}
        capped = {'int', 'fireresper'}
        seen = {}
        for int_line in range(0, 90, 5):
            for fire_line in (0, 12, 70):
                lines = {'int': int_line, 'fireresper': fire_line}
                key = class_key(BY_STAT, lines, upper)
                ids = [r['id'] for r in class_runes(BY_STAT, lines, upper, capped)]
                self.assertEqual(seen.setdefault(key, ids), ids, lines)
        self.assertGreater(len(seen), 1)

    def test_a_stat_outside_the_upper_stats_gets_no_rune(self):
        lines = {'int': 0, 'fireresper': 0}
        ids = [r['id'] for r in class_runes(BY_STAT, lines, {'int'}, {'fireresper'})]
        self.assertEqual(ids, [3])

    def test_lower_tiers_come_only_for_capped_upper_stats(self):
        lines = {'int': 0, 'fireresper': 0}
        self.assertEqual([r['id'] for r in class_runes(BY_STAT, lines, {'int'}, set())], [3])
        self.assertEqual([r['id'] for r in class_runes(BY_STAT, lines, {'int'}, {'int'})], [1, 2, 3])
