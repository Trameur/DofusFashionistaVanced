# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A rune that moves a line onto the stat another piece asks for lets the build wear that piece."""

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_id)

NEEDED = 40


class AConditionMetOnlyByARuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.hat = piece('Hat', {self.source: NEEDED})
        self.amulet = piece('Amulet', {'vit': 300})
        self.amulet.min_stats_to_equip = [(stat_id(self.target), NEEDED)]
        self.model = SmallModel([self.hat, self.amulet])

    def test_without_a_rune_the_piece_is_left_off(self):
        result = self.solve(self.model, build_input({'vit': 1}, 0))
        self.assertNotIn(self.amulet.id, result.item_per_slot.values())

    def test_one_rune_on_another_piece_lets_it_be_worn(self):
        result = self.solve(self.model, build_input({'vit': 1}, 1))
        self.assertEqual(self.amulet.id, result.item_per_slot['amulet'])
        self.assertEqual({'hat': (self.hat.id, element_key(self.source, self.target))},
                         result.dracorunes)

    def test_the_rune_is_kept_although_its_own_lines_carry_no_weight(self):
        self.model.setup(build_input({'vit': 1}, 1))
        self.assertIn('draco_%d_e_%s_%s' % (self.hat.id, self.source, self.target),
                      self.model.dracorune_columns)
