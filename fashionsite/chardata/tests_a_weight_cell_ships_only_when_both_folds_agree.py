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
PLAN = {split: [tier for tier, planned in tuning.INSTANCE_PLAN if planned == split] for split in tuning.DEV_SPLITS}


def _run(split, which, pow=1.5, hp=0.2, switched=(), proven=True, elements=ELEMENTS, engine=None, **more):
    instance = tuning.Instance('Iop', elements, 'plain', '200', PLAN[split][which], split)
    run = tuning.TuneRun(instance)
    run.engine_ratios = dict(ENGINE if engine is None else engine)
    read = tuning.Read({}, set(switched), 1000.0, 5000.0, 2.0)
    run.rounds = [tuning.Round(0, dict({'pow': pow, 'hp': hp}, **more), SimpleNamespace(proven=proven), read, 1.0, {})]
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


class AGroupPoolsOnlyTheCellsThatWeighTheStatTests(SimpleTestCase):

    def _cell(self, stat, engine, values, elements=ELEMENTS):
        """The four dev runs of a cell: `values` are its stat's ratios in the order of the plan."""
        runs = []
        for (split, which), value in zip([('dev_a', 0), ('dev_a', 1), ('dev_b', 0), ('dev_b', 1)], values):
            runs.append(_run(split, which, elements=elements, engine=dict(ENGINE, **{stat: engine}), **{stat: value}))
        return runs

    def test_a_fixed_damage_the_cell_weighs_is_not_pulled_to_zero_by_cells_that_play_another_element(self):
        engine = dict(ENGINE, earthdam=6.0)
        cell = self._cell('earthdam', 6.0, [9.0, 9.0, 5.7, 5.7])
        others = [run for element in ('int', 'cha', 'agi') for run in self._cell('earthdam', 0.0, [0.0] * 4,
                                                                                (element,))]
        entry = tuning.pool_cell(cell, engine, cell + others)['earthdam']
        self.assertEqual((True, 'folds', 6.0), (entry['weak'], entry['reason'], entry['value']))
        self.assertNotEqual('bound', entry.get('reason'))
        self.assertNotIn('earthdam', tuning.applied_ratios(tuning.pool_cell(cell, engine, cell + others)))

    def test_the_move_of_the_cells_that_weigh_it_is_applied_to_this_cells_engine_weight(self):
        engine = dict(ENGINE, neutdam=3.0)
        duo = ('str', 'int')
        cell = self._cell('neutdam', 3.0, [3.6, 3.6, 5.1, 5.1], duo)
        weighing = self._cell('neutdam', 2.0, [2.8] * 4, ('str', 'cha'))
        silent = self._cell('neutdam', 0.0, [0.0] * 4, ('agi', 'int'))
        entry = tuning.pool_cell(cell, engine, cell + weighing + silent)['neutdam']
        self.assertEqual((False, 'pooled'), (entry['weak'], entry['reason']))
        self.assertAlmostEqual(1.4 * 3.0, entry['value'])

    def test_a_cell_that_does_not_weigh_the_stat_keeps_zero(self):
        engine = dict(ENGINE, neutdam=0.0)
        cell = self._cell('neutdam', 0.0, [0.0] * 4)
        weighing = self._cell('neutdam', 2.0, [2.8] * 4, ('int',))
        entry = tuning.pool_cell(cell, engine, cell + weighing)['neutdam']
        self.assertEqual(0.0, entry['value'])
        self.assertEqual({}, {stat: value for stat, value in tuning.applied_ratios(
            tuning.pool_cell(cell, engine, cell + weighing)).items() if stat == 'neutdam'})

    def test_the_folds_of_the_group_are_read_on_the_moves_not_on_the_weights(self):
        engine = dict(ENGINE, neutdam=3.0)
        cell = self._cell('neutdam', 3.0, [3.6, 3.6, 5.1, 5.1])
        large = self._cell('neutdam', 30.0, [36.0, 36.0, 66.0, 66.0], ('int',))
        entry = tuning.pool_cell(cell, engine, cell + large)['neutdam']
        self.assertEqual((True, 'folds', 3.0), (entry['weak'], entry['reason'], entry['value']))

    def test_cells_that_switched_on_the_stat_count_only_among_the_cells_that_weigh_it(self):
        engine = dict(ENGINE, neutdam=3.0)
        cell = self._cell('neutdam', 3.0, [3.6, 3.6, 5.1, 5.1])
        weighing = self._cell('neutdam', 2.0, [2.8] * 4, ('int',))
        silent = [_run(split, which, elements=('cha',), engine=dict(ENGINE, neutdam=0.0), neutdam=0.0,
                       switched=('neutdam',)) for split, which in (('dev_a', 0), ('dev_a', 1), ('dev_b', 0),
                                                                    ('dev_b', 1))] * 4
        entry = tuning.pool_cell(cell, engine, cell + weighing + silent)['neutdam']
        self.assertEqual('pooled', entry['reason'])


DUO = ('str', 'int')
DUO_ENGINE = dict(ENGINE, str=1.0, int=1.0)
FOLDS = (('dev_a', 0), ('dev_a', 1), ('dev_b', 0), ('dev_b', 1))


def _duo_cell(elements, lead_values, **more):
    """The four dev runs of a duo cell, in the order of the plan: `lead_values` are the first element's shares."""
    first, second = elements
    engine = dict(ENGINE, **{first: 1.0, second: 1.0})
    return [_run(split, which, elements=elements, engine=engine, **dict({first: value, second: 2 - value}, **more))
            for (split, which), value in zip(FOLDS, lead_values)]


def _shipped_shares(entries, duo=DUO):
    """What the table would write for the two shares: the engine's 1.0 where an entry is weak."""
    return {stat: (1.0 if entries[stat]['weak'] else entries[stat]['value']) for stat in duo}


class ADuosSharesArePooledAsOneTests(SimpleTestCase):

    def test_a_pair_inside_the_bounds_whose_folds_agree_ships_and_sums_to_two(self):
        entries = tuning.pool_cell(_duo_cell(DUO, [1.04, 1.04, 1.10, 1.10]), DUO_ENGINE)
        self.assertEqual([False, False], [entries[stat]['weak'] for stat in DUO])
        self.assertAlmostEqual(1.07, entries['str']['value'])
        self.assertAlmostEqual(0.93, entries['int']['value'])
        self.assertAlmostEqual(2.0, sum(_shipped_shares(entries).values()))
        self.assertEqual({'str', 'int'}, {stat for stat in tuning.applied_ratios(entries) if stat in DUO})

    def test_asymmetric_folds_do_not_leave_one_share_weak_and_the_other_not(self):
        entries = tuning.pool_cell(_duo_cell(DUO, [1.12, 1.12, 1.38, 1.38]), DUO_ENGINE)
        self.assertFalse(tuning._folds_disagree(*entries['str']['folds'], 1.0))
        self.assertTrue(tuning._folds_disagree(*entries['int']['folds'], 1.0))
        self.assertEqual([False, False], [entries[stat]['weak'] for stat in DUO])
        self.assertAlmostEqual(2.0, sum(_shipped_shares(entries).values()))

    def test_asymmetric_folds_that_pass_one_share_and_fail_the_other_make_both_weak_at_the_engine(self):
        entries = tuning.pool_cell(_duo_cell(DUO, [0.7, 0.7, 0.9, 0.9]), DUO_ENGINE)
        self.assertTrue(tuning._folds_disagree(*entries['str']['folds'], 1.0))
        self.assertFalse(tuning._folds_disagree(*entries['int']['folds'], 1.0))
        self.assertEqual([(True, 'folds', 1.0), (True, 'folds', 1.0)],
                         [(entries[stat]['weak'], entries[stat]['reason'], entries[stat]['value']) for stat in DUO])
        self.assertEqual({}, {stat: value for stat, value in tuning.applied_ratios(entries).items() if stat in DUO})

    def test_a_pair_pushed_past_the_bounds_is_clamped_with_both_elements_still_played(self):
        entries = tuning.pool_cell(_duo_cell(DUO, [1.9] * 4), DUO_ENGINE)
        low, high = tuning.share_bounds()
        self.assertEqual({'str': (high, 'bound'), 'int': (low, 'bound')},
                         {stat: (entries[stat]['value'], entries[stat]['reason']) for stat in DUO})
        self.assertAlmostEqual(2.0, entries['str']['value'] + entries['int']['value'])
        self.assertGreaterEqual(entries['int']['value'] / entries['str']['value'], tuning.PLAYED_SHARE)
        self.assertEqual(tuning.clamp_shares({'str': 1.9, 'int': 0.1}), {stat: entries[stat]['value'] for stat in DUO})

    def test_a_change_of_less_than_a_unit_leaves_both_shares_at_the_engine(self):
        entries = tuning.pool_cell(_duo_cell(DUO, [1.0 + 0.4 / UNIT] * 4), DUO_ENGINE)
        self.assertEqual([(1.0, 'unchanged'), (1.0, 'unchanged')],
                         [(entries[stat]['value'], entries[stat]['reason']) for stat in DUO])
        self.assertEqual({}, {stat: value for stat, value in tuning.applied_ratios(entries).items() if stat in DUO})

    def test_no_usable_run_leaves_both_shares_weak_at_the_engine(self):
        entries = tuning.pool_cell(_duo_cell(DUO, [1.05] * 4, proven=False), DUO_ENGINE)
        self.assertEqual([(True, 'no_runs', 1.0), (True, 'no_runs', 1.0)],
                         [(entries[stat]['weak'], entries[stat]['reason'], entries[stat]['value']) for stat in DUO])

    def test_the_second_share_keeps_its_own_measurement(self):
        runs = _duo_cell(DUO, [1.12, 1.12, 1.38, 1.38])
        entries = tuning.pool_cell(runs, DUO_ENGINE)
        self.assertEqual(4, entries['int']['n'])
        for got, wanted in zip(entries['int']['spread'] + entries['int']['folds'], [0.62, 0.88, 0.88, 0.62]):
            self.assertAlmostEqual(wanted, got)
        self.assertEqual({tuning.instance_key(run.instance): run.best_round.ratios['int'] for run in runs},
                         entries['int']['builds'])

    def test_a_cell_that_plays_one_element_holds_no_shares(self):
        self.assertFalse(set(DUO) & set(tuning.pool_cell(_four(1.4, 1.6, 1.5, 1.7), ENGINE)))

    def test_whatever_the_folds_the_shipped_pair_sums_to_two(self):
        for first, second in ((1.12, 1.38), (0.7, 0.9), (1.0, 1.9), (1.3, 1.3), (0.5, 1.5), (1.9, 1.9), (1.04, 1.1)):
            entries = tuning.pool_cell(_duo_cell(DUO, [first, first, second, second]), DUO_ENGINE)
            with self.subTest(first=first, second=second):
                self.assertAlmostEqual(2.0, sum(_shipped_shares(entries).values()))
                self.assertEqual(entries['str']['weak'], entries['int']['weak'])
                self.assertEqual(entries['str'].get('reason'), entries['int'].get('reason'))


class AGroupPoolsAShareOnlyWhereItSetsThePairTests(SimpleTestCase):

    def test_a_weak_first_share_is_pooled_over_the_cells_it_leads(self):
        cell = _duo_cell(DUO, [0.95, 0.95, 1.1, 1.1])
        sibling = _duo_cell(('str', 'cha'), [1.06] * 4)
        entries = tuning.pool_cell(cell, DUO_ENGINE, cell + sibling)
        self.assertEqual([(False, 'pooled'), (False, 'pooled')],
                         [(entries[stat]['weak'], entries[stat]['reason']) for stat in DUO])
        self.assertAlmostEqual(1.06, entries['str']['value'])
        self.assertAlmostEqual(0.94, entries['int']['value'])

    def test_the_second_share_of_another_cell_does_not_pool_into_a_first_share(self):
        cell = _duo_cell(('int', 'cha'), [0.95, 0.95, 1.1, 1.1])
        follower = _duo_cell(DUO, [0.9] * 4)
        entries = tuning.pool_cell(cell, dict(ENGINE, int=1.0, cha=1.0), cell + follower)
        self.assertEqual([(True, 'folds'), (True, 'folds')],
                         [(entries[stat]['weak'], entries[stat]['reason']) for stat in ('int', 'cha')])
        self.assertEqual([1.0, 1.0], [entries[stat]['value'] for stat in ('int', 'cha')])


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


def _evaluation(lo=1.0, hi=1.0, valid=True, pow_share=0.5, panel_lo=None, panel_hi=None, range_=6, mp=6, **more):
    panel = {'lo': lo if panel_lo is None else panel_lo, 'hi': hi if panel_hi is None else panel_hi}
    stats = {'range': range_, 'mp': mp, 'init': 0, 'lock': 0, 'dodge': 0}
    return dict({'valid': valid, 'u_acc': {'lo': lo, 'hi': hi}, 'u_panel': panel, 'pow_share': pow_share,
                 'stats': stats}, **more)


def _pair(gain_lo=0.03, gain_hi=0.03, valid=True, engine_share=0.5, table_share=0.55, panel_lo=None, panel_hi=None,
          range_delta=0, mp_delta=0):
    """A pair whose panel score gains like the credited one unless `panel_lo` and `panel_hi` say otherwise, and whose
    table set has `range_delta` more range and `mp_delta` more MP than the engine's."""
    return {'engine': _evaluation(1.0, 1.0, valid, engine_share),
            'table': _evaluation(1.0 + gain_lo, 1.0 + gain_hi, valid, table_share,
                                 1.0 + (gain_lo if panel_lo is None else panel_lo),
                                 1.0 + (gain_hi if panel_hi is None else panel_hi), 6 + range_delta, 6 + mp_delta)}


def _entries(**changes):
    entries = tuning.pool_cell(_four(1.4, 1.6, 1.5, 1.7), ENGINE)
    entries.update(changes)
    return entries


def _accept(dev=None, test=None, guarded=None, blind=0.9, value=None, notes=()):
    dev = [_pair() for _ in range(4)] if dev is None else dev
    test = _pair() if test is None else test
    return tuning.accept_cell(_entries() if value is None else value, dev, test, guarded, blind, notes)


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

    def test_a_dev_median_that_gains_only_through_the_effect_table_credit(self):
        self.assertEqual('panel_gain', self._reason(dev=[_pair(panel_lo=-0.02)] * 3 + [_pair()]))
        self.assertEqual('panel_gain', self._reason(dev=[_pair(panel_hi=-0.02)] * 3 + [_pair()]))

    def test_a_panel_gain_of_zero_is_allowed(self):
        self.assertEqual('shipped', _accept(dev=[_pair(panel_lo=0.0, panel_hi=0.0) for _ in range(4)])['status'])

    def test_a_panel_gain_is_the_median_of_the_dev_pairs(self):
        dev = [_pair(panel_lo=-0.05), _pair(), _pair(), _pair()]
        self.assertEqual('shipped', _accept(dev=dev)['status'])
        verdict = _accept(dev=[_pair(panel_lo=-0.05)] * 2 + [_pair()] * 2)
        self.assertEqual(('engine', 'panel_gain'), (verdict['status'], verdict['reason']))
        self.assertAlmostEqual(-0.01, verdict['panel_gain']['lo'])

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


class TheTestPairKeepsItsPanelTurnTests(SimpleTestCase):
    """The held-out pair is judged on the panel's turn alone too: a gain made of effect credit does not stand for it."""

    def _verdict(self, **panel):
        return _accept(test=_pair(0.1, 0.1, **panel))

    def test_a_test_pair_that_gains_only_through_the_effect_credit_keeps_the_engine(self):
        for end in ('panel_lo', 'panel_hi'):
            with self.subTest(end=end):
                verdict = self._verdict(**{end: -0.05})
                self.assertEqual(('engine', 'test_panel'), (verdict['status'], verdict['reason']))

    def test_a_panel_loss_of_a_hundredth_is_allowed_on_the_test_pair(self):
        self.assertEqual('shipped', self._verdict(panel_lo=-0.0099, panel_hi=-0.0099)['status'])
        self.assertEqual('test_panel', self._verdict(panel_lo=-0.0101)['reason'])
        self.assertEqual('test_panel', self._verdict(panel_hi=-0.0101)['reason'])

    def test_a_test_pair_with_no_panel_score_keeps_the_engine(self):
        test = _pair(0.1, 0.1)
        test['table']['u_panel'] = {'lo': None, 'hi': None}
        self.assertEqual('test_panel', _accept(test=test)['reason'])

    def test_the_dev_panel_median_is_judged_first(self):
        verdict = _accept(dev=[_pair(panel_lo=-0.02)] * 3 + [_pair()], test=_pair(0.1, 0.1, panel_lo=-0.05))
        self.assertEqual('panel_gain', verdict['reason'])

    def test_the_test_panel_is_judged_before_the_test_gain(self):
        self.assertEqual('test_panel', _accept(test=_pair(-0.001, -0.001, panel_lo=-0.05))['reason'])

    def test_the_verdict_keeps_the_panel_gain_of_the_test_pair(self):
        verdict = self._verdict(panel_lo=-0.05, panel_hi=0.04)
        self.assertAlmostEqual(-0.05, verdict['test_panel_gain']['lo'])
        self.assertAlmostEqual(0.04, verdict['test_panel_gain']['hi'])
        self.assertAlmostEqual(0.03, _accept()['test_panel_gain']['lo'])


class TheBlindStatsOfAPairHoldTests(SimpleTestCase):
    """Range and MP are in no score: the table's set must not give up the engine's."""

    def _dev(self, *range_deltas):
        return [_pair(range_delta=delta) for delta in range_deltas]

    def test_a_dev_median_of_one_range_lost_is_allowed(self):
        self.assertEqual('shipped', _accept(dev=self._dev(-2, -1, -1, 0))['status'])
        self.assertEqual('shipped', _accept(dev=self._dev(-2, -2, 0, 0))['status'])

    def test_a_dev_median_of_more_than_one_range_lost_keeps_the_engine(self):
        for deltas in ((-3, -2, -2, 0), (-2, -2, -1, 0), (-1, -2, -2, -2)):
            with self.subTest(deltas=deltas):
                verdict = _accept(dev=self._dev(*deltas))
                self.assertEqual(('engine', 'range'), (verdict['status'], verdict['reason']))

    def test_one_dev_pair_that_loses_more_range_than_the_median_does_is_no_fault(self):
        self.assertEqual('shipped', _accept(dev=self._dev(-4, 0, 0, 0))['status'])

    def test_a_test_pair_that_loses_more_than_one_range_keeps_the_engine(self):
        self.assertEqual('shipped', _accept(test=_pair(range_delta=-1))['status'])
        self.assertEqual('range', _accept(test=_pair(range_delta=-2))['reason'])

    def test_range_gained_is_no_fault(self):
        self.assertEqual('shipped', _accept(dev=self._dev(3, 3, 3, 3), test=_pair(range_delta=2))['status'])

    def test_a_range_that_could_not_be_read_keeps_the_engine(self):
        dev = self._dev(0, 0, 0, 0)
        del dev[2]['engine']['stats']['range']
        self.assertEqual('range', _accept(dev=dev)['reason'])
        test = _pair()
        del test['table']['stats']
        self.assertEqual('range', _accept(test=test)['reason'])

    def test_the_verdict_keeps_the_range_it_judged(self):
        verdict = _accept(dev=self._dev(-2, -1, -1, 0), test=_pair(range_delta=-1))
        self.assertEqual({'dev_median': -1, 'test': -1}, verdict['range_delta'])

    def test_an_mp_change_on_a_dev_pair_keeps_the_engine(self):
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                verdict = _accept(dev=[_pair(mp_delta=delta), _pair(), _pair(), _pair()])
                self.assertEqual(('engine', 'mp'), (verdict['status'], verdict['reason']))

    def test_an_mp_change_on_the_test_pair_keeps_the_engine(self):
        for delta in (-1, 1):
            with self.subTest(delta=delta):
                self.assertEqual('mp', _accept(test=_pair(mp_delta=delta))['reason'])

    def test_an_mp_that_could_not_be_read_keeps_the_engine(self):
        test = _pair()
        test['engine']['stats'] = {'range': 6}
        self.assertEqual('mp', _accept(test=test)['reason'])

    def test_the_verdict_keeps_the_mp_it_judged(self):
        verdict = _accept(dev=[_pair(mp_delta=1), _pair(), _pair(), _pair()])
        self.assertEqual({'dev': [1, 0, 0, 0], 'test': 0}, verdict['mp_delta'])

    def test_initiative_lock_and_dodge_are_recorded_and_hold_nothing(self):
        test = _pair()
        test['table']['stats'].update(init=-2000, lock=-5, dodge=-5)
        self.assertEqual('shipped', _accept(test=test)['status'])

    def test_the_loss_is_judged_before_the_range_and_the_range_before_the_mp_and_the_ceiling(self):
        lossy = [_pair(gain_lo=-0.02, gain_hi=0.1), _pair(), _pair(), _pair()]
        self.assertEqual('loss', _accept(dev=lossy, test=_pair(range_delta=-2))['reason'])
        self.assertEqual('range', _accept(test=_pair(range_delta=-2, mp_delta=1))['reason'])
        self.assertEqual('mp', _accept(test=_pair(mp_delta=1, table_share=0.99))['reason'])


class ThePowerShareCeilingTests(SimpleTestCase):

    def _ships(self, engine, table, where='test'):
        pair = _pair(engine_share=engine, table_share=table)
        kwargs = {'test': pair} if where == 'test' else {'dev': [pair, _pair(), _pair(), _pair()]}
        return _accept(**kwargs)

    def test_a_power_share_up_to_one_and_a_half_times_the_engines_passes(self):
        self.assertEqual('shipped', self._ships(0.4, 0.6)['status'])
        self.assertEqual('ceiling', self._ships(0.4, 0.61)['reason'])

    def test_a_share_may_always_rise_to_a_fifth(self):
        self.assertEqual(0.20, tuning.CEILING_FLOOR)
        self.assertEqual('shipped', self._ships(0.0, 0.20)['status'])
        self.assertEqual('shipped', self._ships(0.02, 0.20)['status'])
        self.assertEqual('ceiling', self._ships(0.02, 0.21)['reason'])

    def test_the_floor_does_not_lift_a_share_that_is_already_above_it(self):
        self.assertEqual('shipped', self._ships(0.5, 0.75)['status'])
        self.assertEqual('ceiling', self._ships(0.5, 0.76)['reason'])

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

    def test_a_guard_that_fell_back_is_no_comparison(self):
        self.assertEqual('guarded_run', _accept(guarded=_guard(fallback=True))['reason'])

    def test_a_guard_that_ran_out_of_time_is_no_comparison(self):
        self.assertEqual('guarded_run', _accept(guarded=_guard(out_of_time=True))['reason'])

    def test_the_facts_are_read_on_the_engine_side_too(self):
        for name in tuning.GUARD_UNFIT:
            with self.subTest(name=name):
                guarded = _guard()
                guarded['engine']['guard'] = {name: True}
                self.assertEqual('guarded_run', _accept(guarded=guarded)['reason'])

    def test_a_guard_that_came_up_short_fails(self):
        self.assertEqual('guarded_floor', _accept(guarded=_guard(short=['ap']))['reason'])

    def test_a_guarded_door_that_loses_more_than_a_hundredth_fails(self):
        self.assertEqual('guarded_loss', _accept(guarded=_guard(gain=-0.02))['reason'])
        self.assertEqual('shipped', _accept(guarded=_guard(gain=-0.0099))['status'])

    def test_a_guarded_door_that_merely_gains_nothing_still_ships(self):
        self.assertEqual('shipped', _accept(guarded=_guard(gain=0.0))['status'])


class TheShardGateTests(SimpleTestCase):

    def _records(self, shipped, unjudged, blind=0, judged=0):
        return ([{'status': 'shipped'}] * shipped + [{'status': 'engine', 'reason': 'test_run'}] * unjudged
                + [{'status': 'engine', 'reason': 'ceiling'}] * judged
                + [{'status': 'engine', 'reason': 'blind'}] * blind)

    def test_a_shard_stops_when_more_than_a_quarter_of_its_finished_cells_could_not_be_judged(self):
        self.assertTrue(tuning.shard_stopped(self._records(5, 3)))
        self.assertFalse(tuning.shard_stopped(self._records(6, 2)))

    def test_it_waits_for_eight_finished_cells(self):
        self.assertFalse(tuning.shard_stopped(self._records(0, 7)))
        self.assertTrue(tuning.shard_stopped(self._records(0, 8)))

    def test_a_cell_that_was_judged_and_kept_the_engine_is_no_sign_of_a_broken_run(self):
        self.assertFalse(tuning.shard_stopped(self._records(0, 0, judged=8)))
        self.assertFalse(tuning.shard_stopped(self._records(0, 2, judged=6)))

    def test_the_four_reasons_that_say_a_cell_was_not_judged(self):
        self.assertEqual(('engine_run', 'dev_runs', 'test_run', 'guarded_run'), tuning.UNJUDGEABLE)
        for reason in tuning.UNJUDGEABLE:
            with self.subTest(reason=reason):
                records = [{'status': 'engine', 'reason': reason}] * 3 + [{'status': 'shipped'}] * 5
                self.assertTrue(tuning.shard_stopped(records))
        for reason in ('dev_gain', 'panel_gain', 'test_panel', 'test_gain', 'loss', 'range', 'mp', 'ceiling',
                       'guarded_floor', 'guarded_loss', 'no_change'):
            with self.subTest(reason=reason):
                records = [{'status': 'engine', 'reason': reason}] * 8
                self.assertFalse(tuning.shard_stopped(records))

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


class ACellWhoseSpellRowsAreUnverifiedKeepsTheEngineTests(SimpleTestCase):

    NOTED = (tuning.BLUFF_NOTE,)

    def test_a_cell_that_gains_everywhere_is_held_on_the_engine(self):
        verdict = _accept(notes=self.NOTED)
        self.assertEqual(('engine', tuning.BLUFF_NOTE), (verdict['status'], verdict['reason']))

    def test_the_gains_of_the_held_cell_are_kept_in_the_verdict(self):
        verdict = _accept(notes=self.NOTED)
        self.assertAlmostEqual(0.03, verdict['u_acc_gain']['lo'])
        self.assertAlmostEqual(0.03, verdict['test_gain']['hi'])

    def test_another_note_holds_nothing(self):
        self.assertEqual('shipped', _accept(notes=('repeated_dev_sets',))['status'])

    def test_a_reason_that_comes_first_is_kept(self):
        verdict = _accept(notes=self.NOTED, test=_pair(gain_hi=-0.001))
        self.assertEqual('test_gain', verdict['reason'])
        verdict = _accept(notes=self.NOTED, dev=[_pair(gain_lo=-0.002)] * 3 + [_pair()])
        self.assertEqual('dev_gain', verdict['reason'])

    def test_the_guarded_door_is_judged_before_the_hold(self):
        guarded = _guard(valid=False)
        self.assertEqual('guarded_run', _accept(notes=self.NOTED, guarded=guarded)['reason'])
