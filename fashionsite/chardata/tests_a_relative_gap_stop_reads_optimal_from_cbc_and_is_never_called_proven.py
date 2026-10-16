# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""CBC and PuLP report a stop within a relative gap as Optimal: the problem tells it apart from a proof."""
import random

from django.test import SimpleTestCase
from pulp import LpSolutionOptimal, LpStatusOptimal, value

from fashionistapulp.lpproblem import LpProblem2, read_best_bound

GAP_EXIT_LOG = """ratioGap was changed from 0 to 0.03
Cbc0010I After 0 nodes, 1 on tree, -753 best solution, best possible -890.87518 (0.03 seconds)
Cbc0011I Exiting as integer gap of 15.875181 less than 1e-10 or 3%
Cbc0001I Search completed - best objective -875, took 64 iterations and 3 nodes (0.03 seconds)

Result - Optimal solution found (within gap tolerance)

Objective value:                875.00000000
"""


def _solver_available():
    try:
        import pulp
        return bool(pulp.listSolvers(onlyAvailable=True))
    except Exception:
        return False


def knapsack():
    """Three rows: CBC stops within 3% at once, below the optimum it proves without a gap."""
    draw = random.Random(3)
    problem = LpProblem2()
    for index in range(300):
        problem.setup_variable('x', index, 0, 3)
    problem.init_objective_function()
    for index in range(300):
        problem.add_to_of('x', index, draw.randint(10, 60))
    problem.finish_objective_function()
    for _row in range(3):
        problem.restriction_lt_eq(draw.randint(200, 400),
                                  [(draw.randint(5, 40), 'x', index) for index in range(300)])
    return problem


class TheGapExitLineGivesTheBoundTests(SimpleTestCase):

    def test_the_bound_is_the_objective_plus_the_printed_gap(self):
        self.assertAlmostEqual(875.0 + 15.875181, read_best_bound(GAP_EXIT_LOG, 875.0))


class ARunGivenAGapTests(SimpleTestCase):

    def setUp(self):
        if not _solver_available():
            self.skipTest('no pulp solver available')

    def test_cbc_reports_the_gap_stop_as_optimal_and_the_problem_does_not_call_it_proven(self):
        exact = knapsack()
        exact.run()
        best = value(exact.pulp_lp.objective)
        quick = knapsack()
        quick.run(gap=0.03)
        state = quick.get_search_state()
        self.assertEqual(LpStatusOptimal, quick.pulp_lp.status)
        self.assertEqual(LpSolutionOptimal, quick.pulp_lp.sol_status)
        self.assertEqual('Optimal', quick.get_status())
        self.assertTrue(quick.search_finished())
        self.assertFalse(quick.solution_is_proven())
        self.assertTrue(exact.solution_is_proven())
        self.assertLess(state['objective'], best)
        self.assertGreaterEqual(state['objective'], (1 - 0.03) * best)
        self.assertGreaterEqual(state['bound'], best)

    def test_a_run_without_a_gap_after_a_gap_run_is_proven_again(self):
        problem = knapsack()
        problem.run(gap=0.03)
        self.assertFalse(problem.solution_is_proven())
        problem.run()
        self.assertTrue(problem.solution_is_proven())
