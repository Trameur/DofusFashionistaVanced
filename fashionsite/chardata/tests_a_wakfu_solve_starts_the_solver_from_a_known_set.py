from unittest import mock

from django.test import SimpleTestCase

from chardata.tests_a_solve_that_picks_systems_is_worth_at_least_its_plain_set import (
    PLAIN, FloorCase, limited)
from chardata.tests_wakfu_build_solves_on_the_damage_model import (
    CAPE, HELMET, Catalogue, outfit, piece)


def valued(worn, **values):
    worn.solution_values = dict(values)
    return worn


def build_of(**kwargs):
    from fashionistapulp.wakfu_model import WakfuBuild
    pieces = (piece(1, HELMET, hp=10), piece(2, HELMET, hp=100), piece(3, CAPE, hp=20))
    return WakfuBuild(Catalogue(*pieces), 50, {'hp': 1}, **kwargs)


class ASolvedSetCarriesItsValuesTests(SimpleTestCase):
    def test_a_solved_set_carries_the_values_the_solver_gave(self):
        build = build_of()
        worn = build.build().solve()
        self.assertTrue(worn.solution_values)
        self.assertEqual(build.problem.get_search_state()['values'], worn.solution_values)

    def test_a_set_that_was_not_solved_carries_none(self):
        from fashionistapulp.wakfu_model import WakfuSet
        self.assertIsNone(WakfuSet().solution_values)


class ABuildGivenAStartHandsItToTheSolverTests(SimpleTestCase):
    def warm_start_of(self, **kwargs):
        from fashionistapulp.lpproblem import LpProblem2
        run = LpProblem2.run
        with mock.patch.object(LpProblem2, 'run', autospec=True, side_effect=run) as ran:
            build_of(**kwargs).build().solve()
        self.assertEqual(1, ran.call_count)
        return ran.call_args.kwargs.get('warm_start')

    def first_values(self):
        build = build_of()
        build.build().solve()
        return dict(build.problem.get_search_state()['values'])

    def test_a_build_given_a_start_hands_it_to_the_solver(self):
        start = self.first_values()
        self.assertEqual(start, self.warm_start_of(start=start))

    def test_a_build_given_no_start_runs_cold(self):
        self.assertIsNone(self.warm_start_of())


class AnotherRoundStartsFromTheBestSetSoFarTests(FloorCase):
    def starts(self, kind):
        return [build.start for build in self.solved if build.kind == kind]

    def test_a_plain_round_starts_from_the_best_plain_round_so_far(self):
        first, second = {'a': 1}, {'b': 1}
        self.run_solve({'plain': [valued(outfit(1, ap=3), **first),
                                  valued(outfit(2, ap=5), **second),
                                  valued(outfit(3, ap=1), c=1),
                                  valued(outfit(4, ap=4), d=1)]},
                       nothing_picked=True)
        # The fourth round follows a worse one, so only the best round can be its start
        self.assertEqual([None, first, second, second], self.starts('plain')[:4])

    def test_each_floor_seed_starts_from_its_plain_set(self):
        first, second = {'a': 1}, {'b': 1}
        self.run_solve({'plain': [valued(outfit(1, ap=3), **first),
                                  valued(outfit(2, ap=2), **second)],
                        'locked': [outfit(1, ap=5), outfit(2, ap=9)]})
        self.assertEqual([first, second], self.starts('locked')[:2])

    def test_a_whole_joint_round_starts_cold(self):
        self.run_solve({'plain': PLAIN, 'locked': [valued(outfit(1, ap=9), f=1)],
                        'joint': [outfit(2, ap=-1)]})
        self.assertEqual([None], self.starts('joint'))

    def test_the_second_step_starts_from_the_first_steps_values_on_a_pruned_model(self):
        floor, pieces = {'f': 1}, {'p': 1}
        self.run_solve({'plain': PLAIN, 'joint': [limited(outfit(2, ap=-1))],
                        'first_step': [valued(outfit(1, ap=9), **pieces)],
                        'locked': [valued(outfit(1, ap=9), **floor), outfit(1, ap=9)]})
        locked = [build for build in self.solved if build.kind == 'locked']
        self.assertEqual(pieces, locked[-1].start)
        self.assertTrue(locked[-1].pruned)
        self.assertEqual(2, len(locked))

    def test_the_first_step_starts_from_the_incumbent(self):
        floor = {'f': 1}
        self.run_solve({'plain': PLAIN, 'joint': [limited(outfit(2, ap=-1))],
                        'first_step': [outfit(1, ap=9)],
                        'locked': [valued(outfit(1, ap=9), **floor), outfit(1, ap=9)]})
        self.assertEqual([floor], self.starts('first_step'))
