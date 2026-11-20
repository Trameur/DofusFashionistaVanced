# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver puts at most the allowed dracorunes on a build, and all of them when each pays."""

from fashionistapulp.dofus_constants import TYPE_NAME_TO_SLOT_NUMBER

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, runes,
                                         stat_value)

LINE = 50


class EveryWornPieceGainsFromARuneTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.pieces = [piece(type_name, {self.source: LINE}, number)
                       for type_name in runes()['item_types']
                       for number in range(TYPE_NAME_TO_SLOT_NUMBER[type_name])]
        self.slots = len(self.pieces)
        self.model = SmallModel(self.pieces)

    def test_the_build_takes_exactly_n_runes_up_to_its_slots(self):
        for allowed in (1, 2, self.slots, self.slots + 1):
            with self.subTest(allowed=allowed):
                result = self.solve(self.model, build_input({self.target: 1}, allowed))
                used = min(allowed, self.slots)
                self.assertEqual(used, len(self.model.chosen_dracorunes()))
                self.assertEqual(used, len(result.dracorunes))
                self.assertEqual(used * LINE, stat_value(self.model, self.target))
                self.assertEqual(
                    {element_key(self.source, self.target)},
                    {key for _item_id, key in result.dracorunes.values()})

    def test_every_slot_of_the_runes_file_is_offered(self):
        self.assertEqual(self.slots, len({one.id for one in self.pieces}))
        result = self.solve(self.model, build_input({self.target: 1}, self.slots))
        self.assertEqual(self.slots, len([slot for slot, item_id in result.item_per_slot.items()
                                          if item_id is not None]))

    def test_a_retry_on_a_changed_objective_keeps_the_runes_and_their_count(self):
        self.model.setup(build_input({self.target: 1, 'vit': 0}, 2))
        before = dict(self.model.dracorune_columns)
        self.model.run(change_of=True)
        self.assertEqual('Optimal', self.model.get_solved_status())
        self.assertEqual(before, self.model.dracorune_columns)
        self.assertEqual(2, -self.model.problem.pulp_lp.constraints['draco_total'].constant)
        self.assertEqual(2, len(self.model.chosen_dracorunes()))

    def test_no_option_puts_no_rune(self):
        for options in (build_input({self.target: 1}), build_input({self.target: 1}, 0)):
            with self.subTest(options=options.options):
                result = self.solve(self.model, options)
                self.assertIsNone(result.dracorunes)
                self.assertEqual(0, stat_value(self.model, self.target))
