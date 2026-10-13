# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The guarded pair is solved when a cell reaches the guarded check and not before: a cell that stops on an earlier
check records that the pair was not run, a scenario with no guarded door records none."""
import json

from django.test import SimpleTestCase

from chardata import tests_a_weight_cell_ships_only_when_both_folds_agree as pooling
from chardata import tests_the_dev_acceptance_reads_the_pooled_weights as doors
from chardata import weight_tuning as tuning

GLASSCANNON = tuning.Cell('Iop', ('str',), 'glasscannon', '200')


class _GuardedRunner(doors._Runner):
    """The dev door, whose guarded solves are comparisons."""

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False, budget_factor=1):
        result = super().run(instance, ratios, forbid, time_limit, guarded, budget_factor)
        if guarded:
            result.credit, result.judgeable = object(), True
        return result

    def guarded_calls(self):
        return [call for call in self.calls if call.guarded]


def _tune(cell=GLASSCANNON, **options):
    runner = _GuardedRunner(**options)
    return runner, tuning.tune_group(runner, [cell], max_rounds=1)[0]


class AGuardedPairIsSolvedOnlyForACellThatReachesItTests(SimpleTestCase):

    def test_a_cell_that_passes_every_earlier_check_has_its_pair_solved(self):
        runner, record = _tune()
        self.assertEqual(('shipped', None), (record['status'], record['reason']))
        self.assertEqual([None, {'pow': record['ratios']['pow']['value']}],
                         [call.ratios for call in runner.guarded_calls()])
        self.assertEqual((True, True), (record['guarded']['engine']['valid'], record['guarded']['table']['valid']))

    def test_a_cell_whose_dev_pairs_do_not_gain_has_none_solved(self):
        runner, record = _tune(dev_pooled=0.95)
        self.assertEqual('dev_gain', record['reason'])
        self.assertEqual([], runner.guarded_calls())
        self.assertEqual(tuning.guarded_not_run(), record['guarded'])

    def test_a_cell_whose_test_pair_does_not_gain_has_none_solved(self):
        runner, record = _tune(test_pooled=0.95, test_panel_shift=0.05)
        self.assertEqual('test_gain', record['reason'])
        self.assertEqual([], runner.guarded_calls())
        self.assertEqual(tuning.guarded_not_run(), record['guarded'])

    def test_a_cell_whose_sets_lose_range_has_none_solved(self):
        runner, record = _tune(table_range=3)
        self.assertEqual('range', record['reason'])
        self.assertEqual([], runner.guarded_calls())
        self.assertEqual(tuning.guarded_not_run(), record['guarded'])

    def test_a_cell_whose_sets_change_the_mp_has_none_solved(self):
        runner, record = _tune(table_mp=1)
        self.assertEqual('mp', record['reason'])
        self.assertEqual([], runner.guarded_calls())
        self.assertEqual(tuning.guarded_not_run(), record['guarded'])

    def test_a_cell_that_applies_nothing_has_none_solved(self):
        runner, record = _tune(factors={})
        self.assertEqual('no_change', record['reason'])
        self.assertEqual([], runner.guarded_calls())
        self.assertEqual(tuning.guarded_not_run(), record['guarded'])

    def test_a_cell_with_too_few_dev_pairs_has_none_solved(self):
        runner, record = _tune(unproven=2)
        self.assertEqual('dev_runs', record['reason'])
        self.assertEqual([], runner.guarded_calls())
        self.assertEqual(tuning.guarded_not_run(), record['guarded'])

    def test_a_scenario_with_no_guarded_door_records_none_and_solves_none(self):
        runner, record = _tune(doors.CELL)
        self.assertEqual('shipped', record['status'])
        self.assertEqual([], runner.guarded_calls())
        self.assertIsNone(record['guarded'])


class ThePairThatWasNotRunSaysSoTests(SimpleTestCase):

    def test_neither_side_is_a_comparison_and_both_name_why(self):
        pair = tuning.guarded_not_run()
        self.assertEqual([False, False], [pair[side]['valid'] for side in ('engine', 'table')])
        self.assertEqual(['not_run', 'not_run'], [pair[side]['dropped'] for side in ('engine', 'table')])
        self.assertIsNone(pair['delta'])

    def test_it_is_not_none_and_is_not_empty(self):
        self.assertTrue(tuning.guarded_not_run())

    def test_it_reads_back_from_a_json_record(self):
        self.assertEqual(tuning.guarded_not_run(), json.loads(json.dumps(tuning.guarded_not_run())))

    def test_a_judgement_handed_it_as_the_pair_finds_no_comparison(self):
        verdict = pooling._accept(guarded=tuning.guarded_not_run())
        self.assertEqual(('engine', 'guarded_run'), (verdict['status'], verdict['reason']))


class AcceptCellMakesTheGuardedPairWhenItReachesTheCheckTests(SimpleTestCase):

    def _maker(self, pair=None):
        calls = []

        def make():
            calls.append(1)
            return pooling._pair() if pair is None else pair
        return calls, make

    def test_it_is_not_made_when_an_earlier_check_fails(self):
        failing = {'blind': dict(blind=0.1), 'dev_runs': dict(dev=[pooling._pair() for _ in range(3)]),
                   'dev_gain': dict(dev=[pooling._pair(gain_lo=-0.002)] * 3 + [pooling._pair()]),
                   'test_run': dict(test=pooling._pair(valid=False)),
                   'test_gain': dict(test=pooling._pair(gain_hi=-0.001)),
                   'loss': dict(dev=[pooling._pair(gain_lo=-0.02, gain_hi=0.1)] + [pooling._pair()] * 3),
                   'range': dict(dev=[pooling._pair(range_delta=-2) for _ in range(4)]),
                   'mp': dict(dev=[pooling._pair(mp_delta=1)] + [pooling._pair()] * 3),
                   'ceiling': dict(dev=[pooling._pair(table_share=0.9) for _ in range(4)])}
        for reason, options in failing.items():
            calls, make = self._maker()
            with self.subTest(reason=reason):
                verdict = pooling._accept(guarded=make, **options)
                self.assertEqual(reason, verdict['reason'])
                self.assertEqual([], calls)
                self.assertNotIn('guarded', verdict)

    def test_it_is_made_once_when_every_earlier_check_passes_and_the_verdict_keeps_it(self):
        pair = pooling._pair()
        calls, make = self._maker(pair)
        verdict = pooling._accept(guarded=make)
        self.assertEqual(([1], 'shipped', pair), (calls, verdict['status'], verdict['guarded']))

    def test_the_pair_it_makes_decides(self):
        short = pooling._pair()
        short['table']['guard'] = {'short': ['ap']}
        for reason, pair in (('guarded_floor', short), ('guarded_loss', pooling._pair(gain_lo=-0.02)),
                             ('guarded_run', pooling._pair(valid=False))):
            _calls, make = self._maker(pair)
            with self.subTest(reason=reason):
                self.assertEqual(reason, pooling._accept(guarded=make)['reason'])

    def test_a_pair_handed_over_made_is_read_as_before_and_not_added_to_the_verdict(self):
        verdict = pooling._accept(guarded=pooling._pair(gain_lo=-0.02))
        self.assertEqual('guarded_loss', verdict['reason'])
        self.assertNotIn('guarded', verdict)

    def test_a_scenario_with_no_guarded_door_ships_without_one(self):
        verdict = pooling._accept(guarded=None)
        self.assertEqual('shipped', verdict['status'])
        self.assertNotIn('guarded', verdict)

    def test_a_cell_with_the_bluff_note_still_reaches_the_check_before_it_keeps_the_engine(self):
        calls, make = self._maker()
        verdict = pooling._accept(guarded=make, notes=(tuning.BLUFF_NOTE,))
        self.assertEqual(([1], tuning.BLUFF_NOTE), (calls, verdict['reason']))
