# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A guarded solve is a comparison only when it was proven and neither fell back nor ran out of time."""
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata import fashion_action
from chardata import weight_tuning as tuning

INSTANCE = tuning.Instance('Iop', ('str',), 'glasscannon', '200', 'high', 'dev_a')
APPLIED = {'pow': 1.5}


def _door(guarded=True, proven=True, guard=None, credit=True):
    return tuning.DoorResult(INSTANCE, None, proven=proven, guarded=guarded, guard=guard, panel_turn=900.0,
                             credit=SimpleNamespace(turn=1000.0, ehp=5000.0) if credit else None)


class AGuardedSolveIsValidOnlyWhenItWasAComparisonTests(SimpleTestCase):

    def valid(self, **kwargs):
        return _door(**kwargs).evaluation()['valid']

    def test_a_proven_guarded_solve_without_a_flag_is_valid(self):
        self.assertTrue(self.valid(guard={'floors': {}}))
        self.assertTrue(self.valid(guard=None))

    def test_an_unproven_guarded_solve_is_not(self):
        self.assertFalse(self.valid(proven=False, guard={'floors': {}}))
        self.assertFalse(self.valid(proven=None))

    def test_a_guarded_solve_that_fell_back_is_not(self):
        self.assertFalse(self.valid(guard={'fallback': True}))

    def test_a_guarded_solve_that_ran_out_of_time_is_not(self):
        self.assertFalse(self.valid(guard={'out_of_time': True}))

    def test_the_other_facts_do_not_decide(self):
        self.assertTrue(self.valid(guard={'short': ['ap'], 'balanced_out_of_time': True}))

    def test_a_solve_without_a_credited_turn_is_not(self):
        self.assertFalse(self.valid(credit=False))

    def test_an_unguarded_solve_is_valid_only_when_proven(self):
        self.assertTrue(self.valid(guarded=False))
        self.assertFalse(self.valid(guarded=False, proven=False))
        self.assertFalse(self.valid(guarded=False, proven=None))


class _Runner(object):
    """Hands out the scripted door results in order and notes how each was asked for."""

    def __init__(self, *results):
        self.script = list(results)
        self.calls = []

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False, budget_factor=1):
        self.calls.append(SimpleNamespace(ratios=ratios, time_limit=time_limit, guarded=guarded,
                                          budget_factor=budget_factor))
        return self.script.pop(0)


FELL_BACK = {'fallback': True, 'out_of_time': True}


class AnUnfitGuardedSolveIsMadeAgainOnAFreshDoubleBudgetTests(SimpleTestCase):

    def test_a_solve_that_is_a_comparison_is_made_once(self):
        runner = _Runner(_door())
        tuning._guarded_solve(runner, INSTANCE, APPLIED, 90)
        self.assertEqual(1, len(runner.calls))
        self.assertEqual((90, 1, True), (runner.calls[0].time_limit, runner.calls[0].budget_factor,
                                         runner.calls[0].guarded))

    def test_a_solve_that_fell_back_is_made_again_with_twice_the_limit_and_twice_the_budget(self):
        again = _door()
        runner = _Runner(_door(guard=FELL_BACK), again)
        self.assertIs(again, tuning._guarded_solve(runner, INSTANCE, APPLIED, 90))
        self.assertEqual([90, 90 * tuning.RETRY_FACTOR], [call.time_limit for call in runner.calls])
        self.assertEqual([1, tuning.RETRY_FACTOR], [call.budget_factor for call in runner.calls])
        self.assertEqual([True, True], [call.guarded for call in runner.calls])
        self.assertEqual([APPLIED, APPLIED], [call.ratios for call in runner.calls])

    def test_an_unproven_solve_is_made_again(self):
        runner = _Runner(_door(proven=False), _door())
        self.assertTrue(tuning._guarded_solve(runner, INSTANCE, APPLIED, 90).evaluation()['valid'])
        self.assertEqual(2, len(runner.calls))

    def test_it_is_made_again_twice_only(self):
        runner = _Runner(_door(guard=FELL_BACK), _door(guard=FELL_BACK), _door(guard=FELL_BACK))
        result = tuning._guarded_solve(runner, INSTANCE, APPLIED, 90)
        self.assertFalse(result.evaluation()['valid'])
        self.assertEqual(3, len(runner.calls))

    def test_an_infeasible_solve_is_not_made_again(self):
        infeasible = _door(proven=None, credit=False)
        infeasible.infeasible = True
        runner = _Runner(infeasible)
        tuning._guarded_solve(runner, INSTANCE, APPLIED, 90)
        self.assertEqual(1, len(runner.calls))

    def test_each_side_of_the_pair_is_made_again_on_its_own(self):
        runner = _Runner(_door(guard=FELL_BACK), _door(), _door())
        pair = tuning._guarded_pair(runner, INSTANCE, APPLIED, 90)
        self.assertEqual([None, None, APPLIED], [call.ratios for call in runner.calls])
        self.assertEqual([1, tuning.RETRY_FACTOR, 1], [call.budget_factor for call in runner.calls])
        self.assertEqual((True, True), (pair['engine']['valid'], pair['table']['valid']))

    def test_a_side_that_stays_unfit_makes_the_pair_no_comparison(self):
        runner = _Runner(_door(), _door(guard=FELL_BACK), _door(guard=FELL_BACK), _door(guard=FELL_BACK))
        pair = tuning._guarded_pair(runner, INSTANCE, APPLIED, 90)
        self.assertEqual((True, False), (pair['engine']['valid'], pair['table']['valid']))


class TheBudgetOfAGuardedRequestIsStretchedTests(SimpleTestCase):

    def test_both_clocks_are_multiplied_inside_the_block_and_restored_after(self):
        before = (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS)
        with tuning.guard_budget(2):
            inside = (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS)
        self.assertEqual((before[0] * 2, before[1] * 2), inside)
        self.assertEqual(before, (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS))

    def test_they_are_restored_when_the_block_fails(self):
        before = (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS)
        with self.assertRaises(RuntimeError):
            with tuning.guard_budget(2):
                raise RuntimeError('solver died')
        self.assertEqual(before, (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS))

    def test_the_door_runner_stretches_them_while_the_door_runs(self):
        seen = []

        def fashion(request, char_id):
            seen.append((fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS))
            return SimpleNamespace(url='/ok')
        runner = tuning.DoorRunner.__new__(tuning.DoorRunner)
        runner.request, runner.retries = object(), 0
        base = (fashion_action.GUARD_BUDGET_SECONDS, fashion_action.BALANCED_SECONDS)
        with mock.patch.object(fashion_action, 'fashion', fashion):
            runner._solve(SimpleNamespace(id=1), 90)
            runner._solve(SimpleNamespace(id=1), 90, 2)
        self.assertEqual([base, (base[0] * 2, base[1] * 2)], seen)

    def test_the_door_runner_passes_the_factor_to_the_solve(self):
        runner = tuning.DoorRunner.__new__(tuning.DoorRunner)
        runner.game_version = 'dofus3'
        with mock.patch.object(tuning.DoorRunner, '_build', return_value=object()), \
                mock.patch.object(tuning.DoorRunner, '_solve', return_value=(1.0, True, 0)) as solve, \
                mock.patch.object(tuning.DoorRunner, '_read'):
            runner.run(INSTANCE, None, (), 90, guarded=True, budget_factor=2)
        self.assertEqual(2, solve.call_args[0][2])
