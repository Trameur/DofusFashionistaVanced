# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A guarded solve that is still no comparison after the retry on twice the budget is made one last time, on four
times the budget with the solver's limit of the retry; a proven solve is still required."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata import fashion_action
from chardata import tests_a_guarded_pair_counts_only_when_both_sides_are_a_comparison as guarded
from chardata import tests_a_weight_cell_ships_only_when_both_folds_agree as pooling
from chardata import weight_tuning as tuning

INSTANCE = guarded.INSTANCE
APPLIED = guarded.APPLIED
FELL_BACK = guarded.FELL_BACK
LAST_BUDGET = 4


def _unproven():
    return guarded._door(proven=False)


class AGuardedSolveStillUnfitAfterTheRetryIsMadeALastTimeTests(SimpleTestCase):

    def test_the_last_attempt_has_four_times_the_budget_and_the_limit_of_the_retry(self):
        last = guarded._door()
        runner = guarded._Runner(_unproven(), _unproven(), last)
        self.assertIs(last, tuning._guarded_solve(runner, INSTANCE, APPLIED, 90))
        self.assertEqual([90, 90 * tuning.RETRY_FACTOR, 90 * tuning.RETRY_FACTOR],
                         [call.time_limit for call in runner.calls])
        self.assertEqual([1, tuning.RETRY_FACTOR, LAST_BUDGET], [call.budget_factor for call in runner.calls])
        self.assertEqual([True, True, True], [call.guarded for call in runner.calls])
        self.assertEqual([APPLIED] * 3, [call.ratios for call in runner.calls])

    def test_a_retry_that_is_a_comparison_is_the_last_solve(self):
        runner = guarded._Runner(_unproven(), guarded._door())
        tuning._guarded_solve(runner, INSTANCE, APPLIED, 90)
        self.assertEqual(2, len(runner.calls))

    def test_a_solve_that_fell_back_on_the_retry_is_made_a_last_time_too(self):
        runner = guarded._Runner(guarded._door(guard=FELL_BACK), guarded._door(guard=FELL_BACK), guarded._door())
        self.assertTrue(tuning._guarded_solve(runner, INSTANCE, APPLIED, 90).evaluation()['valid'])
        self.assertEqual(3, len(runner.calls))

    def test_it_is_never_made_a_fourth_time(self):
        runner = guarded._Runner(_unproven(), _unproven(), _unproven())
        result = tuning._guarded_solve(runner, INSTANCE, APPLIED, 90)
        self.assertFalse(result.evaluation()['valid'])
        self.assertEqual(3, len(runner.calls))

    def test_an_infeasible_retry_is_not_made_again(self):
        infeasible = guarded._door(proven=None, credit=False)
        infeasible.infeasible = True
        runner = guarded._Runner(_unproven(), infeasible)
        self.assertIs(infeasible, tuning._guarded_solve(runner, INSTANCE, APPLIED, 90))
        self.assertEqual(2, len(runner.calls))

    def test_the_limits_follow_the_limit_asked_for(self):
        runner = guarded._Runner(_unproven(), _unproven(), guarded._door())
        tuning._guarded_solve(runner, INSTANCE, APPLIED, 40)
        self.assertEqual([40, 80, 80], [call.time_limit for call in runner.calls])


class ASideThatStaysUnfitAfterTheLastAttemptMakesTheCellNoComparisonTests(SimpleTestCase):

    def test_each_side_of_the_pair_gets_its_own_last_attempt(self):
        runner = guarded._Runner(_unproven(), _unproven(), guarded._door(), guarded._door())
        pair = tuning._guarded_pair(runner, INSTANCE, APPLIED, 90)
        self.assertEqual([None, None, None, APPLIED], [call.ratios for call in runner.calls])
        self.assertEqual([1, tuning.RETRY_FACTOR, LAST_BUDGET, 1], [call.budget_factor for call in runner.calls])
        self.assertEqual((True, True), (pair['engine']['valid'], pair['table']['valid']))

    def test_a_side_still_unproven_after_the_last_attempt_is_no_comparison(self):
        runner = guarded._Runner(guarded._door(), _unproven(), _unproven(), _unproven())
        pair = tuning._guarded_pair(runner, INSTANCE, APPLIED, 90)
        self.assertEqual((True, False), (pair['engine']['valid'], pair['table']['valid']))
        self.assertEqual(4, len(runner.calls))

    def test_the_cell_then_keeps_the_engine_for_want_of_a_proven_guarded_solve(self):
        pair = tuning._guarded_pair(guarded._Runner(guarded._door(), _unproven(), _unproven(), _unproven()),
                                    INSTANCE, APPLIED, 90)
        verdict = pooling._accept(guarded=pair)
        self.assertEqual(('engine', 'guarded_run'), (verdict['status'], verdict['reason']))


class TheLastAttemptStretchesTheGuardBudgetFourTimesTests(SimpleTestCase):

    def test_the_door_runner_gives_the_solve_four_times_the_clocks(self):
        seen = []

        def fashion(request, char_id):
            seen.append((fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS))
            return SimpleNamespace(url='/ok')
        runner = tuning.DoorRunner.__new__(tuning.DoorRunner)
        runner.request, runner.retries = object(), 0
        base = (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS)
        with mock.patch.object(fashion_action, 'fashion', fashion):
            runner._solve(SimpleNamespace(id=1), 180, LAST_BUDGET)
        self.assertEqual([(base[0] * LAST_BUDGET, base[1] * LAST_BUDGET)], seen)
        self.assertEqual(base, (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS))
