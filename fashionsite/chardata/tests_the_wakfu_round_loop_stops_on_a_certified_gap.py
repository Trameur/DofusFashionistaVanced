import collections
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import Catalogue, outfit
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, state)

# What the stub rounds price: AP and health points at one each
OBJECTIVE = {'ap': 1.0, 'hp': 1.0}


def stub_build(script, solved):
    """A WakfuBuild stand-in that hands out the scripted sets and prices a set linearly."""
    from fashionistapulp import wakfu_value

    class StubBuild:
        def __init__(self, structure, level, weights, forbidden=(), full_set=True,
                     minimums=None, **ignored):
            self.weights = dict(weights)

        def build(self):
            return self

        def solve(self, deadline=None):
            solved.append(self)
            return script.pop(0) if script else None

        def totals(self, worn):
            out = wakfu_value.bare_totals({'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)})
            for item in worn.values():
                out.update(item.stats)
            return out

        def objective_of(self, worn):
            return sum(self.weights.get(key, 0) * number
                       for key, number in self.totals(worn).items())

    return StubBuild


class TheRoundLoopStubTests(SimpleTestCase):
    """The loop on scripted sets, the value of a set being its AP and the objective AP + HP."""

    def run_loop(self, *sets, rounds=5):
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
            return wakfu_value.solve(Catalogue(), 50, role, rounds=rounds)

    def test_a_worse_round_with_no_objective_to_gain_settles_by_the_gap_at_round_two(self):
        result = self.run_loop(outfit(1, ap=2), outfit(2, ap=-1), outfit(3, ap=5))
        self.assertEqual(2, len(result.rounds))
        self.assertEqual('gap', result.settled_by)
        self.assertTrue(result.converged)
        self.assertLessEqual(result.gap, 0.1)
        self.assertEqual(1, min(result.best.ids))

    def test_a_round_is_priced_on_its_own_objective_beside_the_incumbent(self):
        result = self.run_loop(outfit(1, ap=2), outfit(2, ap=-1, hp=5), outfit(3, ap=-2))
        first, second = result.rounds[:2]
        # AP 6 + 2 against AP 6 - 1 and 5 HP, each read on the objective of round two
        self.assertAlmostEqual(8.0, first.objective)
        self.assertAlmostEqual(10.0, second.objective)

    def test_a_gap_above_the_tolerance_does_not_settle_the_loop(self):
        result = self.run_loop(outfit(1, ap=2), outfit(2, ap=-1, hp=5), outfit(3, ap=-2))
        self.assertIsNone(result.settled_by)
        self.assertFalse(result.converged)
        self.assertEqual(3, len(result.rounds))
        self.assertAlmostEqual(2.0, result.gap)

    def test_the_round_after_a_gap_solves_at_the_midpoint_of_the_two_sets(self):
        self.run_loop(outfit(1, ap=2), outfit(2, ap=-1, hp=5), outfit(3, ap=-2))
        # AP 6 bare; the incumbent's 8; then 8 + (5 - 8) / 2
        self.assertEqual([6, 8, 6.5], [build.weights['point_ap'] for build in self.solved])

    def test_a_damped_round_that_improves_goes_on_from_its_own_totals(self):
        result = self.run_loop(outfit(1, ap=2), outfit(2, ap=-1, hp=5), outfit(3, ap=4),
                               outfit(4, ap=-1), outfit(5, ap=9))
        self.assertEqual(4, len(result.rounds))
        self.assertEqual('gap', result.settled_by)
        self.assertEqual(3, min(result.best.ids))
        self.assertEqual([6, 8, 6.5, 10], [build.weights['point_ap'] for build in self.solved])

    def test_a_set_that_comes_back_settles_by_key_with_no_gap(self):
        result = self.run_loop(outfit(1, ap=2), outfit(2, ap=4), outfit(2, ap=4),
                               outfit(3, ap=9))
        self.assertEqual('key', result.settled_by)
        self.assertEqual(0.0, result.gap)
        self.assertEqual(3, len(result.rounds))

    def test_a_loop_that_improves_every_round_never_settles_early(self):
        result = self.run_loop(*[outfit(number, ap=number) for number in range(1, 9)])
        self.assertEqual(5, len(result.rounds))
        self.assertIsNone(result.settled_by)
        self.assertFalse(result.converged)
        self.assertIsNone(result.gap)
        self.assertEqual(5, min(result.best.ids))

    def test_the_replaced_solve_keeps_the_tuple_the_callers_unpack(self):
        result = self.run_loop(outfit(1, ap=2), outfit(2, ap=-1))
        rounds, best, converged = result
        self.assertEqual((2, True), (len(rounds), converged))
        self.assertIs(best, result.best)
        unsettled = result._replace(converged=False)
        self.assertIsNone(unsettled.settled_by)
        self.assertEqual(result.gap, unsettled.gap)


class TheObjectiveOfASetIsTheSolversTests(SublimationModelCase):
    """objective_of on the set a real solve gave equals the objective CBC maximized."""

    def test_the_objective_read_back_equals_the_solver_objective(self):
        self.invent()
        build, worn = self.sublimate({'hp': 1, 'ferocity': 2, 'ap': 5}, runes='optimistic',
                                     ap_values={ap: ap - 4 for ap in range(4, 13)})
        self.assertGreater(len(worn), 5)
        self.assert_objective_is_read_back(build, worn)

    def test_a_set_scores_lower_on_the_objective_of_another_set_it_does_not_match(self):
        self.invent()
        build, worn = self.sublimate({'hp': 1})
        poorer = type(worn)({position: item for position, item in worn.items()
                             if position != 'HEAD'})
        self.assertLess(build.objective_of(poorer), build.objective_of(worn))


class TheResultNamesHowTheLoopStoppedTests(SublimationModelCase):
    def test_a_result_is_settled_exactly_when_it_names_a_reason(self):
        from fashionistapulp import wakfu_solve
        from fashionistapulp.wakfu_model import PROVEN, STEPWISE, TIME_LIMIT
        self.invent()
        result = wakfu_solve.solve_build(
            self.structure, level=LEVEL, elements='fire', reach='distance', class_id=ALPHA,
            on_class_turn=False, aptitudes=None, runes='none', seconds=60,
            sublimations='none', passives='none')
        self.assertIsNotNone(result.worn)
        self.assertEqual(result.settled_by is not None, result.settled)
        self.assertIn(result.settled_by, ('key', 'gap', None))
        self.assertIn(result.status, (PROVEN, TIME_LIMIT, STEPWISE))


class AJointRoundThatRunsOutOfTimeSwitchesToStepsTests(SublimationModelCase):
    def solve_on_the_clock(self):
        from fashionistapulp import wakfu_value
        self.invent({3: state(lines=[('A', 'ferocity', 40, 0, ())])},
                    {120: (3, 1, 'normal', ())})
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        with mock.patch('fashionistapulp.lpproblem.LpProblem2.solution_is_proven',
                        return_value=False):
            return wakfu_value.solve(self.structure, LEVEL, role, class_id=ALPHA, rounds=3,
                                     sublimations='optimistic', passives='none')

    def test_the_rounds_after_a_clock_stop_are_solved_in_steps(self):
        from fashionistapulp.wakfu_model import STEPWISE, TIME_LIMIT
        result = self.solve_on_the_clock()
        statuses = [one.worn.status for one in result.rounds]
        self.assertEqual(TIME_LIMIT, statuses[0])
        self.assertGreater(len(statuses), 1)
        self.assertEqual({STEPWISE}, set(statuses[1:]))

    def test_a_stepwise_round_still_places_and_prices_a_sublimation(self):
        result = self.solve_on_the_clock()
        later = result.rounds[1]
        self.assertTrue(later.worn.sublimations)
        self.assertIsNotNone(later.objective)
        self.assertEqual([], self.rules_broken(later.worn))
