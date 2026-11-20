# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A rune on a weapon moves its characteristic lines in the stat rows and leaves its hits alone."""

from fashionistapulp import dracorune_terms

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         eligible_items, piece, runes, structure)


class AWeaponRuneMovesStatLinesTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        for number, item in enumerate(eligible_items('Weapon')):
            variants = dracorune_terms.item_variants(item, runes(), structure())
            if variants and structure().get_weapon_for_item(item).hits_dict:
                break
        self.weapon = piece('Weapon', {}, number, keep_lines=True)
        self.variant = variants[0]
        self.weights = {structure().get_stat_by_id(stat_id).key: 1
                        for stat_id, change in self.variant.delta if change > 0}
        self.model = SmallModel([self.weapon])

    def test_the_rune_column_sits_only_on_the_stat_rows_it_moves(self):
        self.model.setup(build_input(self.weights, 1))
        lp = self.model.problem.pulp_lp
        name, column = next((name, self.model.problem.pulp_vars[name])
                            for name, (_item_id, key) in self.model.dracorune_columns.items()
                            if key == self.variant.key)
        rows = self.model.restrictions.stat_total_constraints
        expected = {id(rows[structure().get_stat_by_id(stat_id).name]): change
                    for stat_id, change in self.variant.delta}
        expected[id(lp.constraints['draco_link_%d' % self.weapon.id])] = 1
        expected[id(lp.constraints['draco_total'])] = 1
        found = {id(row): row.expr[column] for row in lp.constraints.values()
                 if column in row.expr}
        self.assertEqual(expected, found, name)

    def test_the_rune_column_has_no_objective_coefficient(self):
        self.model.setup(build_input(self.weights, 1))
        objective = self.model.problem.pulp_lp.objective
        self.assertEqual([], [variable.name for variable in objective
                              if variable.name.startswith('draco_')])

    def test_the_solved_rune_goes_on_the_weapon(self):
        result = self.solve(self.model, build_input(self.weights, 1))
        self.assertEqual(['weapon'], list(result.dracorunes))
