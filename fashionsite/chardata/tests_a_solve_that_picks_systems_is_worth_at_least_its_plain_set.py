import time
from unittest import mock

import pulp
from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import Catalogue, outfit
from chardata.wakfu_invented_sublimation_model import (
    ALPHA, LEVEL, SublimationModelCase, state)

# What the stub rounds price: AP and health points at one each
OBJECTIVE = {'ap': 1.0, 'hp': 1.0}
# Every way of picking sublimations or passives, with the modes the plain stage gets
PICKED = (
    (('optimistic', 'solve'), ('none', 'none')),
    (('optimistic', None), ('none', None)),
    ((None, 'solve'), (None, 'none')),
    (('optimistic', 'none'), ('none', 'none')),
    (('none', 'solve'), ('none', 'none')),
)
NOTHING_PICKED = ({}, {'sublimations': 'none', 'passives': 'none'}, {'sublimations': 'none'},
                  {'passives': 'none'})


def limited(worn):
    from fashionistapulp.wakfu_model import TIME_LIMIT
    worn.status = TIME_LIMIT
    return worn


def kinded_build(scripts, solved, clock=None, after=()):
    """A WakfuBuild stand-in that hands out the scripted sets by the model it was asked for.

    plain: no sublimation or passive picked; first_step: the pieces step of a stepwise round;
    locked: something picked and pieces locked (the floor, then the second step of a stepwise
    round); joint: something picked, nothing locked. A scripted exception is raised. After a
    solve the clock is set to the next value of after. A build keeps the start and the pruning
    it was given.
    """
    from fashionistapulp import wakfu_value
    pending = list(after)

    class KindedBuild:
        def __init__(self, structure, level, weights, forbidden=(), full_set=True,
                     minimums=None, locked=(), sublimations=None, passives=None,
                     fight_constants=None, start=None, prune_locked_positions=False,
                     **ignored):
            self.weights = dict(weights)
            self.locked = locked
            self.start = start
            self.pruned = prune_locked_positions
            self.sublimations, self.passives = sublimations, passives
            picking = wakfu_value.picks_sublimations_or_passives(sublimations, passives)
            if fight_constants is not None:
                self.kind = 'first_step'
            elif not picking:
                self.kind = 'plain'
            else:
                self.kind = 'locked' if locked else 'joint'

        def build(self):
            return self

        def solve(self, deadline=None):
            self.deadline = deadline
            solved.append(self)
            queue = scripts.get(self.kind, [])
            one = queue.pop(0) if queue else None
            if clock is not None and pending:
                clock[0] = pending.pop(0)
            if isinstance(one, Exception):
                raise one
            return one

        def totals(self, worn):
            out = wakfu_value.bare_totals({'ap': (6, 6), 'mp': (3, 3), 'wp': (6, 6)})
            for item in worn.values():
                out.update(item.stats)
            return out

        def objective_of(self, worn):
            return sum(self.weights.get(key, 0) * number
                       for key, number in self.totals(worn).items())

        def report(self, worn):
            pass

        def held_lines(self, worn):
            return {}

    return KindedBuild


class FloorCase(SimpleTestCase):
    def run_solve(self, scripts, rounds=5, deadline=None, clock=None, after=(), floor=True,
                  turn=None, nothing_picked=False, **modes):
        from fashionistapulp import wakfu_value
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        self.solved = []
        if not modes and not nothing_picked:
            modes = {'sublimations': 'optimistic'}

        def weights(role, level, totals, turn=None):
            return dict(OBJECTIVE, point_ap=totals['ap'])

        def value(role, level, totals, turn=None):
            return float(totals['ap'])

        patches = [
            mock.patch('fashionistapulp.wakfu_model.WakfuBuild',
                       kinded_build({kind: list(sets) for kind, sets in scripts.items()},
                                    self.solved, clock, after)),
            mock.patch.object(wakfu_value, 'linear_weights', weights),
            mock.patch.object(wakfu_value, 'value', value),
        ]
        if clock is not None:
            patches.append(mock.patch.object(time, 'monotonic', lambda: clock[0]))
        if not floor:
            patches.append(mock.patch.object(wakfu_value, '_floor', lambda *a: (None, None, ())))
        for patch in patches:
            patch.start()
            self.addCleanup(patch.stop)
        return wakfu_value.solve(Catalogue(), 50, role, rounds=rounds, deadline=deadline,
                                 turn=turn, **modes)

    def kinds(self):
        return [build.kind for build in self.solved]


# The plain set is AP 9 (6 and 3); the floor's locked solve AP 15; the joint sets AP 2 and 1
PLAIN = [outfit(1, ap=3), outfit(1, ap=3)]


class ASolveThatPicksSystemsIsWorthItsPlainSetTests(FloorCase):
    def test_the_systems_solve_is_worth_at_least_its_plain_set(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [outfit(2, ap=-4), outfit(3, ap=-5)]})
        self.assertGreaterEqual(result.best.value, 15)

    def test_a_round_stopped_on_its_clock_does_not_settle_by_the_gap(self):
        from fashionistapulp.wakfu_model import TIME_LIMIT
        result = self.run_solve({'plain': PLAIN,
                                 'locked': [outfit(1, ap=9), outfit(4, ap=-3)],
                                 'joint': [outfit(2, ap=10), limited(outfit(3, ap=-1))],
                                 'first_step': [outfit(4, ap=-3)]})
        self.assertIsNone(result.settled_by)
        self.assertFalse(result.converged)
        self.assertEqual(TIME_LIMIT, result.rounds[2].worn.status)
        self.assertLessEqual(result.gap, 0.1)
        self.assertEqual(4, len(result.rounds))

    def test_a_stepwise_round_settles_nothing(self):
        from fashionistapulp.wakfu_model import STEPWISE
        result = self.run_solve({'plain': PLAIN, 'joint': [limited(outfit(2, ap=-1))],
                                 'first_step': [outfit(1, ap=9)],
                                 'locked': [outfit(1, ap=9), outfit(1, ap=9)]})
        self.assertEqual(3, len(result.rounds))
        self.assertEqual(STEPWISE, result.rounds[2].worn.status)
        self.assertEqual(result.rounds[2].key, result.best.key)
        self.assertIsNone(result.settled_by)
        self.assertFalse(result.converged)

    def test_a_proven_round_still_settles_by_the_gap(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [outfit(2, ap=-1), outfit(3, ap=9)]})
        self.assertEqual('gap', result.settled_by)
        self.assertEqual(2, len(result.rounds))
        self.assertTrue(result.converged)

    def test_a_proven_round_that_comes_back_still_settles_by_key(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [outfit(1, ap=9), outfit(3, ap=9)]})
        self.assertEqual('key', result.settled_by)
        self.assertEqual(0.0, result.gap)
        self.assertEqual(result.rounds[1].worn.status, result.best.worn.status)


class TheFloorIsRoundOneTests(FloorCase):
    def test_the_floor_is_round_one_and_solved_in_steps(self):
        from fashionistapulp.wakfu_model import STEPWISE
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [outfit(2, ap=-1)]})
        floor = result.rounds[0]
        self.assertEqual(STEPWISE, floor.worn.status)
        self.assertEqual(15.0, floor.value)
        self.assertEqual(frozenset({1}), floor.ids)
        self.assertIsNotNone(floor.objective)
        self.assertIs(floor, result.best)
        self.assertEqual([(1, 'HEAD')], self.locked_of_the_floor())

    def locked_of_the_floor(self):
        return list(next(build for build in self.solved if build.kind == 'locked').locked)

    def test_the_floor_keeps_the_plain_set_when_its_locked_solve_lands_lower(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=-5)],
                                 'joint': [outfit(2, ap=-1)]})
        self.assertEqual(9.0, result.rounds[0].value)
        self.assertEqual(9.0, result.best.value)

    def test_a_locked_solve_with_no_set_or_a_crash_keeps_the_plain_set_as_floor(self):
        for locked, crashed in (([None], ()),
                                ([pulp.PulpSolverError('boom')], ((1, 'boom'),))):
            with self.subTest(locked=locked):
                result = self.run_solve({'plain': PLAIN, 'locked': locked,
                                         'joint': [outfit(2, ap=-1)]})
                self.assertEqual(9.0, result.rounds[0].value)
                self.assertEqual(frozenset({1}), result.rounds[0].ids)
                self.assertEqual(crashed, result.crashed)

    def test_the_first_systems_round_solves_at_the_plain_sets_totals(self):
        self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                        'joint': [outfit(2, ap=-1)]})
        joint = next(build for build in self.solved if build.kind == 'joint')
        # AP 6 + 3 of the plain best, not the floor's 6 + 9
        self.assertEqual(9, joint.weights['point_ap'])

    def test_the_floor_is_the_incumbent_the_gap_is_read_against(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [outfit(2, ap=-4)]})
        # AP 2 and no HP against the floor's AP 15
        self.assertAlmostEqual(-13.0, result.gap)


class ThePlainStageTests(FloorCase):
    def test_the_plain_stage_picks_nothing(self):
        for (sublimations, passives), (plain_sublimations, plain_passives) in PICKED:
            with self.subTest(sublimations=sublimations, passives=passives):
                self.run_solve({'plain': PLAIN}, sublimations=sublimations, passives=passives)
                first = self.solved[0]
                self.assertEqual('plain', first.kind)
                self.assertEqual(plain_sublimations, first.sublimations)
                self.assertEqual(plain_passives, first.passives)

    def test_the_plain_stage_gets_a_share_of_the_time_left(self):
        from fashionistapulp import wakfu_value
        self.run_solve({'plain': PLAIN}, deadline=100.0, clock=[0.0])
        self.assertEqual('plain', self.solved[0].kind)
        self.assertAlmostEqual(wakfu_value.PLAIN_SHARE * 100, self.solved[0].deadline)

    def test_under_floor_seconds_the_loop_is_the_old_one(self):
        from fashionistapulp import wakfu_value
        left = wakfu_value.FLOOR_SECONDS - 1
        result = self.run_solve({'plain': PLAIN, 'joint': [outfit(2, ap=2), outfit(3, ap=3)]},
                                deadline=float(left), clock=[0.0])
        self.assertEqual(['joint', 'joint', 'joint'], self.kinds())
        self.assertEqual([6, 8, 9], [build.weights['point_ap'] for build in self.solved])
        self.assertEqual(frozenset({2}), result.rounds[0].ids)

    def test_with_floor_seconds_left_the_floor_runs(self):
        from fashionistapulp import wakfu_value
        self.run_solve({'plain': PLAIN, 'joint': [outfit(2, ap=2)]},
                       deadline=float(wakfu_value.FLOOR_SECONDS), clock=[0.0])
        self.assertEqual('plain', self.solved[0].kind)

    def test_a_crash_on_the_plain_stage_first_round_leaves_the_old_loop(self):
        result = self.run_solve({'plain': [pulp.PulpSolverError('boom')],
                                 'joint': [outfit(2, ap=2)]})
        self.assertEqual(frozenset({2}), result.rounds[0].ids)
        self.assertEqual(['plain', 'joint'], self.kinds()[:2])
        self.assertEqual(6, self.solved[1].weights['point_ap'])

    def test_a_plain_stage_that_finds_nothing_leaves_the_old_loop(self):
        result = self.run_solve({'plain': [None], 'joint': [outfit(2, ap=2)]})
        self.assertEqual(frozenset({2}), result.rounds[0].ids)
        self.assertNotEqual('locked', self.kinds()[1])

    def test_a_crash_on_the_first_systems_round_keeps_the_floor_and_records_round_two(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [pulp.PulpSolverError('boom')]})
        self.assertEqual(1, len(result.rounds))
        self.assertEqual(15.0, result.best.value)
        self.assertEqual(((2, 'boom'),), result.crashed)


class NothingPickedNeverRunsThePlainStageTests(FloorCase):
    def test_nothing_picked_never_runs_the_plain_stage(self):
        from fashionistapulp import wakfu_value
        for modes in NOTHING_PICKED:
            with self.subTest(**modes):
                with mock.patch.object(wakfu_value, '_floor') as floor:
                    self.run_solve({'plain': [outfit(1, ap=3)]}, nothing_picked=True, **modes)
                floor.assert_not_called()

    def test_nothing_picked_the_generic_pass_still_starts_with_ten_seconds_left(self):
        for modes in NOTHING_PICKED:
            with self.subTest(**modes):
                self.assertEqual(2, len(self.passes(10.5, **modes)))

    def passes(self, left, **modes):
        from fashionistapulp import wakfu_value
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        calls = []

        def scripted(*args, **kwargs):
            calls.append(args)
            return wakfu_value.ModelSolve((), None, False)

        class Turn:
            def damage(self, totals):
                return 1.0

        with mock.patch.object(wakfu_value, '_solve', scripted), \
                mock.patch.object(wakfu_value, 'base_values', return_value={}), \
                mock.patch.object(wakfu_value, 'resource_ceiling', return_value={}), \
                mock.patch.object(time, 'monotonic', return_value=0.0):
            wakfu_value.solve(Catalogue(), 50, role, turn=Turn(), deadline=left, **modes)
        return calls

    def test_with_systems_picked_the_generic_pass_needs_floor_seconds(self):
        from fashionistapulp import wakfu_value
        floor = wakfu_value.FLOOR_SECONDS
        self.assertEqual(1, len(self.passes(floor - 0.5, sublimations='optimistic')))
        self.assertEqual(1, len(self.passes(floor - 0.5, passives='solve')))
        self.assertEqual(2, len(self.passes(floor, sublimations='optimistic')))


class AStepwiseRoundNeedsTwoRoundMinimumsTests(FloorCase):
    def test_a_stepwise_round_needs_two_round_minimums(self):
        from fashionistapulp import wakfu_value
        need = 2 * wakfu_value.MIN_ROUND_SECONDS
        for left, expected in ((need - 1, ['joint']),
                               (need + 1, ['joint', 'first_step', 'locked'])):
            with self.subTest(left=left):
                self.run_solve({'joint': [limited(outfit(1, ap=2))],
                                'first_step': [outfit(2, ap=1)],
                                'locked': [outfit(2, ap=1)]},
                               deadline=100.0, clock=[0.0], after=[100.0 - left], floor=False)
                self.assertEqual(expected, self.kinds()[:len(expected)])
                if left < need:
                    self.assertEqual(1, len(self.solved))


class ARealSolveWithSublimationsIsWorthItsPlainSetTests(SublimationModelCase):
    def solve(self, **modes):
        from fashionistapulp import wakfu_value
        self.invent({3: state(lines=[('A', 'ferocity', 40, 0, ())])},
                    {120: (3, 1, 'normal', ())})
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        return wakfu_value.solve(self.structure, LEVEL, role, class_id=ALPHA, rounds=3, **modes)

    def test_a_real_solve_with_sublimations_is_worth_at_least_the_same_solve_with_none(self):
        from fashionistapulp.wakfu_model import STEPWISE
        plain = self.solve(sublimations='none', passives='none')
        systems = self.solve(sublimations='optimistic', passives='none')
        self.assertEqual(STEPWISE, systems.rounds[0].worn.status)
        self.assertGreaterEqual(systems.best.value, plain.best.value - 1e-9)
        self.assertEqual([], self.rules_broken(systems.best.worn))


class AFloorLeavesTimeForARoundTests(FloorCase):
    def test_after_the_floor_a_whole_joint_round_needs_two_round_minimums(self):
        from fashionistapulp import wakfu_value
        left = 2 * wakfu_value.MIN_ROUND_SECONDS - 5
        # Two plain rounds, then the floor's locked solve, after which the clock is at left
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': [outfit(2, ap=-1)]},
                                deadline=100.0, clock=[0.0], after=[0.0, 0.0, 100.0 - left])
        self.assertNotIn('joint', self.kinds())
        self.assertEqual(1, len(result.rounds))


class TheTwoMinimumStopTests(FloorCase):
    def test_a_picking_solve_with_nothing_done_runs_its_first_round_on_less_than_two_minimums(self):
        from fashionistapulp import wakfu_value
        left = 2 * wakfu_value.MIN_ROUND_SECONDS - 5
        self.assertLess(left, wakfu_value.FLOOR_SECONDS)
        result = self.run_solve({'joint': [outfit(2, ap=2)]}, deadline=float(left),
                                clock=[0.0])
        self.assertEqual(['joint'], self.kinds())
        self.assertEqual(frozenset({2}), result.rounds[0].ids)

    def test_a_solve_that_picks_nothing_keeps_looping_on_less_than_two_minimums(self):
        from fashionistapulp import wakfu_value
        left = 2 * wakfu_value.MIN_ROUND_SECONDS - 5
        self.assertGreaterEqual(left, wakfu_value.MIN_ROUND_SECONDS)
        self.run_solve({'plain': [outfit(1, ap=3), outfit(2, ap=5), outfit(3, ap=7)]},
                       deadline=100.0, clock=[0.0], after=[100.0 - left],
                       nothing_picked=True)
        self.assertGreater(self.kinds().count('plain'), 1)
