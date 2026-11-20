# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A locked piece stays the piece worn and may still take a rune, counted in the build's runes."""

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_value)

LOCKED_LINE = 10


class ALockedPieceMayTakeARuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.locked = piece('Hat', {self.source: LOCKED_LINE}, 0)
        self.better = piece('Hat', {self.target: 5 * LOCKED_LINE}, 1)
        self.cloak = piece('Cloak', {self.source: LOCKED_LINE // 2})
        self.model = SmallModel([self.locked, self.better, self.cloak])

    def test_the_locked_piece_is_worn_and_draconized(self):
        result = self.solve(self.model, build_input({self.target: 1}, 1,
                                                    locked={'hat': self.locked.id}))
        self.assertEqual(self.locked.id, result.item_per_slot['hat'])
        self.assertEqual({'hat': (self.locked.id, element_key(self.source, self.target))},
                         result.dracorunes)
        self.assertEqual(LOCKED_LINE, stat_value(self.model, self.target))

    def test_the_rune_on_the_locked_piece_counts_in_the_build_runes(self):
        result = self.solve(self.model, build_input({self.target: 1}, 2,
                                                    locked={'hat': self.locked.id}))
        self.assertEqual({'hat', 'cloak'}, set(result.dracorunes))
        self.assertEqual(LOCKED_LINE + LOCKED_LINE // 2, stat_value(self.model, self.target))
