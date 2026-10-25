import io
import types
from unittest import mock

import pulp
from django.test import SimpleTestCase

from chardata.management.commands.wakfu_build import Command
from chardata.tests_the_wakfu_round_loop_stops_on_a_certified_gap import (
    OBJECTIVE, stub_build)
from chardata.tests_wakfu_build_solves_on_the_damage_model import Catalogue, outfit
from chardata import tests_wakfu_value_prices_ap_by_the_class_turn as class_turn


def crashing(script, solved, crash_on):
    base = stub_build(script, solved)

    class CrashingBuild(base):
        def solve(self, deadline=None):
            if len(solved) + 1 == crash_on:
                solved.append(self)
                raise pulp.PulpSolverError('Error while trying to execute, exit 3221225477')
            return super().solve(deadline)

    return CrashingBuild


class ASolverCrashIsKeptPerRoundTests(SimpleTestCase):
    def run_loop(self, crash_on, *sets):
        from fashionistapulp import wakfu_value
        role = wakfu_value.DamageDealer(('fire',), 'distance')
        self.solved = []

        def weights(role, level, totals, turn=None):
            return dict(OBJECTIVE, point_ap=totals['ap'])

        def value(role, level, totals, turn=None):
            return float(totals['ap'])

        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild',
                        crashing(list(sets), self.solved, crash_on)), \
                mock.patch.object(wakfu_value, 'linear_weights', weights), \
                mock.patch.object(wakfu_value, 'value', value):
            return wakfu_value.solve(Catalogue(), 50, role, rounds=5)

    def test_a_crash_after_a_first_round_keeps_the_incumbent_and_records_the_round(self):
        result = self.run_loop(2, outfit(1, ap=2), outfit(2, ap=4))
        self.assertEqual(1, len(result.rounds))
        self.assertEqual(1, min(result.best.ids))
        self.assertEqual(1, len(result.crashed))
        self.assertEqual(2, result.crashed[0][0])
        self.assertIn('3221225477', result.crashed[0][1])
        self.assertFalse(result.converged)
        self.assertIsNone(result.settled_by)
        self.assertEqual(2, len(self.solved))

    def test_a_crash_in_a_later_round_keeps_the_best_of_the_rounds_before_it(self):
        result = self.run_loop(3, outfit(1, ap=2), outfit(2, ap=4), outfit(3, ap=9))
        self.assertEqual(2, len(result.rounds))
        self.assertEqual(2, min(result.best.ids))
        self.assertEqual(3, result.crashed[0][0])

    def test_a_loop_without_a_crash_records_none(self):
        result = self.run_loop(99, outfit(1, ap=2), outfit(2, ap=-1), outfit(3, ap=5))
        self.assertEqual((), result.crashed)

    def test_a_crash_in_the_first_round_raises_a_clear_error(self):
        from fashionistapulp import wakfu_value
        with self.assertRaises(wakfu_value.SolverCrashed) as caught:
            self.run_loop(1, outfit(1, ap=2))
        self.assertIn('first round', str(caught.exception))


class ACrashInTheGenericModelKeepsTheClassTurnRoundsTests(SimpleTestCase):
    """The class turn's rounds, then the generic model's, on scripted sets."""

    def run_solve(self, crash_on, *sets):
        from fashionistapulp import wakfu_value
        base, solved = class_turn.scripted(*sets)

        class CrashingBuild(base):
            def solve(self, deadline=None):
                if len(solved) + 1 == crash_on:
                    solved.append(self)
                    raise pulp.PulpSolverError('exit 3221225477')
                return super().solve(deadline)

        with mock.patch('fashionistapulp.wakfu_model.WakfuBuild', CrashingBuild):
            result = wakfu_value.solve(class_turn.Catalogue(), 50,
                                       wakfu_value.DamageDealer(('fire',), 'distance'),
                                       rounds=3, turn=class_turn.FakeTurn())
        return result, solved

    def test_a_crash_on_the_generic_first_round_keeps_the_class_turn_set(self):
        result, solved = self.run_solve(3, class_turn.outfit(1, ap=4),
                                        class_turn.outfit(1, ap=4))
        self.assertEqual(3, len(solved))
        self.assertEqual(2, len(result.rounds))
        self.assertIs(result.rounds[0], result.best)
        self.assertEqual(((3, 'exit 3221225477'),), result.crashed)
        self.assertFalse(result.converged)
        self.assertIsNone(result.settled_by)

    def test_a_crash_on_a_later_generic_round_is_recorded_after_the_class_turn_rounds(self):
        result, solved = self.run_solve(4, class_turn.outfit(1, ap=4),
                                        class_turn.outfit(1, ap=4),
                                        class_turn.outfit(2, ap=1))
        self.assertEqual(4, len(solved))
        self.assertIs(result.rounds[0], result.best)
        self.assertEqual(((4, 'exit 3221225477'),), result.crashed)
        self.assertFalse(result.converged)
        self.assertIsNone(result.settled_by)


class TheCommandReportsACrashedRoundTests(SimpleTestCase):
    def printed(self, crashed):
        from fashionistapulp import wakfu_value
        model = wakfu_value.ModelSolve((), None, False, crashed=crashed)
        result = types.SimpleNamespace(
            states={}, passive_mode=None, not_counted=[], model=model, settled_by=None,
            gap=None, warnings=())
        out = io.StringIO()
        Command(stdout=out).print_fight(result)
        return out.getvalue()

    def test_a_crashed_round_is_reported_with_its_number_and_the_set_is_not_settled(self):
        text = self.printed(((3, 'exit 3221225477'),))
        self.assertIn('round 3: the solver crashed (exit 3221225477)', text)
        self.assertIn('not settled, a round crashed', text)

    def test_a_loop_that_did_not_crash_reports_no_crash(self):
        self.assertNotIn('crashed', self.printed(()))
