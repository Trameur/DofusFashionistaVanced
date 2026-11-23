# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The solver guard retries a transient failure, fails when the solver stays unreachable, and skips only without pulp."""
import sys
import unittest
from unittest import mock

from chardata import solver_guard
from chardata.solver_guard import PulpSolverUnreachable, pulp_solver_available, pulp_solver_required
from fashionistapulp import lpproblem


def _run(case):
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(case)
    result = unittest.TestResult()
    suite.run(result)
    return result


class ThePulpGuardFailsInsteadOfSkippingTests(unittest.TestCase):

    def setUp(self):
        patcher = mock.patch.object(solver_guard.time, 'sleep')
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_transient_error_is_retried_and_the_tests_run(self):
        with mock.patch.object(lpproblem.SOLVER, 'available', side_effect=[OSError('busy'), True]) as probe:
            self.assertTrue(pulp_solver_available())
        self.assertEqual(2, probe.call_count)

    def test_a_decorated_test_runs_after_a_transient_error(self):
        ran = []

        class Case(unittest.TestCase):
            @pulp_solver_required
            def test_it(self):
                ran.append(True)

        with mock.patch.object(lpproblem.SOLVER, 'available', side_effect=[OSError('busy'), RuntimeError('load'), True]):
            result = _run(Case)
        self.assertEqual(([True], 0, 0, 0), (ran, len(result.failures), len(result.errors), len(result.skipped)))

    def test_a_solver_that_never_answers_makes_the_guard_raise(self):
        with mock.patch.object(lpproblem.SOLVER, 'available', side_effect=OSError('busy')) as probe:
            with self.assertRaises(PulpSolverUnreachable) as caught:
                pulp_solver_available()
        self.assertEqual(solver_guard.ATTEMPTS, probe.call_count)
        self.assertIn('OSError: busy', str(caught.exception))

    def test_a_solver_reported_missing_every_time_makes_the_guard_raise(self):
        with mock.patch.object(lpproblem.SOLVER, 'available', return_value=False):
            with self.assertRaises(PulpSolverUnreachable):
                pulp_solver_available()

    def test_a_dependent_test_fails_and_is_not_skipped_when_the_solver_stays_unreachable(self):
        ran = []

        class Case(unittest.TestCase):
            @pulp_solver_required
            def test_it(self):
                ran.append(True)

        with mock.patch.object(lpproblem.SOLVER, 'available', side_effect=OSError('busy')):
            result = _run(Case)
        self.assertEqual(([], 1, 0, 0), (ran, len(result.failures), len(result.errors), len(result.skipped)))
        self.assertIn('could not be reached', result.failures[0][1])

    def test_a_decorated_class_fails_its_tests_when_the_solver_stays_unreachable(self):
        @pulp_solver_required
        class Case(unittest.TestCase):
            def test_it(self):
                pass

        with mock.patch.object(lpproblem.SOLVER, 'available', return_value=False):
            result = _run(Case)
        self.assertEqual((1, 0), (len(result.failures), len(result.skipped)))

    def test_a_missing_pulp_keeps_the_skip(self):
        with mock.patch.dict(sys.modules, {'pulp': None}):
            self.assertFalse(pulp_solver_available())

            class Case(unittest.TestCase):
                @pulp_solver_required
                def test_it(self):
                    self.fail('must not run')

            result = _run(Case)
        self.assertEqual((0, 0, 1), (len(result.failures), len(result.errors), len(result.skipped)))
        self.assertEqual('no pulp solver available', result.skipped[0][1])

    def test_a_missing_pulp_skips_a_decorated_class_too(self):
        with mock.patch.dict(sys.modules, {'pulp': None}):
            @pulp_solver_required
            class Case(unittest.TestCase):
                def test_it(self):
                    self.fail('must not run')

            result = _run(Case)
        self.assertEqual((0, 1), (len(result.failures), len(result.skipped)))
