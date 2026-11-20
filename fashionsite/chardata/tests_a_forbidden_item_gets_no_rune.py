# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A forbidden piece gets no rune column, and the rune goes on a piece the build may wear."""

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         columns, element_key, element_move, piece)


class AForbiddenPieceGetsNoRuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.best = piece('Hat', {self.source: 80}, 0)
        self.other = piece('Hat', {self.source: 30}, 1)
        self.model = SmallModel([self.best, self.other])

    def test_the_best_piece_takes_the_rune_when_allowed(self):
        result = self.solve(self.model, build_input({self.target: 1}, 1))
        self.assertEqual({'hat': (self.best.id, element_key(self.source, self.target))},
                         result.dracorunes)

    def test_a_forbidden_piece_has_no_rune_column(self):
        result = self.solve(self.model, build_input({self.target: 1}, 1,
                                                    forbidden=[self.best.id]))
        self.assertEqual([], [name for name in columns(self.model)
                              if name.startswith('draco_%d_' % self.best.id)])
        self.assertNotIn('draco_link_%d' % self.best.id, self.model.problem.pulp_lp.constraints)
        self.assertEqual({'hat': (self.other.id, element_key(self.source, self.target))},
                         result.dracorunes)
