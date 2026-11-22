# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A transcendence rune another free rune of its copy beats is left out without changing the best set."""

from unittest import mock

import pulp

from fashionistapulp import model as model_module
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.transcendence_terms import (ROW_BOUND_STATS, blocking_kinds,
                                                 class_runes, copy_runes)

from chardata.dracorune_fixtures import BetaModelTestCase, SmallModel, element_move, piece
from chardata.transcendence_fixtures import beta_rune, exo_input, plain_piece, stat_runes

STAT_NAME = {key: name for name, key in STATS_NAMES}


def _without_pruning(by_stat, lines, upper, capped, *_ignored):
    return class_runes(by_stat, lines, upper, capped)


class DominatedRunesNeverChangeTheOptimumTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.pieces = [piece('Hat', {}), piece('Cloak', {}), piece('Amulet', {}),
                       piece('Belt', {}), piece('Boots', {})]

    def best(self, model_input, pruned):
        model = SmallModel(self.pieces)
        if pruned:
            model.setup(model_input)
        else:
            with mock.patch.object(model_module, 'copy_runes', _without_pruning):
                model.setup(model_input)
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        return pulp.value(model.problem.pulp_lp.objective), model

    def same_optimum(self, weights, runes, dracorunes=None, minimums=None, **exos):
        def make():
            model_input = exo_input(weights, runes, dracorunes, **exos)
            model_input.minimum_stats = dict(minimums or {})
            return model_input
        cut, cut_model = self.best(make(), True)
        full, full_model = self.best(make(), False)
        self.assertAlmostEqual(full, cut, places=6)
        return cut_model, full_model

    def test_a_free_stat_beating_another_free_stat_drops_it(self):
        cut, full = self.same_optimum({'str': 3, 'int': 1}, 3)
        self.assertTrue(stat_runes(cut, 'str'))
        self.assertFalse(stat_runes(cut, 'int'))
        self.assertTrue(stat_runes(full, 'int'))

    def test_a_free_stat_beating_a_capped_one_drops_it(self):
        cut, full = self.same_optimum({'str': 3, 'ap': 5}, 3, ap_exo=True)
        self.assertTrue(stat_runes(full, 'ap'))
        self.assertFalse(stat_runes(cut, 'ap'))

    def test_a_capped_stat_beating_every_free_one_stays_in(self):
        cut, full = self.same_optimum({'str': 3, 'ap': 100}, 3, ap_exo=True)
        self.assertTrue(stat_runes(cut, 'ap'))
        self.assertEqual(len(full.transcendence_columns), len(cut.transcendence_columns))

    def test_a_tie_between_two_free_runes_keeps_one(self):
        cut, full = self.same_optimum({'str': 1, 'int': 1}, 3)
        self.assertEqual(1, sum(1 for key in ('str', 'int') if stat_runes(cut, key)))
        self.assertEqual(2, sum(1 for key in ('str', 'int') if stat_runes(full, key)))

    def test_a_rune_on_a_stat_a_minimum_reads_stays_in(self):
        minimums = {STAT_NAME['int']: 20}
        cut, full = self.same_optimum({'str': 3, 'int': 1}, 3, minimums=minimums)
        self.assertTrue(stat_runes(cut, 'int'))
        self.assertEqual(len(full.transcendence_columns), len(cut.transcendence_columns))

    def test_a_rune_on_a_dracorune_copy_is_dropped_only_when_the_kinds_allow(self):
        self.pieces = [piece('Hat', {self.source: 50}), piece('Cloak', {self.source: 50}),
                       piece('Amulet', {}), piece('Belt', {}), piece('Boots', {})]
        weights = {self.target: 2, 'earthdam': 5, 'pow': 2}
        self.assertTrue(blocking_kinds(self.target) <= blocking_kinds('earthdam'))
        self.assertFalse(blocking_kinds(self.target) <= blocking_kinds('pow'))
        cut, full = self.same_optimum(weights, 3)
        self.assertTrue(stat_runes(full, 'pow'))
        self.assertFalse(stat_runes(cut, 'pow'))
        cut, full = self.same_optimum(weights, 3, 2)
        self.assertTrue(cut.dracorune_columns)
        self.assertTrue(stat_runes(cut, 'pow'))
        self.assertFalse(stat_runes(cut, 'earthdam'))
        self.assertTrue(stat_runes(full, 'earthdam'))

    def test_several_weight_profiles_find_the_same_optimum(self):
        self.pieces = [piece('Hat', {self.source: 50, 'vit': 30}), piece('Cloak', {'int': 40}),
                       piece('Amulet', {'pow': 20}), piece('Belt', {'earthdam': 5}),
                       piece('Boots', {}), piece('Ring', {'cha': 30})]
        profiles = (({'str': 2, 'int': 2, 'cha': 1, 'vit': 0.3, 'pow': 1}, 4, None, {}),
                    ({self.target: 3, 'earthdam': 4, 'pow': 1, 'vit': 0.2, 'init': 0.05}, 5, 2, {}),
                    ({'str': 1, 'agi': 1, 'ap': 8, 'mp': 6, 'dodge': 3, 'lock': 3}, 4, 3,
                     {'ap_exo': True, 'mp_exo': True}),
                    ({'earthresper': 1, 'fireresper': 2, 'vit': 0.5, 'heals': 2}, 3, 1, {}),
                    ({'str': 1, 'int': 1, 'cha': 1, 'agi': 1, 'vit': 0.1, 'crires': 4}, 6, 2, {}))
        for weights, runes, dracorunes, exos in profiles:
            with self.subTest(weights=weights, runes=runes, dracorunes=dracorunes):
                self.same_optimum(weights, runes, dracorunes, **exos)

    def test_a_negative_percent_resist_piece_keeps_the_resist_rune_that_floors_it(self):
        self.pieces = [plain_piece('Weapon', {'fireresper': -2, 'str': 300}), piece('Hat', {}),
                       piece('Cloak', {}), piece('Amulet', {}), piece('Belt', {}),
                       piece('Boots', {})]
        cut, full = self.same_optimum({'str': 3, 'fireresper': 1}, 3)
        self.assertTrue(stat_runes(cut, 'fireresper'))
        self.assertTrue(stat_runes(full, 'fireresper'))

    def test_pruning_cuts_columns(self):
        cut, full = self.same_optimum({'str': 3, 'int': 2, 'agi': 1, 'cha': 1, 'vit': 0.1}, 4)
        self.assertLess(len(cut.transcendence_columns), len(full.transcendence_columns))

    def test_a_column_goes_up_to_the_class_size_and_one_for_ap_mp_and_range(self):
        model = SmallModel(self.pieces + [piece('Ring', {})])
        model.setup(exo_input({'str': 3, 'ap': 200, 'mp': 200, 'range': 200, 'vit': 0.1}, 4,
                              ap_exo=True, mp_exo=True, range_exo=True))
        keys = {rune['id']: rune['stat_key']
                for rune in model_module.readable_transcendence_runes('beta')}
        seen = set()
        for name, (number, rune_id) in model.transcendence_columns.items():
            bound = model.problem.pulp_vars[name].upBound
            size = sum(model.problem.pulp_vars['x_%s' % str(item).replace('-', '_')].upBound
                       for item in model.transcendence_classes[number])
            self.assertLessEqual(bound, size)
            self.assertLessEqual(bound, 4)
            if keys[rune_id] in ROW_BOUND_STATS:
                self.assertEqual(1, bound)
                seen.add(keys[rune_id])
        self.assertEqual(ROW_BOUND_STATS, seen)


class CopyRunesTests(BetaModelTestCase):

    def kept(self, stats, weights, pinned=(), draconized=False, bounded=None):
        by_stat = {key: [beta_rune(key, rank)] for key, rank in stats.items()}
        return [rune['stat_key'] for rune in copy_runes(
            by_stat, {}, set(by_stat), set(), set(pinned), weights, draconized, bounded)]

    def test_a_rune_is_dropped_by_the_gain_of_the_better_one_not_by_its_own_bonus(self):
        self.assertEqual(['str'], self.kept({'str': 1, 'vit': 3}, {'str': 1, 'vit': 0.05}))

    def test_a_row_bound_rune_never_beats_another(self):
        self.assertEqual(['ap', 'vit'], sorted(self.kept({'ap': 4, 'vit': 3}, {'ap': 200, 'vit': 1})))

    def test_a_pinned_stat_is_never_dropped(self):
        stats, weights = {'str': 3, 'int': 3}, {'str': 9, 'int': 1}
        self.assertEqual(['str'], self.kept(stats, weights))
        self.assertEqual(['int', 'str'], sorted(self.kept(stats, weights, pinned={'int'})))

    def test_a_tie_keeps_the_smaller_id_and_a_draconized_tie_the_fewer_kinds(self):
        stats, weights = {'pow': 1, 'dodge': 1}, {'pow': 2, 'dodge': 3}
        self.assertEqual(['pow'], self.kept(stats, weights))
        self.assertEqual(['dodge'], self.kept(stats, weights, draconized=True))

    def test_a_draconized_copy_keeps_a_rune_blocking_fewer_kinds_than_the_better_one(self):
        stats, weights = {'earthdam': 3, 'pow': 3}, {'earthdam': 5, 'pow': 2}
        self.assertEqual(['earthdam'], self.kept(stats, weights))
        self.assertEqual(['earthdam', 'pow'], sorted(self.kept(stats, weights, draconized=True)))

    def test_a_bounded_stat_is_dropped_when_beaten_and_never_beats_another(self):
        stats = {'str': 3, 'summon': 1}
        self.assertEqual(['str'], self.kept(stats, {'str': 9}, bounded={'summon': 1}))
        self.assertEqual(['str', 'summon'], sorted(self.kept(stats, {'str': 1}, bounded={'summon': 100})))
        stats = {'summon': 1, 'vit': 1}
        self.assertEqual(['summon', 'vit'], sorted(self.kept(stats, {'vit': 1}, bounded={'summon': 100})))
