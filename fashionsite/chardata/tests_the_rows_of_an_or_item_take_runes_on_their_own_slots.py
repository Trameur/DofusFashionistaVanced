# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The rows of an OR item each get their own rune columns, linked to their own worn variable."""

from chardata.dracorune_fixtures import (BetaModelTestCase, OrGroupModel, build_input,
                                         columns, element_key, element_move, piece)


class TheRowsOfAnOrItemTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.first = piece('Ring', {self.source: 50}, 0)
        self.second = piece('Ring', {self.source: 30, 'vit': 5}, 1)
        self.model = OrGroupModel([self.first, self.second], {'A': [self.first, self.second]})
        self.key = element_key(self.source, self.target)

    def link(self, row):
        return self.model.problem.pulp_lp.constraints['draco_link_%d' % row.id]

    def test_each_row_has_a_column_and_a_link_to_its_own_worn_variable(self):
        self.model.setup(build_input({self.target: 1}, 2))
        for row in (self.first, self.second):
            worn = self.model.problem.pulp_vars['x_%d' % row.id]
            self.assertEqual(-1, self.link(row).expr[worn])
            self.assertIn('draco_%d_e_%s_%s' % (row.id, self.source, self.target), columns(self.model))

    def test_the_runes_go_on_worn_rows_only(self):
        for allowed in (1, 2):
            self.model.setup(build_input({self.target: 1}, allowed))
            self.model.run()
            worn = {row.id: self.model.problem.pulp_vars['x_%d' % row.id].varValue
                    for row in (self.first, self.second)}
            for item_id, _key in self.model.chosen_dracorunes():
                self.assertGreaterEqual(worn[item_id], 1)
            self.assertEqual(allowed, len(self.model.chosen_dracorunes()))

    def test_the_or_count_still_caps_the_copies_with_runes_on(self):
        self.model.setup(build_input({self.target: 1}, 2))
        self.model.run()
        total = sum(self.model.problem.pulp_vars['x_%d' % row.id].varValue
                    for row in (self.first, self.second))
        self.assertLessEqual(total, 2)
        result = self.model.get_result_minimal()
        self.assertEqual(2, len(result.dracorunes))

    def test_forbidding_one_row_removes_the_columns_of_both(self):
        self.model.setup(build_input({self.target: 1}, 2, forbidden=[self.first.id]))
        self.assertEqual([], columns(self.model))
