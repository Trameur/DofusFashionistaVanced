# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A rune the solution meets every row and its objective without is left off the result; a rune it needs stays."""

from unittest import mock

from chardata.dracorune_fixtures import (BetaModelTestCase, SmallModel, build_input,
                                         element_key, element_move, piece, stat_id, structure)
from fashionistapulp.dracorunes import RESISTANCE_NAMES
from fashionistapulp.model import Model

NEEDED = 40
EARTH_RESIST = 30
SPARE = 5
UNREACHABLE_VITALITY = 1000


class AWastedRuneIsRemovedTests(BetaModelTestCase):

    def setUp(self):
        super().setUp()
        self.source, self.target = element_move()
        self.key = element_key(self.source, self.target)
        self.hat = piece('Hat', {self.source: NEEDED, 'vit': 10})
        self.amulet = piece('Amulet', {'vit': 300})
        self.amulet.min_stats_to_equip = [(stat_id(self.target), NEEDED)]
        self.boots = piece('Boots', {self.target: NEEDED, 'vit': 10})

    def column(self, model):
        return next(model.problem.pulp_vars[name]
                    for name, (item_id, key) in model.dracorune_columns.items()
                    if item_id == self.hat.id and key == self.key)

    def forced(self, model, model_input):
        """The model solved with the hat's rune on, then the row that forced it removed."""
        model.setup(model_input)
        lp = model.problem.pulp_lp
        lp.addConstraint(self.column(model) >= 1, 'force_the_rune')
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        self.assertEqual(1, round(self.column(model).varValue))
        del lp.constraints['force_the_rune']
        return lp.objective.value()

    def test_a_needed_rune_stays(self):
        result = self.solve(SmallModel([self.hat, self.amulet]), build_input({'vit': 1}, 1))
        self.assertEqual(self.amulet.id, result.item_per_slot['amulet'])
        self.assertEqual({'hat': (self.hat.id, self.key)}, result.dracorunes)

    def test_a_rune_another_piece_makes_useless_is_dropped(self):
        model = SmallModel([self.hat, self.amulet, self.boots])
        model_input = build_input({'vit': 1}, 1)
        objective = self.forced(model, model_input)
        values = {variable.name: variable.varValue for variable in model.problem.pulp_lp.variables()}
        result = model.get_result_minimal()
        self.assertEqual({self.hat.id, self.amulet.id, self.boots.id},
                         {item_id for item_id in result.item_per_slot.values() if item_id})
        self.assertIsNone(result.dracorunes)
        self.assertEqual(values, {variable.name: variable.varValue
                                  for variable in model.problem.pulp_lp.variables()})
        unforced = SmallModel([self.hat, self.amulet, self.boots])
        self.solve(unforced, model_input)
        self.assertAlmostEqual(unforced.problem.pulp_lp.objective.value(), objective)

    def test_a_rune_that_holds_a_row_up_stays_once_forced(self):
        model = SmallModel([self.hat, self.amulet])
        self.forced(model, build_input({'vit': 1}, 1))
        self.assertEqual({'hat': (self.hat.id, self.key)}, model.get_result_minimal().dracorunes)

    def resistance_case(self, over_the_cap, weights, minimums=None):
        """(model, the hat's rune) solved with the hat's earth resist forced onto fire, boots that far from the fire cap."""
        fire = structure().get_stat_by_key('fireresper')
        cap = SmallModel([]).stat_maximum[fire.name]
        key = 'resistance:%s>%s' % (RESISTANCE_NAMES['earth'], RESISTANCE_NAMES['fire'])
        hat = piece('Hat', {'earthresper': EARTH_RESIST, 'vit': 10})
        boots = piece('Boots', {'fireresper': cap + over_the_cap, 'vit': 10})
        model = SmallModel([hat, boots])
        model.setup(build_input(weights, 1, minimums=minimums))
        column = next(model.problem.pulp_vars[name]
                      for name, (item_id, rune) in model.dracorune_columns.items()
                      if item_id == hat.id and rune == key)
        lp = model.problem.pulp_lp
        lp.addConstraint(column >= 1, 'force_the_rune')
        model.run()
        self.assertEqual('Optimal', model.get_solved_status())
        del lp.constraints['force_the_rune']
        self.assertEqual(cap, model.problem.pulp_vars['stat_%d' % fire.id].varValue)
        self.assertEqual(cap + over_the_cap + EARTH_RESIST,
                         model.problem.pulp_vars['total_%d' % fire.id].varValue)
        return model, {'hat': (hat.id, key)}

    def runes_shown(self, model):
        values = {variable.name: variable.varValue for variable in model.problem.pulp_lp.variables()}
        shown = model.get_result_minimal().dracorunes
        self.assertEqual(values, {variable.name: variable.varValue
                                  for variable in model.problem.pulp_lp.variables()})
        return shown

    def test_a_resistance_rune_whose_target_stays_over_the_cap_is_dropped(self):
        model, _rune = self.resistance_case(10, {'fireresper': 1, 'vit': 1})
        self.assertIsNone(self.runes_shown(model))

    def test_a_resistance_rune_that_lifts_its_target_to_the_cap_stays(self):
        model, rune = self.resistance_case(-10, {'fireresper': 1, 'vit': 1})
        self.assertEqual(rune, self.runes_shown(model))

    def test_a_resistance_rune_a_minimum_does_not_need_is_dropped_under_the_cap(self):
        fire = structure().get_stat_by_key('fireresper').name
        cap = SmallModel([]).stat_maximum[fire]
        model, _rune = self.resistance_case(-10, {'vit': 1}, {fire: cap - 20})
        self.assertIsNone(self.runes_shown(model))

    def test_a_kept_rune_is_put_back_before_the_next_one_is_weighed(self):
        for needed_type, spare_type in (('Hat', 'Boots'), ('Boots', 'Hat')):
            with self.subTest(needed=needed_type):
                needed = piece(needed_type, {self.source: NEEDED, 'vit': 10})
                spare = piece(spare_type, {self.source: SPARE, 'vit': 10})
                model = SmallModel([needed, spare, self.amulet])
                model.setup(build_input({'vit': 1}, 2))
                lp = model.problem.pulp_lp
                forced = []
                for name, (item_id, key) in model.dracorune_columns.items():
                    if key == self.key:
                        forced.append('force_%s' % item_id)
                        lp.addConstraint(model.problem.pulp_vars[name] >= 1, forced[-1])
                model.run()
                self.assertEqual('Optimal', model.get_solved_status())
                self.assertEqual(sorted([(needed.id, self.key), (spare.id, self.key)]),
                                 sorted(model.chosen_dracorunes()))
                for name in forced:
                    del lp.constraints[name]
                shown = self.runes_shown(model)
                self.assertEqual({needed_type.lower(): (needed.id, self.key)}, shown)

    def test_a_solve_that_is_not_optimal_keeps_its_runes_unchecked(self):
        model = SmallModel([self.hat, self.amulet, self.boots])
        vitality = structure().get_stat_by_key('vit').name
        model.setup(build_input({'vit': 1}, 1, minimums={vitality: UNREACHABLE_VITALITY}))
        model.problem.pulp_lp.addConstraint(self.column(model) >= 1, 'force_the_rune')
        model.run()
        self.assertEqual('Infeasible', model.get_solved_status())
        chosen = model.chosen_dracorunes()
        self.assertEqual([(self.hat.id, self.key)], chosen)
        values = {variable.name: variable.varValue for variable in model.problem.pulp_lp.variables()}
        with mock.patch.object(Model, '_solution_holds', return_value=True) as holds:
            self.assertEqual(chosen, model.useful_dracorunes(chosen))
        holds.assert_not_called()
        self.assertEqual(values, {variable.name: variable.varValue
                                  for variable in model.problem.pulp_lp.variables()})

    def test_a_solution_with_no_rune_is_not_checked(self):
        with mock.patch.object(Model, '_solution_holds') as holds:
            result = self.solve(SmallModel([self.hat, self.amulet]), build_input({'vit': 1}, 0))
            self.assertIsNone(result.dracorunes)
            result = self.solve(SmallModel([self.hat, self.boots]), build_input({'vit': 1}, 1))
            self.assertIsNone(result.dracorunes)
        holds.assert_not_called()
