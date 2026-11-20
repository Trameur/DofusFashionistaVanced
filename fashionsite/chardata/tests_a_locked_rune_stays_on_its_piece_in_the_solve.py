# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The rune of a locked piece is worn again by the next solve, counts in the build's runes, and a stale lock never breaks the model."""

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_value)

LINE = 10


class ALockedRuneStaysOnItsPieceTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.key = element_key(self.source, self.target)
        self.hat = piece('Hat', {self.source: LINE}, 0)
        self.cloak = piece('Cloak', {self.source: LINE})
        self.model = SmallModel([self.hat, self.cloak])

    def model_input(self, count, locks, locked, weights=None):
        found = build_input(weights or {self.source: 1}, count, locked=locked)
        if locks is not None:
            found.options['dracorune_locks'] = locks
        return found

    def test_a_rune_that_loses_value_is_still_worn_on_the_locked_piece(self):
        result = self.solve(self.model, self.model_input(
            1, {'hat': self.key}, {'hat': self.hat.id}))
        self.assertEqual(self.hat.id, result.item_per_slot['hat'])
        self.assertEqual({'hat': (self.hat.id, self.key)}, result.dracorunes)
        self.assertEqual(LINE, stat_value(self.model, self.target))

    def test_without_the_lock_the_same_rune_is_not_worn(self):
        result = self.solve(self.model, self.model_input(1, None, {'hat': self.hat.id}))
        self.assertFalse(result.dracorunes)

    def test_the_locked_runes_count_in_the_limit_and_raise_it_when_it_is_lower(self):
        result = self.solve(self.model, self.model_input(
            1, {'hat': self.key, 'cloak': self.key},
            {'hat': self.hat.id, 'cloak': self.cloak.id}))
        self.assertEqual({'hat', 'cloak'}, set(result.dracorunes))
        self.assertEqual(2 * LINE, stat_value(self.model, self.target))

    def test_a_limit_above_the_locked_runes_leaves_room_for_the_solver(self):
        free = piece('Amulet', {self.source: LINE})
        model = SmallModel([self.hat, free])
        result = self.solve(model, self.model_input(
            2, {'hat': self.key}, {'hat': self.hat.id}, {self.target: 1}))
        self.assertEqual({'hat', 'amulet'}, set(result.dracorunes))

    def test_the_forced_rune_is_kept_even_when_the_pruning_would_drop_it(self):
        weights = {self.source: 5, self.target: 0}
        result = self.solve(self.model, self.model_input(
            3, {'hat': self.key}, {'hat': self.hat.id}, weights))
        self.assertEqual({'hat': (self.hat.id, self.key)}, result.dracorunes)

    def assert_ignored(self, locks, locked, weights=None):
        result = self.solve(self.model, self.model_input(1, locks, locked, weights))
        self.assertFalse(result.dracorunes)
        self.assertEqual([], [name for name in self.model.problem.pulp_vars
                              if name.startswith('draco_') and
                              self.model.problem.pulp_vars[name].lowBound])

    def test_an_entry_for_a_slot_that_is_not_locked_is_ignored(self):
        self.assert_ignored({'hat': self.key}, {})

    def test_an_entry_for_another_locked_piece_is_ignored(self):
        other = piece('Hat', {self.target: LINE}, 1)
        self.model = SmallModel([self.hat, other])
        self.assert_ignored({'hat': self.key}, {'hat': other.id}, {self.target: 1})

    def test_an_entry_whose_variant_no_longer_exists_is_ignored(self):
        self.assert_ignored({'hat': 'element:no>such'}, {'hat': self.hat.id})

    def test_an_unreadable_entry_is_ignored(self):
        for locks in ({'hat': None}, {'hat': 7}, {None: self.key}, {'weapon': self.key}, 'hat', []):
            with self.subTest(locks=locks):
                self.assert_ignored(locks, {'hat': self.hat.id})

    def test_a_stale_entry_does_not_make_the_model_infeasible(self):
        result = self.solve(self.model, self.model_input(
            1, {'hat': 'element:no>such', 'cloak': self.key}, {'hat': self.hat.id}))
        self.assertEqual(self.hat.id, result.item_per_slot['hat'])
        self.assertFalse(result.dracorunes)

    def test_stale_entries_do_not_raise_the_limit(self):
        other = piece('Hat', {self.target: LINE}, 1)
        free = piece('Amulet', {self.source: LINE})
        model = SmallModel([other, self.cloak, free])
        result = self.solve(model, self.model_input(
            1, {'hat': self.key, 'cloak': 'element:no>such'},
            {'hat': other.id, 'cloak': self.cloak.id}, {self.target: 1}))
        self.assertEqual(1, len(result.dracorunes))

    def test_a_pool_model_forgets_the_locks_of_the_last_build(self):
        self.solve(self.model, self.model_input(1, {'hat': self.key}, {'hat': self.hat.id}))
        result = self.solve(self.model, self.model_input(1, None, {'hat': self.hat.id}))
        self.assertFalse(result.dracorunes)
