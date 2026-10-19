# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The rows the site owns are the model the solver reads, on a fresh model, a pooled one and after a rebuild."""
import os
import tempfile

from django.test import SimpleTestCase, TestCase
from pulp import LpContinuous, LpInteger, LpMaximize, LpProblem, LpVariable

from chardata.tests_a_build_with_no_set_is_shown_its_closest_set import _solver_available
from chardata.tests_the_row_table_support import holds
from fashionistapulp.dofus_constants import STATS_NAMES
from fashionistapulp.lpproblem import LpProblem2, RowHandle
from fashionistapulp.model import (EFFECTIVE_HP_CONSTRAINT, EFFECTIVE_HP_MINIMUM, Model,
                                   ModelInput)
from fashionistapulp.structure import get_structure, set_current_game_version

OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False, 'dofus': True, 'trophies': True,
           'dragoturkey': True, 'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
           'shields': True}


def _mps(lp):
    handle, path = tempfile.mkstemp(suffix='.mps')
    os.close(handle)
    try:
        lp.writeMPS(path)
        with open(path, 'rb') as written:
            return written.read()
    finally:
        os.remove(path)


def _reference_mps(problem):
    """The problem written from its row table alone, with the library's plain API."""
    lp = LpProblem('The Whiskas Problem', LpMaximize)
    columns = {}

    def expression(terms):
        total = 0
        for coefficient, name in terms:
            if name not in columns:
                low, high, integer = problem.variable_spec(name)
                columns[name] = LpVariable(name, low, high, LpInteger if integer else LpContinuous)
            total = total + coefficient * columns[name]
        return total

    for row in problem.rows():
        built = expression(row.terms)
        if row.sense == '<=':
            lp.addConstraint(built <= row.rhs, row.name)
        elif row.sense == '>=':
            lp.addConstraint(built >= row.rhs, row.name)
        else:
            lp.addConstraint(built == row.rhs, row.name)
    lp.objective = expression(problem.objective_terms())
    return _mps(lp)


class RowHandleTests(SimpleTestCase):

    def _problem(self):
        problem = LpProblem2()
        problem.declare_variable('a', 0, 10)
        problem.declare_variable('b', 0, 10)
        return problem

    def test_change_rhs_and_the_constant_round_trip(self):
        problem = self._problem()
        row = problem.add_row([(1, 'a'), (2, 'b')], '<=', 4, 'cap')
        self.assertIsInstance(row, RowHandle)
        self.assertEqual(-4, row.constant)
        self.assertEqual(-4, problem.pulp_lp.constraints['cap'].constant)
        row.changeRHS(9)
        self.assertEqual(9, row.rhs)
        self.assertEqual(-9, row.constant)
        self.assertEqual(-9, problem.pulp_lp.constraints['cap'].constant)
        row.changeRHS(4)
        self.assertEqual(-4, problem.pulp_lp.constraints['cap'].constant)

    def test_an_unchanged_right_hand_side_touches_nothing(self):
        problem = self._problem()
        row = problem.add_row([(1, 'a')], '<=', 4, 'cap')
        live = problem.pulp_lp.constraints['cap']
        calls = []
        problem._row_changed = calls.append
        row.changeRHS(4)
        self.assertEqual([], calls)
        row.changeRHS(5)
        self.assertEqual([row], calls)
        self.assertIs(live, problem.pulp_lp.constraints['cap'])

    def test_a_duplicate_name_is_refused(self):
        problem = self._problem()
        problem.add_row([(1, 'a')], '<=', 4, 'cap')
        with self.assertRaises(ValueError):
            problem.add_row([(1, 'b')], '<=', 4, 'cap')

    def test_an_unnamed_row_is_numbered_as_the_library_numbers_it(self):
        problem = self._problem()
        first = problem.add_row([(1, 'a')], '<=', 4)
        problem.add_row([(1, 'b')], '==', 2, 'named')
        second = problem.add_row([(1, 'b')], '>=', 1)
        self.assertEqual(['_C1', 'named', '_C2'], problem.row_names())
        self.assertEqual(['_C1', 'named', '_C2'], list(problem.pulp_lp.constraints))
        self.assertEqual(('_C1', '_C2'), (first.name, second.name))

    def test_a_row_naming_an_unknown_variable_is_refused(self):
        with self.assertRaises(KeyError):
            self._problem().add_row([(1, 'missing')], '<=', 4)

    def test_a_row_with_no_term_is_a_handle_and_no_row(self):
        problem = self._problem()
        row = problem.add_row([], '<=', 4)
        self.assertEqual((), row.terms)
        self.assertEqual([], problem.row_names())
        with self.assertRaises(TypeError):
            problem.add_row([], '<=', -1)

    def test_only_the_variables_a_row_names_are_columns(self):
        problem = self._problem()
        problem.add_row([(1, 'a')], '<=', 4, 'cap')
        problem.set_objective([(1, 'a')])
        self.assertEqual(['a'], [v.name for v in problem.pulp_lp.variables()])

    def test_a_row_removed_and_added_again_sits_after_the_others(self):
        problem = self._problem()
        problem.add_row([(1, 'a')], '<=', 4, 'one')
        problem.add_row([(1, 'b')], '<=', 4, 'two')
        problem.add_row([(1, 'a'), (1, 'b')], '<=', 6, 'three')
        problem.pulp_lp
        problem.remove_rows(['one'])
        problem.add_row([(1, 'a')], '<=', 5, 'one')
        self.assertEqual(['two', 'three', 'one'], list(problem.pulp_lp.constraints))
        self.assertEqual(-5, problem.pulp_lp.constraints['one'].constant)

    def test_a_row_removed_and_added_unchanged_is_the_same_handle(self):
        problem = self._problem()
        first = problem.add_row([(1, 'a')], '<=', 4, 'one')
        problem.pulp_lp
        problem.remove_rows(['one'])
        again = problem.add_row([(1, 'a')], '<=', 4, 'one')
        self.assertIs(first, again)
        self.assertEqual(['one'], list(problem.pulp_lp.constraints))

    def test_the_library_problem_after_a_removal_is_the_one_a_fresh_build_gives(self):
        problem = self._problem()
        problem.add_row([(1, 'a')], '<=', 4, 'one')
        problem.add_row([(1, 'b')], '<=', 4, 'two')
        problem.set_objective([(1, 'a'), (2, 'b')])
        problem.pulp_lp
        problem.remove_rows(['one'])
        self.assertEqual(_reference_mps(problem), _mps(problem.pulp_lp))

    def test_a_row_that_stays_keeps_its_stored_constraint_through_a_removal(self):
        problem = self._problem()
        gone = problem.add_row([(1, 'a')], '<=', 4, 'one')
        stays = problem.add_row([(1, 'b')], '<=', 4, 'two')
        problem.set_objective([(1, 'a'), (2, 'b')])
        stored = problem.pulp_lp.constraints['two']
        problem.remove_rows(['one'])
        lp = problem.pulp_lp
        self.assertIs(stored, stays._constraint)
        self.assertIs(stored, lp.constraints['two'])
        self.assertIsNone(gone._constraint)

    def test_a_column_declared_again_with_another_bound_builds_the_problem_again(self):
        problem = self._problem()
        problem.add_row([(1, 'a')], '<=', 4, 'one')
        problem.set_objective([(1, 'a')])
        problem.pulp_lp
        problem.declare_variable('a', 0, 7)
        column = [v for v in problem.pulp_lp.variables() if v.name == 'a'][0]
        self.assertEqual(7, column.upBound)


class ALevelRowChangesTheSolutionTests(TestCase):

    def test_the_solution_follows_a_changed_right_hand_side(self):
        if not _solver_available():
            self.skipTest('no solver')
        problem = LpProblem2()
        problem.declare_variable('x_a', 0, 20)
        problem.declare_variable('x_b', 0, 20)
        level = problem.restriction_lt_eq(3, [(1, 'x', 'a')])
        problem.restriction_lt_eq(7, [(1, 'x', 'b')])
        problem.set_objective([(1, 'x_a'), (1, 'x_b')])
        problem.run()
        self.assertEqual((3, 7), (problem.value('x_a'), problem.value('x_b')))
        level.changeRHS(11)
        problem.run()
        self.assertEqual((11, 7), (problem.value('x_a'), problem.value('x_b')))
        self.assertTrue(holds(level, {'x_a': problem.value('x_a')}))


class TheTableIsTheModelTests(TestCase):
    """Fresh, pooled and rebuilt models write the bytes of the table, in every game."""

    def _request(self, kind, ids):
        base = {name: 0 for name, _key in STATS_NAMES}
        base.update({'AP': 7, 'MP': 3, 'Summon': 1, 'Prospecting': 100, 'Pods': 1000})
        minimums, values, overlaps, hinges = {}, None, None, None
        locked, forbidden = {}, []
        objective = {'vit': 1, 'str': 3, 'ap': 400, 'ch': 100}
        if kind == 'mods':
            values = {ids[0]: {12: 1000.0}, ids[1]: {12: 2000.0}}
            overlaps = {(ids[0], ids[1]): {12: -500.0}}
        elif kind == 'hinges':
            hinges = ((30, 0.5), (60, 0.2))
        elif kind == 'hp':
            minimums = {EFFECTIVE_HP_MINIMUM: 4000}
        elif kind == 'rich':
            minimums = {'Vitality': 1500, EFFECTIVE_HP_MINIMUM: 4000}
            values = {ids[0]: {12: 1000.0}, ids[1]: {12: 2000.0}}
            overlaps = {(ids[0], ids[1]): {12: -500.0}}
            hinges = ((30, 0.5), (60, 0.2))
            locked = {'a': ids[2]}
            forbidden = [ids[1]]
        elif kind != 'plain':
            raise ValueError(kind)
        return ModelInput(200, base, minimums, locked, forbidden, objective, dict(OPTIONS),
                          'Iop', 995, [], {}, values, overlaps, crit_hinges=hinges)

    def _check(self, problem):
        written = _mps(problem.pulp_lp)
        self.assertEqual(_reference_mps(problem), written)
        problem._force_rebuild = True
        self.assertEqual(written, _mps(problem.pulp_lp))
        return written

    def _versions(self, only=None):
        for version in only or ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            set_current_game_version(version)
            self.addCleanup(set_current_game_version, 'dofus3')
            structure = get_structure(version)
            ids = [item.id for item in structure.items_list[:300] if item.id][:3]
            yield version, ids

    def test_a_fresh_model_writes_its_table_in_every_version(self):
        for version, ids in self._versions():
            kinds = ('plain', 'mods', 'hinges', 'hp', 'rich') if version == 'dofus3' else ('rich',)
            for kind in kinds:
                with self.subTest(version=version, kind=kind):
                    model = Model()
                    model.setup(self._request(kind, ids))
                    self._check(model.problem)

    def test_elastic_minimums_write_their_table(self):
        for version, ids in self._versions(('dofus3', 'retro')):
            with self.subTest(version=version):
                model = Model()
                model.setup(self._request('rich', ids))
                shortfalls = model.add_elastic_minimums({'AP': 30, 'Vitality': 9000}, 200)
                model.minimise_shortfall(shortfalls)
                self._check(model.problem)
                model.hold_shortfall(shortfalls, 1.0)
                self.assertIn('elastic_hold', model.problem.row_names())
                self._check(model.problem)

    def test_a_pooled_model_writes_what_a_fresh_one_writes_and_keeps_no_leftover_row(self):
        for version, ids in self._versions():
            kinds = ('rich', 'plain', 'mods', 'rich') if version == 'dofus3' else ('rich', 'plain', 'rich')
            pooled = Model()
            for step, kind in enumerate(kinds):
                with self.subTest(version=version, step=step, kind=kind):
                    pooled.setup(self._request(kind, ids))
                    fresh = Model()
                    fresh.setup(self._request(kind, ids))
                    self.assertEqual(_mps(fresh.problem.pulp_lp), _mps(pooled.problem.pulp_lp))
                    self.assertEqual(fresh.problem.row_names(), pooled.problem.row_names())
                    if kind == 'plain':
                        names = pooled.problem.row_names()
                        self.assertFalse([n for n in names
                                          if n.startswith(('modifier_', 'crit_hinge_'))])
                        self.assertNotIn(EFFECTIVE_HP_CONSTRAINT, names)
                        self.assertFalse([n for n in pooled.problem.variable_names()
                                          if n.startswith(('modap_', 'modpick_', 'crithinge_'))])
