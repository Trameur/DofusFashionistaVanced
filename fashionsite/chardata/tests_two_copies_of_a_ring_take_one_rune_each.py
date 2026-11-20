# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Two copies of a ring can take one rune each, and each rune lands on its own ring slot."""

from fashionistapulp.modelresult import ModelResultMinimal

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_value)

LINE = 50


class TwoCopiesOfARingTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.ring = piece('Ring', {self.source: LINE})
        self.model = SmallModel([self.ring])
        self.key = element_key(self.source, self.target)

    def test_a_rune_column_of_a_doubled_ring_goes_up_to_two(self):
        self.model.setup(build_input({self.target: 1}, 2))
        name = 'draco_%d_e_%s_%s' % (self.ring.id, self.source, self.target)
        self.assertEqual(2, self.model.problem.pulp_vars[name].upBound)

    def test_two_runes_go_on_the_two_copies(self):
        result = self.solve(self.model, build_input({self.target: 1}, 2))
        self.assertEqual(self.ring.id, result.item_per_slot['ring1'])
        self.assertEqual(self.ring.id, result.item_per_slot['ring2'])
        self.assertEqual({'ring1': (self.ring.id, self.key), 'ring2': (self.ring.id, self.key)},
                         result.dracorunes)
        self.assertEqual(2 * LINE, stat_value(self.model, self.target))

    def test_one_rune_goes_on_one_copy(self):
        result = self.solve(self.model, build_input({self.target: 2, self.source: 1}, 1))
        self.assertEqual(self.ring.id, result.item_per_slot['ring2'])
        self.assertEqual({'ring1': (self.ring.id, self.key)}, result.dracorunes)
        self.assertEqual(LINE, stat_value(self.model, self.target))
        self.assertEqual(LINE, stat_value(self.model, self.source))


class TwoRunesOfOneRingFillItsSlotsInOrderTests(BetaModelTestCase):

    def test_two_variants_of_one_ring_take_one_slot_each(self):
        minimal = ModelResultMinimal({'ring1': 7, 'ring2': 7, 'hat': 3}, {}, None)
        minimal.place_dracorunes([(7, 'resistance:fire>air'), (7, 'element:str>agi')])
        self.assertEqual({'ring1': (7, 'element:str>agi'), 'ring2': (7, 'resistance:fire>air')},
                         minimal.dracorunes)

    def test_a_rune_without_its_piece_is_left_out(self):
        minimal = ModelResultMinimal({'ring1': 7, 'ring2': None}, {}, None)
        with self.assertLogs('fashionistapulp.modelresult', 'WARNING'):
            minimal.place_dracorunes([(7, 'power'), (7, 'power')])
        self.assertEqual({'ring1': (7, 'power')}, minimal.dracorunes)

    def test_a_minimal_result_pickled_before_the_runes_reads_none(self):
        minimal = ModelResultMinimal.__new__(ModelResultMinimal)
        minimal.__dict__.update({'item_per_slot': {}, 'input': {}, 'stats': None})
        self.assertIsNone(minimal.dracorunes)
