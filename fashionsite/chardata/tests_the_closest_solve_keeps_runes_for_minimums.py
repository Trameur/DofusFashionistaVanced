# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The closest solve keeps every rune a minimum could use, through the shortfall and the tie break."""

import time
from types import SimpleNamespace
from unittest import mock

from chardata import fashion_action
from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input, columns,
                                         element_key, element_move, piece)
from fashionistapulp import dracorunes

NEEDED = 40
STAT_NAMES = {'str': 'Strength', 'int': 'Intelligence', 'cha': 'Chance', 'agi': 'Agility'}


def column(item, key):
    kind, _, move = key.partition(':')
    return 'draco_%d_%s_%s' % (item.id, kind[:1], '_'.join(move.split('>')))


class AMinimumOnlyARuneReachesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.hat = piece('Hat', {self.source: NEEDED})
        self.amulet = piece('Amulet', {'vit': 300})
        self.minimums = {STAT_NAMES[self.target]: NEEDED}

    def closest(self, runes_allowed):
        model_input = build_input({'vit': 1}, runes_allowed, self.minimums)
        built = []

        def small_model(**_kwargs):
            built.append(SmallModel([self.hat, self.amulet]))
            return built[-1]

        with mock.patch.object(fashion_action, 'Model', side_effect=small_model), \
                mock.patch.dict(fashion_action._BUILD_SECONDS, {}, clear=True):
            found = fashion_action._closest_solve(SimpleNamespace(id=0), model_input, 'proof',
                                                  time.monotonic() + 600)
        self.assertEqual(1, len(built))
        self.assertEqual('found', found['state'])
        self.assertIn('tie_break', found)
        return found

    def test_one_rune_closes_the_shortfall(self):
        found = self.closest(1)
        self.assertAlmostEqual(0, found['shortfall'])
        self.assertTrue(found['meets_all'])
        self.assertEqual({'hat': (self.hat.id, element_key(self.source, self.target))},
                         found['minimal'].dracorunes)

    def test_without_a_rune_the_minimum_stays_short(self):
        for runes_allowed in (0, None):
            with self.subTest(runes_allowed=runes_allowed):
                found = self.closest(runes_allowed)
                self.assertGreater(found['shortfall'], 0)
                self.assertFalse(found['meets_all'])
                self.assertFalse(getattr(found['minimal'], 'dracorunes', None))


class TheShortfallKeepsWhatTheMinimumsAloneCouldUseTests(BetaModelTestCase):
    """Two runes move a line onto the asked stat; the weight prefers one, the minimums alone the other."""

    def setUp(self):
        super().setUp()
        _source, self.target = element_move()
        self.weighted, self.other = sorted(
            key for key, _damage in dracorunes.ELEMENT_PAIRS if key != self.target)[:2]
        self.hat = piece('Hat', {self.weighted: NEEDED, self.other: NEEDED})
        self.model = SmallModel([self.hat])
        self.model_input = build_input({self.weighted: 1, 'vit': 0}, 1,
                                       {STAT_NAMES[self.target]: NEEDED})
        self.by_weight = column(self.hat, element_key(self.other, self.target))
        self.by_minimum = column(self.hat, element_key(self.weighted, self.target))

    def test_the_weights_alone_keep_one_of_the_two(self):
        self.model.setup(self.model_input)
        self.assertIn(self.by_weight, columns(self.model))
        self.assertNotIn(self.by_minimum, columns(self.model))

    def test_the_elastic_minimums_keep_both(self):
        self.model.setup(self.model_input)
        self.model.add_elastic_minimums(self.model_input.minimum_stats, 200)
        self.assertIn(self.by_weight, columns(self.model))
        self.assertIn(self.by_minimum, columns(self.model))

    def test_a_retried_run_keeps_both(self):
        self.model.setup(self.model_input)
        shortfalls = self.model.add_elastic_minimums(self.model_input.minimum_stats, 200)
        self.model.minimise_shortfall(shortfalls)
        widened = columns(self.model)
        self.model.run(0, change_of=True)
        self.assertEqual('Optimal', self.model.get_solved_status())
        self.assertEqual(widened, columns(self.model))
        self.model.hold_shortfall(shortfalls, self.model.get_shortfall(shortfalls))
        self.model.run(0, change_of=True)
        self.assertEqual(widened, columns(self.model))

    def test_the_next_setup_forgets_the_widened_set(self):
        self.model.setup(self.model_input)
        before = columns(self.model)
        self.model.add_elastic_minimums(self.model_input.minimum_stats, 200)
        self.model.setup(self.model_input)
        self.assertEqual(before, columns(self.model))
