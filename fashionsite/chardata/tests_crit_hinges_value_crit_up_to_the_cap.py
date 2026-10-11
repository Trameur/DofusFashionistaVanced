# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Crit hinges pay a crit point at the objective weight up to each breakpoint and drop less above it."""

import pulp
from django.test import SimpleTestCase

from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.model import Model, ModelInput
from fashionistapulp.model_pool import borrow_model, return_model
from fashionistapulp.structure import get_structure, set_current_game_version

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True, 'trophies': True,
           'dragoturkey': True, 'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
           'shields': True}
WEIGHT = 100
KEY_WITHOUT_HINGES = 716856835884310526


def _input(hinges=None):
    base = {name: 0 for name, _key in STATS_NAMES}
    base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
    return ModelInput(200, base, {}, {}, [], {'ch': WEIGHT}, dict(OPTIONS), 'Iop', 995, [], {},
                      crit_hinges=hinges)


class _Dofus3Model(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')
        self.crit_column = 'stat_%s' % get_structure('dofus3').get_stat_by_key('ch').id

    def solve(self, hinges=None):
        model = borrow_model()
        try:
            model.setup(_input(hinges))
            model.run()
            self.assertEqual('Optimal', model.get_solved_status())
            lp = model.problem.pulp_lp
            rest = sum(coefficient * variable.varValue for variable, coefficient in lp.objective.items()
                       if variable.name != self.crit_column and not variable.name.startswith('crithinge'))
            return {'objective': model.problem.objective_value, 'rest': rest,
                    'crit': model.problem.get_result()[self.crit_column],
                    'items': model.get_result_minimal().item_per_slot,
                    'columns': sorted(variable.name for variable in lp.variables()),
                    'constraints': sorted(lp.constraints)}
        finally:
            return_model(model)


class TheHingesPayTheCritUpToTheirBreakpointTests(_Dofus3Model):

    def setUp(self):
        super().setUp()
        self.free = self.solve()
        self.assertGreater(self.free['crit'], 6)

    def value(self, crit, hinges):
        return WEIGHT * crit - sum(drop * max(0, crit - breakpoint) for breakpoint, drop in hinges)

    def test_without_hinges_the_problem_is_the_one_of_before(self):
        again = self.solve(())
        self.assertEqual(self.free, again)
        self.assertEqual([], [name for name in again['columns'] if name.startswith('crithinge')])

    def test_a_hinge_pays_the_crit_up_to_its_breakpoint_only(self):
        hinges = ((int(self.free['crit']) // 2, WEIGHT),)
        solved = self.solve(hinges)
        self.assertGreaterEqual(solved['crit'], hinges[0][0])
        self.assertAlmostEqual(solved['rest'] + WEIGHT * min(solved['crit'], hinges[0][0]),
                               solved['objective'])
        self.assertAlmostEqual(solved['rest'] + self.value(solved['crit'], hinges), solved['objective'])

    def test_two_hinges_pay_a_slope_between_them(self):
        third = int(self.free['crit']) // 3
        hinges = ((third, 60), (2 * third, 40))
        solved = self.solve(hinges)
        self.assertGreaterEqual(solved['crit'], 2 * third)
        self.assertAlmostEqual(solved['rest'] + WEIGHT * third + 40 * third, solved['objective'])
        self.assertAlmostEqual(solved['rest'] + self.value(solved['crit'], hinges), solved['objective'])

    def test_a_negative_crit_keeps_the_first_slope(self):
        model = borrow_model()
        try:
            model.setup(_input(((10, WEIGHT),)))
            lp = model.problem.pulp_lp
            for variable in lp.variables():
                variable.varValue = 0
            model.problem.pulp_vars[self.crit_column].varValue = -7
            self.assertEqual(-7 * WEIGHT, pulp.value(lp.objective))
        finally:
            return_model(model)

    def hinge_row(self, breakpoint=10):
        model = borrow_model()
        self.addCleanup(return_model, model)
        model.setup(_input(((breakpoint, WEIGHT),)))
        lp = model.problem.pulp_lp
        for variable in lp.variables():
            variable.varValue = 0
        return model, lp.constraints['crit_hinge_0']

    def test_the_row_of_a_hinge_keeps_the_crit_over_its_breakpoint_in_the_hinge_column(self):
        _model, row = self.hinge_row(10)
        self.assertEqual({'crithinge_0': 1, self.crit_column: -1},
                         {variable.name: coefficient for variable, coefficient in row.items()})
        self.assertEqual(pulp.LpConstraintGE, row.sense)
        self.assertEqual(10, row.value())

    def test_a_crit_above_the_breakpoint_holds_the_hinge_column_at_the_excess(self):
        model, row = self.hinge_row(10)
        model.problem.pulp_vars[self.crit_column].varValue = 25
        hinge = model.problem.pulp_vars['crithinge_0']
        for value, holds in ((14.5, False), (15, True), (15.5, True)):
            with self.subTest(hinge=value):
                hinge.varValue = value
                self.assertEqual(holds, row.valid())

    def test_a_crit_under_the_breakpoint_holds_the_row_with_the_hinge_column_at_zero(self):
        model, row = self.hinge_row(10)
        for crit in (10, 9, 0, -7):
            with self.subTest(crit=crit):
                model.problem.pulp_vars[self.crit_column].varValue = crit
                self.assertTrue(row.valid())

    def test_a_rising_slope_is_refused(self):
        model = borrow_model()
        try:
            with self.assertRaises(ValueError):
                model.setup(_input(((10, -1),)))
        finally:
            return_model(model)


class TheModelForgetsTheHingesOfItsLastSetupTests(_Dofus3Model):

    def shape(self, model):
        lp = model.problem.pulp_lp
        return {'rows': len(lp.constraints), 'columns': len(lp.variables()),
                'hinge_rows': sorted(name for name in lp.constraints if name.startswith('crit_hinge_')),
                'hinge_columns': sorted(variable.name for variable in lp.variables()
                                        if variable.name.startswith('crithinge_')),
                'hinge_vars': sorted(name for name in model.problem.pulp_vars if name.startswith('crithinge_'))}

    def test_each_setup_has_the_rows_and_columns_of_its_own_hinges_only(self):
        model = Model()
        model.setup(_input())
        plain = self.shape(model)
        self.assertEqual([], plain['hinge_rows'] + plain['hinge_columns'] + plain['hinge_vars'])
        model.setup(_input(((10, 5.5), (20, 3))))
        two = self.shape(model)
        self.assertEqual(['crit_hinge_0', 'crit_hinge_1'], two['hinge_rows'])
        self.assertEqual(['crithinge_0', 'crithinge_1'], two['hinge_columns'])
        self.assertEqual(['crithinge_0', 'crithinge_1'], two['hinge_vars'])
        self.assertEqual((plain['rows'] + 2, plain['columns'] + 2), (two['rows'], two['columns']))
        model.setup(_input())
        self.assertEqual(plain, self.shape(model))
        model.setup(_input(((30, 4),)))
        one = self.shape(model)
        self.assertEqual((['crit_hinge_0'], ['crithinge_0'], ['crithinge_0']),
                         (one['hinge_rows'], one['hinge_columns'], one['hinge_vars']))
        self.assertEqual((plain['rows'] + 1, plain['columns'] + 1), (one['rows'], one['columns']))

    def test_a_solve_after_a_hinged_one_reads_the_same_problem(self):
        before = self.solve()
        hinged = self.solve(((int(before['crit']) // 2, WEIGHT),))
        after = self.solve()
        self.assertEqual(before, after)
        self.assertEqual(['crithinge_0'], [name for name in hinged['columns']
                                           if name not in before['columns']])
        self.assertEqual(['crit_hinge_0'], [name for name in hinged['constraints']
                                            if name not in before['constraints']])


class TheHingesChangeTheKeysTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('dofus3')
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_no_hinge_keeps_the_keys_of_before(self):
        """An input without hinges keeps its stored cache key."""
        old = _input()
        del old.crit_hinges
        for plain in (_input(), _input(()), _input(None), old):
            with self.subTest(hinges=getattr(plain, 'crit_hinges', 'absent')):
                self.assertEqual(KEY_WITHOUT_HINGES, plain.cache_key())
                self.assertEqual(hash(_input()), hash(plain))

    def test_hinges_change_the_keys(self):
        plain, hinged = _input(), _input(((10, 5.5),))
        self.assertNotEqual(plain.cache_key(), hinged.cache_key())
        self.assertNotEqual(hash(plain), hash(hinged))
        for other in (((10, 6.5),), ((11, 5.5),), ((10, 5.5), (20, 1))):
            with self.subTest(other=other):
                self.assertNotEqual(hinged.cache_key(), _input(other).cache_key())
                self.assertNotEqual(hash(hinged), hash(_input(other)))
