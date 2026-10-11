# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A weight cell ships only when both dev folds agree and the table gains on the held-out instance."""
import copy
import statistics
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.weight_table import unit_of

ELEMENTS = ('str',)
UNIT = unit_of(ELEMENTS, 'plain')
ENGINE = {'pow': 1.0, 'hp': 0.2}
PLAN = {split: [(minimums, tier) for minimums, tier, planned in tuning.INSTANCE_PLAN if planned == split]
        for split in tuning.DEV_SPLITS}


def _run(split, which, pow=1.5, hp=0.2, switched=(), proven=True):
    minimums, tier = PLAN[split][which]
    instance = tuning.Instance('Iop', ELEMENTS, 'plain', '200', minimums, tier, split)
    run = tuning.TuneRun(instance)
    read = tuning.Read({}, set(switched), 1000.0, 5000.0, 2.0)
    run.rounds = [tuning.Round(0, {'pow': pow, 'hp': hp}, SimpleNamespace(proven=proven), read, 1.0, {})]
    run.best = 0
    return run


def _four(first, second, third, fourth, **kwargs):
    """The four dev runs: two on each fold, with their pow ratios in the order of the plan."""
    return [_run('dev_a', 0, pow=first, **kwargs), _run('dev_a', 1, pow=second, **kwargs),
            _run('dev_b', 0, pow=third, **kwargs), _run('dev_b', 1, pow=fourth, **kwargs)]


def _pow(runs, engine=ENGINE, group=None, stamp=None):
    return tuning.pool_cell(runs, engine, group, stamp)['pow']


class TheFoldsAgreeTests(SimpleTestCase):

    def test_two_folds_within_the_tolerance_on_the_same_side_of_the_engine_agree(self):
        entry = _pow(_four(1.4, 1.6, 1.5, 1.7))
        self.assertFalse(entry['weak'])
        self.assertNotIn('reason', entry)
        self.assertEqual(1.55, entry['value'])
        self.assertEqual(statistics.median([1.4, 1.6, 1.5, 1.7]), entry['value'])

    def test_the_entry_carries_the_measurement_behind_the_value(self):
        runs = _four(1.4, 1.6, 1.5, 1.7)
        entry = _pow(runs, stamp={'data': '3.7', 'date': '2026-10-11', 'source': 'tune'})
        self.assertEqual({tuning.instance_key(run.instance): run.best_round.ratios['pow'] for run in runs},
                         entry['builds'])
        self.assertEqual((4, [1.4, 1.7], 1.0, [1.5, 1.6]), (entry['n'], entry['spread'], entry['engine'],
                                                           entry['folds']))
        self.assertEqual(('3.7', '2026-10-11', 'tune'), (entry['data'], entry['date'], entry['source']))

    def test_folds_further_apart_than_the_tolerance_disagree(self):
        self.assertEqual(1.25, tuning.FOLD_AGREEMENT)
        self.assertTrue(tuning._folds_disagree(1.2, 1.2 * 1.26, 1.0))
        self.assertFalse(tuning._folds_disagree(1.2, 1.2 * 1.24, 1.0))

    def test_folds_on_opposite_sides_of_the_engine_disagree_however_close(self):
        self.assertTrue(tuning._folds_disagree(0.95, 1.05, 1.0))
        self.assertTrue(tuning._folds_disagree(1.05, 0.95, 1.0))
        self.assertFalse(tuning._folds_disagree(1.05, 1.1, 1.0))

    def test_a_fold_that_is_missing_or_a_zero_beside_a_value_disagrees(self):
        self.assertTrue(tuning._folds_disagree(None, 1.0, 1.0))
        self.assertTrue(tuning._folds_disagree(1.0, None, 1.0))
        self.assertTrue(tuning._folds_disagree(0.0, 0.5, 1.0))
        self.assertFalse(tuning._folds_disagree(0.0, 0.0, 0.0))


class AWeakStatKeepsTheEngineUnlessTheSiblingsAgreeTests(SimpleTestCase):

    def test_disagreeing_folds_make_the_stat_weak_at_the_engine_value(self):
        entry = _pow(_four(1.2, 1.2, 2.0, 2.0))
        self.assertEqual((True, 'folds', 1.0), (entry['weak'], entry['reason'], entry['value']))

    def test_opposite_folds_make_it_weak(self):
        entry = _pow(_four(0.95, 0.95, 1.05, 1.05))
        self.assertEqual((True, 'folds'), (entry['weak'], entry['reason']))

    def test_a_weak_stat_is_read_again_over_the_group_and_pooled_when_that_agrees(self):
        cell = _four(1.2, 1.2, 2.0, 2.0)
        siblings = [_run('dev_a', 0, pow=1.5), _run('dev_a', 1, pow=1.5), _run('dev_b', 0, pow=1.6),
                    _run('dev_b', 1, pow=1.6)] * 2
        entry = _pow(cell, group=cell + siblings)
        self.assertEqual((False, 'pooled'), (entry['weak'], entry['reason']))
        self.assertEqual(statistics.median([run.best_round.ratios['pow'] for run in cell + siblings]), entry['value'])
        self.assertEqual([1.2, 2.0], [entry['folds'][0], entry['folds'][1]])

    def test_a_group_that_disagrees_too_leaves_the_stat_weak(self):
        cell = _four(1.2, 1.2, 2.0, 2.0)
        siblings = _four(1.1, 1.1, 2.2, 2.2)
        entry = _pow(cell, group=cell + siblings)
        self.assertEqual((True, 'folds', 1.0), (entry['weak'], entry['reason'], entry['value']))

    def test_the_group_does_not_rescue_a_stat_most_of_its_runs_switched_on(self):
        cell = _four(1.2, 1.2, 2.0, 2.0)
        siblings = [_run('dev_a', 0, pow=1.5, switched=('pow',)), _run('dev_a', 1, pow=1.5, switched=('pow',)),
                    _run('dev_b', 0, pow=1.6, switched=('pow',)), _run('dev_b', 1, pow=1.6, switched=('pow',))] * 2
        entry = _pow(cell, group=cell + siblings)
        self.assertEqual((True, 'folds'), (entry['weak'], entry['reason']))

    def test_a_stat_that_is_pooled_is_applied_like_any_other(self):
        cell = _four(1.2, 1.2, 2.0, 2.0)
        siblings = _four(1.5, 1.5, 1.6, 1.6) * 2
        entries = tuning.pool_cell(cell, ENGINE, cell + siblings)
        self.assertEqual({'pow': entries['pow']['value']}, {stat: value for stat, value in
                                                            tuning.applied_ratios(entries).items() if stat == 'pow'})


class ASwitchedStatKeepsTheEngineTests(SimpleTestCase):

    def test_a_stat_that_switched_on_more_than_half_the_runs_is_weak(self):
        runs = [_run('dev_a', 0, switched=('pow',)), _run('dev_a', 1, switched=('pow',)),
                _run('dev_b', 0, switched=('pow',)), _run('dev_b', 1)]
        entry = _pow(runs)
        self.assertEqual((True, 'switch', 1.0), (entry['weak'], entry['reason'], entry['value']))

    def test_exactly_half_is_not_more_than_half(self):
        runs = [_run('dev_a', 0, switched=('pow',)), _run('dev_a', 1, switched=('pow',)), _run('dev_b', 0),
                _run('dev_b', 1)]
        self.assertFalse(_pow(runs)['weak'])

    def test_the_other_stats_of_the_cell_are_pooled_on_their_own(self):
        runs = [_run('dev_a', 0, switched=('pow',)), _run('dev_a', 1, switched=('pow',)),
                _run('dev_b', 0, switched=('pow',)), _run('dev_b', 1, hp=0.2)]
        entries = tuning.pool_cell(runs, ENGINE)
        self.assertTrue(entries['pow']['weak'])
        self.assertEqual('switch', entries['pow']['reason'])
        self.assertTrue(entries['hp']['value'] == 0.2)


class AValueStaysInTheBoundsTests(SimpleTestCase):

    def test_a_median_above_four_times_the_engine_is_clamped_to_it(self):
        entry = _pow(_four(6.0, 6.0, 6.0, 6.0))
        self.assertEqual((False, 'bound', 4.0), (entry['weak'], entry['reason'], entry['value']))

    def test_a_median_under_a_quarter_of_the_engine_is_clamped_to_it(self):
        entry = _pow(_four(0.1, 0.1, 0.1, 0.1))
        self.assertEqual((False, 'bound', 0.25), (entry['weak'], entry['reason'], entry['value']))

    def test_the_bounds_are_a_quarter_and_four_times(self):
        self.assertEqual((0.25, 4), tuning.BOUNDS)

    def test_a_stat_the_engine_weighs_at_zero_stays_at_zero(self):
        entries = tuning.pool_cell(_four(0.5, 0.5, 0.5, 0.5), {'pow': 0.0, 'hp': 0.2})
        self.assertEqual((0.0, 'bound'), (entries['pow']['value'], entries['pow']['reason']))

    def test_a_change_under_one_unit_of_weight_is_the_engine_value(self):
        entry = _pow(_four(*[1.0 + 0.4 / UNIT] * 4))
        self.assertEqual((1.0, 'unchanged', False), (entry['value'], entry['reason'], entry['weak']))

    def test_a_change_of_one_unit_of_weight_counts(self):
        entry = _pow(_four(*[1.0 + 1.2 / UNIT] * 4))
        self.assertNotEqual(1.0, entry['value'])
        self.assertNotIn('reason', entry)


class OnlyProvenRunsCountTests(SimpleTestCase):

    def test_an_unproven_run_is_left_out_of_the_pool(self):
        runs = _four(1.4, 1.6, 1.5, 1.7)
        runs.append(_run('dev_a', 0, pow=9.0, proven=False))
        entry = _pow(runs)
        self.assertEqual((4, 1.55), (entry['n'], entry['value']))

    def test_a_cell_with_no_usable_run_keeps_the_engine_for_every_stat(self):
        entries = tuning.pool_cell(_four(1.4, 1.6, 1.5, 1.7, proven=False), ENGINE)
        for stat, entry in entries.items():
            with self.subTest(stat=stat):
                self.assertEqual((True, 'no_runs', ENGINE[stat], 0), (entry['weak'], entry['reason'], entry['value'],
                                                                     entry['n']))

    def test_only_the_applied_stats_come_out_of_a_cell(self):
        entries = tuning.pool_cell(_four(1.4, 1.6, 1.5, 1.7), ENGINE)
        self.assertEqual({'pow': 1.55}, tuning.applied_ratios(entries))
        weak = tuning.pool_cell(_four(1.2, 1.2, 2.0, 2.0), ENGINE)
        self.assertEqual({}, tuning.applied_ratios(weak))


def _evaluation(lo=1.0, hi=1.0, valid=True, pow_share=0.5, **more):
    return dict({'valid': valid, 'u_acc': {'lo': lo, 'hi': hi}, 'pow_share': pow_share}, **more)


def _pair(gain_lo=0.03, gain_hi=0.03, valid=True, engine_share=0.5, table_share=0.55):
    return {'engine': _evaluation(1.0, 1.0, valid, engine_share),
            'table': _evaluation(1.0 + gain_lo, 1.0 + gain_hi, valid, table_share)}


def _entries(**changes):
    entries = tuning.pool_cell(_four(1.4, 1.6, 1.5, 1.7), ENGINE)
    entries.update(changes)
    return entries


def _accept(dev=None, test=None, guarded=None, blind=0.9, value=None):
    dev = [_pair() for _ in range(4)] if dev is None else dev
    test = _pair() if test is None else test
    return tuning.accept_cell(_entries() if value is None else value, dev, test, guarded, blind)


class AGainingCellShipsTests(SimpleTestCase):

    def test_a_cell_that_gains_everywhere_ships(self):
        verdict = _accept()
        self.assertEqual(('shipped', None), (verdict['status'], verdict['reason']))
        self.assertAlmostEqual(0.03, verdict['u_acc_gain']['lo'])
        self.assertAlmostEqual(0.03, verdict['test_gain']['hi'])
        self.assertEqual({'engine': 0.5, 'table': 0.55}, verdict['pow_share'])

    def test_the_minimum_runs_and_the_loss_are_the_specs(self):
        self.assertEqual((4, 0.01), (tuning.MIN_DEV_RUNS, tuning.MAX_LOSS))


class ACellThatDoesNotGainKeepsTheEngineTests(SimpleTestCase):

    def _reason(self, **kwargs):
        verdict = _accept(**kwargs)
        self.assertEqual('engine', verdict['status'])
        return verdict['reason']

    def test_nothing_applied_is_no_change(self):
        weak = tuning.pool_cell(_four(1.2, 1.2, 2.0, 2.0), ENGINE)
        self.assertEqual('no_change', self._reason(value=weak))

    def test_fewer_than_four_valid_dev_runs(self):
        self.assertEqual('dev_runs', self._reason(dev=[_pair() for _ in range(3)]))
        self.assertEqual('dev_runs', self._reason(dev=[_pair(), _pair(), _pair(), _pair(valid=False)]))

    def test_a_fifth_dev_pair_that_is_invalid_does_not_matter(self):
        self.assertEqual('shipped', _accept(dev=[_pair() for _ in range(4)] + [_pair(valid=False)])['status'])

    def test_no_valid_test_instance(self):
        self.assertEqual('test_run', self._reason(test=_pair(valid=False)))
        verdict = tuning.accept_cell(_entries(), [_pair() for _ in range(4)], None, None, 0.9)
        self.assertEqual('test_run', verdict['reason'])

    def test_a_dev_median_that_does_not_gain_at_either_end(self):
        self.assertEqual('dev_gain', self._reason(dev=[_pair(gain_lo=-0.002)] * 3 + [_pair()]))
        self.assertEqual('dev_gain', self._reason(dev=[_pair(gain_hi=-0.002)] * 3 + [_pair()]))
        self.assertEqual('dev_gain', self._reason(dev=[_pair(gain_lo=0.0) for _ in range(4)]))

    def test_a_held_out_instance_that_does_not_gain_at_either_end(self):
        self.assertEqual('test_gain', self._reason(test=_pair(gain_hi=-0.001)))
        self.assertEqual('test_gain', self._reason(test=_pair(gain_lo=0.0)))

    def test_one_instance_that_loses_more_than_a_hundredth_at_either_end(self):
        self.assertEqual('loss', self._reason(dev=[_pair(gain_lo=-0.02, gain_hi=0.1), _pair(), _pair(), _pair()]))
        self.assertEqual('loss', self._reason(dev=[_pair(gain_hi=-0.02, gain_lo=0.1), _pair(), _pair(), _pair()]))

    def test_a_loss_under_a_hundredth_is_allowed(self):
        dev = [_pair(gain_lo=-0.0099, gain_hi=0.1), _pair(), _pair(), _pair()]
        self.assertEqual('shipped', _accept(dev=dev)['status'])
        dev = [_pair(gain_lo=-0.0101, gain_hi=0.1), _pair(), _pair(), _pair()]
        self.assertEqual('loss', _accept(dev=dev)['reason'])

    def test_a_class_the_blind_gate_cannot_vouch_for(self):
        for blind in (None, 0.0, 0.74):
            with self.subTest(blind=blind):
                self.assertEqual('blind', self._reason(blind=blind))
        self.assertEqual('shipped', _accept(blind=0.75)['status'])
        self.assertEqual(0.75, tuning.BLIND_SHARE)

    def test_the_blind_gate_comes_before_everything_else(self):
        verdict = tuning.accept_cell(_entries(), [], None, None, 0.1)
        self.assertEqual('blind', verdict['reason'])


class ThePowerShareCeilingTests(SimpleTestCase):

    def _ships(self, engine, table, where='test'):
        pair = _pair(engine_share=engine, table_share=table)
        kwargs = {'test': pair} if where == 'test' else {'dev': [pair, _pair(), _pair(), _pair()]}
        return _accept(**kwargs)

    def test_a_power_share_up_to_one_and_a_half_times_the_engines_passes(self):
        self.assertEqual('shipped', self._ships(0.4, 0.6)['status'])
        self.assertEqual('ceiling', self._ships(0.4, 0.61)['reason'])

    def test_a_small_share_may_rise_by_five_points(self):
        self.assertEqual('shipped', self._ships(0.02, 0.07)['status'])
        self.assertEqual('ceiling', self._ships(0.02, 0.08)['reason'])

    def test_the_ceiling_is_read_on_the_dev_instances_too(self):
        self.assertEqual('ceiling', self._ships(0.4, 0.9, 'dev')['reason'])

    def test_a_share_that_could_not_be_read_fails_the_ceiling(self):
        self.assertEqual('ceiling', self._ships(None, 0.5)['reason'])
        self.assertEqual('ceiling', self._ships(0.5, None)['reason'])

    def test_a_share_that_falls_passes(self):
        self.assertEqual('shipped', self._ships(0.6, 0.3)['status'])


def _guard(gain=0.02, valid=True, engine_valid=True, **facts):
    table = _evaluation(1.0 + gain, 1.0 + gain, valid)
    table['guard'] = facts
    return {'engine': _evaluation(1.0, 1.0, engine_valid), 'table': table}


class TheGuardedCheckTests(SimpleTestCase):

    def test_a_scenario_without_a_guarded_door_is_not_checked(self):
        self.assertEqual('shipped', _accept(guarded=None)['status'])

    def test_a_guarded_door_that_holds_ships(self):
        self.assertEqual('shipped', _accept(guarded=_guard())['status'])

    def test_a_guarded_door_that_gives_nothing_to_compare_fails(self):
        self.assertEqual('guarded_run', _accept(guarded=_guard(valid=False))['reason'])
        self.assertEqual('guarded_run', _accept(guarded=_guard(engine_valid=False))['reason'])

    def test_a_guard_that_fell_back_fails(self):
        self.assertEqual('guarded_floor', _accept(guarded=_guard(fallback=True))['reason'])

    def test_a_guard_that_came_up_short_fails(self):
        self.assertEqual('guarded_floor', _accept(guarded=_guard(short=['ap']))['reason'])

    def test_a_guarded_door_that_loses_more_than_a_hundredth_fails(self):
        self.assertEqual('guarded_loss', _accept(guarded=_guard(gain=-0.02))['reason'])
        self.assertEqual('shipped', _accept(guarded=_guard(gain=-0.0099))['status'])

    def test_a_guarded_door_that_merely_gains_nothing_still_ships(self):
        self.assertEqual('shipped', _accept(guarded=_guard(gain=0.0))['status'])


class TheShardGateTests(SimpleTestCase):

    def _records(self, shipped, kept, blind=0):
        return ([{'status': 'shipped'}] * shipped + [{'status': 'engine', 'reason': 'no_change'}] * kept
                + [{'status': 'engine', 'reason': 'blind'}] * blind)

    def test_a_shard_stops_when_more_than_a_quarter_of_its_finished_cells_kept_the_engine(self):
        self.assertTrue(tuning.shard_stopped(self._records(5, 3)))
        self.assertFalse(tuning.shard_stopped(self._records(6, 2)))

    def test_it_waits_for_eight_finished_cells(self):
        self.assertFalse(tuning.shard_stopped(self._records(0, 7)))
        self.assertTrue(tuning.shard_stopped(self._records(0, 8)))

    def test_blind_cells_do_not_count_either_way(self):
        self.assertFalse(tuning.shard_stopped(self._records(6, 2, blind=20)))
        self.assertFalse(tuning.shard_stopped(self._records(0, 0, blind=20)))

    def test_the_limits_are_the_specs(self):
        self.assertEqual((0.25, 8), (tuning.SHARD_WEAK_LIMIT, tuning.SHARD_MIN_CELLS))


class TheRecordsAreNotMutatedTests(SimpleTestCase):

    def test_accepting_a_cell_leaves_its_entries_as_they_were(self):
        value = _entries()
        before = copy.deepcopy(value)
        _accept(value=value)
        self.assertEqual(before, value)
