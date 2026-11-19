# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A piece with recorded rolls is draconized from its rolled lines, not from the catalogue's."""

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_id,
                                         stat_value)

CATALOGUE = 50
ROLLED = 70


class RecordedRollsAreDraconizedAsRolledTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.hat = piece('Hat', {self.source: CATALOGUE})
        self.model = SmallModel([self.hat],
                                stat_overrides={self.hat.id: {stat_id(self.source): ROLLED}})

    def test_the_variant_moves_the_rolled_value(self):
        variants = {one.key: dict(one.delta)
                    for one in self.model.dracorune_candidates[self.hat.id]}
        self.assertEqual({stat_id(self.source): -ROLLED, stat_id(self.target): ROLLED},
                         variants[element_key(self.source, self.target)])

    def test_the_solved_build_carries_the_rolled_value_on_the_new_stat(self):
        result = self.solve(self.model, build_input({self.target: 1}, 1))
        self.assertEqual({'hat': (self.hat.id, element_key(self.source, self.target))},
                         result.dracorunes)
        self.assertEqual(ROLLED, stat_value(self.model, self.target))
        self.assertEqual(0, stat_value(self.model, self.source))

    def test_without_rolls_the_catalogue_value_moves(self):
        model = SmallModel([self.hat])
        self.solve(model, build_input({self.target: 1}, 1))
        self.assertEqual(CATALOGUE, stat_value(model, self.target))
