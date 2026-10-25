import time
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests_the_wakfu_round_loop_stops_on_a_certified_gap import (
    OBJECTIVE, stub_build)
from chardata.tests_wakfu_build_solves_on_the_damage_model import Catalogue, outfit
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, state)

# Every way of asking for no sublimation and no passive
NOTHING_PICKED = ({}, {'sublimations': 'none', 'passives': 'none'}, {'sublimations': 'none'},
                  {'passives': 'none'})


class ASolveThatPicksNothingKeepsThePlainRoundLoopTests(SimpleTestCase):
    """Scripted sets, the value of a set being its AP and the objective AP + HP."""

    def run_loop(self, *sets, rounds=5, deadline=None, **modes):
        from fashionistapulp import wakfu_value
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        self.solved = []

        def weights(role, level, totals, turn=None):
            return dict(OBJECTIVE, point_ap=totals['ap'])

        def value(role, level, totals, turn=None):
            return float(totals['ap'])

        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild',
                        stub_build(list(sets), self.solved)), \
                mock.patch.object(wakfu_value, 'linear_weights', weights), \
                mock.patch.object(wakfu_value, 'value', value):
            return wakfu_value.solve(Catalogue(), 50, role, rounds=rounds, deadline=deadline,
                                     **modes)

    def test_each_round_moves_toward_the_new_set_by_two_over_k_plus_two(self):
        for modes in NOTHING_PICKED:
            with self.subTest(**modes):
                self.run_loop(outfit(1, ap=6), outfit(2, ap=3), outfit(3, ap=8),
                              outfit(3, ap=8), **modes)
                # AP 6 bare, then 12; 12 + 2/3 x (9 - 12) = 10; 10 + 2/4 x (14 - 10) = 12
                self.assertEqual([6, 12, 10, 12],
                                 [build.weights['point_ap'] for build in self.solved])

    def test_a_round_worse_than_the_best_does_not_stop_the_rounds(self):
        for modes in NOTHING_PICKED:
            with self.subTest(**modes):
                result = self.run_loop(outfit(1, ap=6), outfit(2, ap=3), outfit(3, ap=8),
                                       outfit(4, ap=2), outfit(5, ap=1), **modes)
                self.assertEqual(5, len(result.rounds))
                self.assertFalse(result.converged)
                self.assertIsNone(result.settled_by)
                self.assertIsNone(result.gap)
                self.assertEqual(3, min(result.best.ids))

    def test_the_rounds_settle_when_a_set_comes_back_twice_in_a_row(self):
        for modes in NOTHING_PICKED:
            with self.subTest(**modes):
                result = self.run_loop(outfit(1, ap=6), outfit(2, ap=3), outfit(2, ap=3),
                                       outfit(3, ap=9), **modes)
                self.assertEqual(3, len(result.rounds))
                self.assertEqual('key', result.settled_by)
                self.assertTrue(result.converged)
                self.assertEqual(1, min(result.best.ids))

    def test_every_round_gets_the_whole_deadline(self):
        for modes in NOTHING_PICKED:
            with self.subTest(**modes):
                deadline = time.monotonic() + 1000
                self.run_loop(outfit(1, ap=6), outfit(2, ap=3), deadline=deadline, **modes)
                self.assertEqual([deadline] * 3, [build.deadline for build in self.solved])

    def test_a_round_that_picks_sublimations_gets_a_share_of_the_deadline(self):
        deadline = time.monotonic() + 1000
        self.run_loop(outfit(1, ap=6), deadline=deadline, sublimations='optimistic')
        self.assertLess(self.solved[0].deadline, deadline - 100)

    def test_a_round_that_picks_passives_gets_a_share_of_the_deadline(self):
        deadline = time.monotonic() + 1000
        self.run_loop(outfit(1, ap=6), deadline=deadline, sublimations='none',
                      passives='solve')
        self.assertLess(self.solved[0].deadline, deadline - 100)


class ASolveThatPicksNothingKeepsTheWholeBudgetTests(SublimationModelCase):
    def deadline_given(self, **modes):
        from fashionistapulp import wakfu_solve, wakfu_value
        self.invent({3: state(lines=[('A', 'ferocity', 40, 0, ())])},
                    {120: (3, 1, 'normal', ())})
        given = []

        def solve(*args, **kwargs):
            given.append(kwargs['deadline'])
            return wakfu_value.ModelSolve((), None, False)

        started = time.monotonic()
        with mock.patch.object(wakfu_value, 'solve', solve):
            wakfu_solve.solve_build(
                self.structure, level=LEVEL, elements='fire', reach='distance',
                class_id=ALPHA, on_class_turn=False, aptitudes=None, runes='none',
                seconds=60, **modes)
        return given[0] - started

    def test_with_nothing_to_pick_the_model_gets_every_second_of_the_budget(self):
        for modes in ({'sublimations': None, 'passives': None},
                      {'sublimations': 'none', 'passives': 'none'}):
            with self.subTest(**modes):
                self.assertGreaterEqual(self.deadline_given(**modes), 60)

    def test_picking_sublimations_keeps_seconds_back_for_the_landing(self):
        from fashionistapulp import wakfu_value
        left = self.deadline_given(sublimations='optimistic', passives='none')
        self.assertLessEqual(left, 60 - wakfu_value.FINISH_SECONDS + 1)
