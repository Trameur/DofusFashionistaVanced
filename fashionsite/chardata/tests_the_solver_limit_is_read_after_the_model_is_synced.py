import time
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests_wakfu_build_solves_on_the_damage_model import HELMET, Catalogue, piece

SYNC_SECONDS = 5


class Stopped(Exception):
    pass


class TheSolverLimitIsReadAfterTheModelIsSyncedTests(SimpleTestCase):
    def test_the_time_a_model_takes_to_sync_comes_off_the_solver_limit(self):
        from fashionistapulp import lpproblem, wakfu_value
        from fashionistapulp.lpproblem import LpProblem2
        from fashionistapulp.wakfu_model import WakfuBuild

        clock = [0.0]
        limits = []
        sync = LpProblem2._sync

        def slow_sync(problem):
            clock[0] += SYNC_SECONDS
            return sync(problem)

        def stop(problem, *args, **kwargs):
            limits.append(lpproblem.SOLVER.timeLimit)
            raise Stopped

        build = WakfuBuild(Catalogue(piece(1, HELMET, hp=10)), 50, {'hp': 1})
        build.build()
        with mock.patch.object(time, 'monotonic', lambda: clock[0]), \
                mock.patch.object(LpProblem2, '_sync', slow_sync), \
                mock.patch.object(LpProblem2, 'run', stop):
            with self.assertRaises(Stopped):
                build.solve(30.0)
        self.assertEqual([int(30 - SYNC_SECONDS) - wakfu_value.SOLVE_MARGIN_SECONDS], limits)
