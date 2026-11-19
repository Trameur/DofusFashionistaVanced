# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A draconized piece still counts for its set and still has to meet its own condition."""

from copy import deepcopy

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_id,
                                         stat_value, structure)

BONUS = 300
LINE = 60


class ADraconizedPieceCountsForItsSetTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.hat = piece('Hat', {self.source: LINE})
        self.cloak = piece('Cloak', {'vit': 1})
        self.set = deepcopy(structure().get_sets_list()[0])
        self.set.items = [self.hat.id, self.cloak.id]
        self.set.bonus = [(2, stat_id('vit'), BONUS)]
        self.set.max_caps = []
        self.hat.set = self.cloak.set = self.set.id
        self.model = SmallModel([self.hat, self.cloak], [self.set])

    def test_the_set_bonus_of_two_pieces_counts_the_draconized_one(self):
        result = self.solve(self.model, build_input({self.target: 1, 'vit': 1}, 1))
        self.assertEqual({'hat': (self.hat.id, element_key(self.source, self.target))},
                         result.dracorunes)
        self.assertEqual(self.cloak.id, result.item_per_slot['cloak'])
        self.assertEqual(BONUS + 1, stat_value(self.model, 'vit'))
        self.assertEqual(LINE, stat_value(self.model, self.target))


class ADraconizedPieceMeetsItsOwnConditionTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()

    def model(self, condition):
        hat = piece('Hat', {self.source: LINE, 'vit': 100})
        if condition:
            hat.min_stats_to_equip = [(stat_id(self.source), LINE // 2)]
        return hat, SmallModel([hat])

    def test_without_its_condition_the_piece_takes_the_rune(self):
        hat, model = self.model(condition=False)
        result = self.solve(model, build_input({self.target: 1, 'vit': 1}, 1))
        self.assertEqual({'hat': (hat.id, element_key(self.source, self.target))},
                         result.dracorunes)

    def test_a_rune_that_breaks_its_own_condition_is_not_taken(self):
        hat, model = self.model(condition=True)
        result = self.solve(model, build_input({self.target: 1, 'vit': 1}, 1))
        self.assertEqual(hat.id, result.item_per_slot['hat'])
        self.assertIsNone(result.dracorunes)
        self.assertEqual(LINE, stat_value(model, self.source))
