# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Every way a CBC search ends reads as one status string and one answer to "proven"."""
import os
import random
import tempfile
from unittest import mock

from django.test import SimpleTestCase
from pulp import COIN_CMD

from fashionistapulp import lpproblem
from fashionistapulp.lpproblem import LpProblem2, read_outcome


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


def knapsack(rows):
    draw = random.Random(3)
    problem = LpProblem2()
    for index in range(300):
        problem.setup_variable('x', index, 0, 3)
    problem.init_objective_function()
    for index in range(300):
        problem.add_to_of('x', index, draw.randint(10, 60))
    problem.finish_objective_function()
    for _row in range(rows):
        problem.restriction_lt_eq(draw.randint(200, 400),
                                  [(draw.randint(5, 40), 'x', index) for index in range(300)])
    return problem


def tiny(bound):
    problem = LpProblem2()
    problem.setup_variable('item', 'x', 0, 10)
    problem.init_objective_function()
    problem.add_to_of('item', 'x', 3)
    problem.finish_objective_function()
    problem.restriction_lt_eq(bound, [(1, 'item', 'x')])
    return problem


def solution_file(folder, first_line):
    path = os.path.join(folder, 'cbc.sol')
    with open(path, 'w') as solution:
        solution.write(first_line + '\n')
    return path


def outcome_of_solution_file(first_line):
    """The outcome PuLP and the adapter give a CBC solution file that opens with first_line."""
    with tempfile.TemporaryDirectory() as folder:
        return read_outcome(*COIN_CMD().get_status(solution_file(folder, first_line)))


class TheFiveEndingsReadFromCbcsFirstLineTests(SimpleTestCase):

    def test_a_search_that_ended_by_itself_is_optimal_and_finished(self):
        outcome = outcome_of_solution_file('Optimal - objective value 875.00000000')
        self.assertEqual(('Optimal', True), tuple(outcome))

    def test_a_stop_on_time_with_a_set_is_optimal_and_not_finished(self):
        outcome = outcome_of_solution_file('Stopped on time - objective value 174.00000000')
        self.assertEqual(('Optimal', False), tuple(outcome))

    def test_a_stop_on_time_without_a_set_is_not_solved_and_not_finished(self):
        outcome = outcome_of_solution_file(
            'Stopped on time (no integer solution - continuous used) - objective value 589.01')
        self.assertEqual(('Not Solved', False), tuple(outcome))

    def test_an_infeasible_model_is_infeasible(self):
        outcome = outcome_of_solution_file('Infeasible - objective value 0.00000000')
        self.assertEqual(('Infeasible', False), tuple(outcome))

    def test_an_integer_infeasible_model_is_infeasible(self):
        outcome = outcome_of_solution_file('Integer infeasible - objective value 589.01')
        self.assertEqual(('Infeasible', False), tuple(outcome))

    def test_an_unbounded_model_is_unbounded(self):
        outcome = outcome_of_solution_file('Unbounded - objective value 0.00000000')
        self.assertEqual(('Unbounded', False), tuple(outcome))

    def test_a_status_nobody_knows_is_undefined(self):
        self.assertEqual(('Undefined', False), tuple(read_outcome(12345, 0)))


class AProblemAnswersFromItsOutcomeTests(SimpleTestCase):

    def setUp(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')

    def test_an_optimal_run_is_optimal_finished_and_proven(self):
        problem = tiny(4)
        problem.run()
        self.assertEqual('Optimal', problem.get_status())
        self.assertTrue(problem.search_finished())
        self.assertTrue(problem.solution_is_proven())
        self.assertEqual(12, problem.objective_value)

    def test_a_gap_stop_is_optimal_finished_and_never_proven(self):
        problem = knapsack(3)
        problem.run(gap=0.03)
        self.assertEqual('Optimal', problem.get_status())
        self.assertTrue(problem.search_finished())
        self.assertFalse(problem.solution_is_proven())

    def test_a_time_stop_with_a_set_is_optimal_unfinished_and_not_proven(self):
        problem = knapsack(80)
        with mock.patch.object(lpproblem.SOLVER, 'timeLimit', 1):
            problem.run()
        self.assertEqual('Optimal', problem.get_status())
        self.assertFalse(problem.search_finished())
        self.assertFalse(problem.solution_is_proven())
        self.assertIsNotNone(problem.objective_value)

    def test_an_infeasible_run_is_infeasible_and_not_proven(self):
        problem = tiny(-1)
        problem.run()
        self.assertEqual('Infeasible', problem.get_status())
        self.assertFalse(problem.search_finished())
        self.assertFalse(problem.solution_is_proven())
        self.assertIsNone(problem.objective_value)

    def test_a_time_stop_without_a_set_is_not_solved_and_not_proven(self):
        problem = tiny(4)
        problem.run()
        with tempfile.TemporaryDirectory() as folder:
            path = solution_file(folder, 'Stopped on time (no integer solution - continuous '
                                         'used) - objective value 5')
            problem.pulp_lp.assignStatus(*COIN_CMD().get_status(path))
        self.assertEqual('Not Solved', problem.get_status())
        self.assertFalse(problem.search_finished())
        self.assertFalse(problem.solution_is_proven())

    def test_a_run_after_a_gap_run_without_a_gap_is_proven_again(self):
        problem = knapsack(3)
        problem.run(gap=0.03)
        self.assertFalse(problem.solution_is_proven())
        problem.run()
        self.assertTrue(problem.solution_is_proven())
