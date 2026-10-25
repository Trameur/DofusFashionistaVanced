import pulp

from chardata.tests_a_solve_that_picks_systems_is_worth_at_least_its_plain_set import (
    PLAIN, FloorCase)
from chardata.tests_wakfu_build_solves_on_the_damage_model import outfit

# Two proven joint rounds that would settle the solve by the gap
SETTLING = [outfit(2, ap=-1), outfit(3, ap=9)]


class TheFloorChecksTheClockAfterThePlainStageTests(FloorCase):
    def test_a_plain_stage_that_spends_the_clock_leaves_no_locked_solve(self):
        from fashionistapulp import wakfu_value
        from fashionistapulp.wakfu_model import STEPWISE
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': SETTLING}, deadline=100.0, clock=[0.0],
                                after=[100.0 - wakfu_value.MIN_ROUND_SECONDS + 1])
        self.assertEqual(['plain'], self.kinds())
        self.assertEqual(1, len(result.rounds))
        self.assertEqual(frozenset({1}), result.rounds[0].ids)
        self.assertEqual(9.0, result.best.value)
        self.assertEqual(STEPWISE, result.best.worn.status)
        self.assertFalse(result.converged)

    def test_a_plain_stage_that_leaves_the_clock_still_runs_the_locked_solve(self):
        from fashionistapulp import wakfu_value
        self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)], 'joint': SETTLING},
                       deadline=100.0, clock=[0.0],
                       after=[100.0 - wakfu_value.MIN_ROUND_SECONDS - 1])
        self.assertIn('locked', self.kinds())


class ACrashTheFloorMeetsIsKeptTests(FloorCase):
    def test_a_crash_in_a_later_plain_round_is_recorded_and_the_solve_is_not_settled(self):
        result = self.run_solve({'plain': [outfit(1, ap=3), pulp.PulpSolverError('boom')],
                                 'locked': [outfit(1, ap=9)], 'joint': SETTLING})
        self.assertEqual(((1, 'boom'),), result.crashed)
        self.assertEqual(15.0, result.rounds[0].value)
        self.assertIsNone(result.settled_by)
        self.assertFalse(result.converged)

    def test_a_crash_in_the_plain_stage_counts_as_the_floor_not_as_a_later_round(self):
        result = self.run_solve({'plain': [outfit(1, ap=3), pulp.PulpSolverError('boom')],
                                 'locked': [outfit(1, ap=9)], 'joint': [outfit(2, ap=-1)]})
        self.assertEqual(2, len(result.rounds))
        self.assertEqual(((1, 'boom'),), result.crashed)

    def test_a_crash_on_the_locked_solve_is_recorded_and_the_solve_is_not_settled(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [pulp.PulpSolverError('boom')],
                                 'joint': SETTLING})
        self.assertEqual(((1, 'boom'),), result.crashed)
        self.assertEqual(9.0, result.rounds[0].value)
        self.assertIsNone(result.settled_by)
        self.assertFalse(result.converged)

    def test_a_crash_after_the_floor_adds_to_the_floors_crash(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [pulp.PulpSolverError('boom')],
                                 'joint': [pulp.PulpSolverError('again')]})
        self.assertEqual(((1, 'boom'), (2, 'again')), result.crashed)

    def test_a_clean_floor_records_no_crash_and_still_settles(self):
        result = self.run_solve({'plain': PLAIN, 'locked': [outfit(1, ap=9)],
                                 'joint': SETTLING})
        self.assertEqual((), result.crashed)
        self.assertEqual('gap', result.settled_by)
