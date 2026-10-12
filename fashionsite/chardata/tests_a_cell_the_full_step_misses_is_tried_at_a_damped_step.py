# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A cell the full step misses on its dev pairs is solved again at the middle of the engine's weights and the pooled
ones; the step is chosen on the dev pairs alone and the test pair is solved once, for the step chosen."""
import copy
import json
import math
import os
import tempfile
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import tests_a_weight_cell_ships_only_when_both_folds_agree as pooling
from chardata import tests_the_dev_acceptance_reads_the_pooled_weights as doors
from chardata import weight_tuning as tuning
from chardata.weight_table import engine_ratios, unit_of

CELL = doors.CELL
FULL = doors.POOLED
#: the dev instances read power at 1.5 times the engine's: the damped step is the midpoint of that move and none
DAMPED_MOVE = math.sqrt(1.5)
DAMPED = doors.ENGINE['pow'] * DAMPED_MOVE
STEP = {'dev': 1.05, 'test': 1.05, 'range': 5, 'mp': 0, 'dev_panel': 0.0, 'test_panel': 0.0}


class _StepRunner(doors._Runner):
    """The fake door of the dev tests, whose table solves score, keep range and MP and read the panel by the step they
    are made at: the full pooled power or the damped one. `full` and `damped` override the defaults of STEP."""

    def __init__(self, full=None, damped=None, **options):
        super().__init__(**options)
        self.steps = {'full': dict(STEP, **(full or {})), 'damped': dict(STEP, **(damped or {}))}
        self.table_calls = []

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False, budget_factor=1):
        if ratios is not None and set(ratios) == self.pooled_stats:
            base = engine_ratios(instance.char_class, instance.elements, instance.scenario, doors.VERSION)['pow']
            step = 'damped' if abs(ratios['pow'] / base - DAMPED_MOVE) < 1e-9 else 'full'
            facts = self.steps[step]
            self.pooled = {'dev_a': facts['dev'], 'dev_b': facts['dev'], 'test': facts['test']}
            self.table_range, self.table_mp = facts['range'], facts['mp']
            self.panel_shift = {'dev_a': facts['dev_panel'], 'dev_b': facts['dev_panel'],
                                'test': facts['test_panel']}
            self.table_calls.append(SimpleNamespace(step=step, instance=instance, forbid=set(forbid)))
        result = super().run(instance, ratios, forbid, time_limit, guarded, budget_factor)
        if guarded:
            result.credit, result.judgeable = object(), True
        return result

    def dev_table_calls(self, step=None):
        return [call for call in self.table_calls if call.instance.split != 'test' and step in (None, call.step)]

    def test_table_calls(self):
        return [call for call in self.table_calls if call.instance.split == 'test']


def _tune(cell=CELL, full=None, damped=None, **options):
    runner = _StepRunner(full, damped, **options)
    return runner, tuning.tune_group(runner, [cell], max_rounds=1)[0]


def _dev_scores(pairs):
    return [pair['table']['u_acc']['lo'] for pair in pairs]


class TheDampedEntriesTests(SimpleTestCase):

    UNIT = pooling.UNIT

    def _damped(self, *values, **kwargs):
        entries = tuning.pool_cell(pooling._four(*values), pooling.ENGINE)
        return entries, tuning.damped_entries(entries, kwargs.get('unit', self.UNIT))

    def test_an_applied_stat_goes_to_the_geometric_midpoint_of_the_engine_and_the_pooled_value(self):
        entries, damped = self._damped(1.4, 1.6, 1.5, 1.7)
        self.assertAlmostEqual(math.sqrt(1.55), damped['pow']['value'])
        self.assertEqual(('damped', False), (damped['pow']['reason'], damped['pow']['weak']))
        self.assertEqual(entries['pow']['value'], damped['pow']['full'])

    def test_a_stat_below_the_engine_comes_up_to_the_midpoint(self):
        _entries, damped = self._damped(0.5, 0.5, 0.5, 0.5)
        self.assertAlmostEqual(math.sqrt(0.5), damped['pow']['value'])

    def test_a_move_of_less_than_a_unit_at_the_midpoint_is_dropped(self):
        entries, damped = self._damped(*[1.0 + 1.6 / self.UNIT] * 4)
        self.assertEqual(entries['pow']['value'], damped['pow']['full'])
        self.assertEqual((1.0, 'unchanged'), (damped['pow']['value'], damped['pow']['reason']))
        self.assertEqual({}, tuning.applied_ratios(damped))

    def test_a_move_of_a_unit_at_the_midpoint_counts(self):
        _entries, damped = self._damped(*[1.0 + 2.4 / self.UNIT] * 4)
        self.assertEqual('damped', damped['pow']['reason'])
        self.assertEqual(['pow'], sorted(tuning.applied_ratios(damped)))

    def test_a_stat_that_was_not_applied_is_left_as_it_was(self):
        entries, damped = self._damped(1.4, 1.6, 1.5, 1.7)
        self.assertEqual(entries['hp'], damped['hp'])
        weak = tuning.pool_cell(pooling._four(1.2, 1.2, 2.0, 2.0), pooling.ENGINE)
        self.assertEqual(weak, tuning.damped_entries(weak, self.UNIT))

    def test_the_pooled_entries_are_left_as_they_were(self):
        entries = tuning.pool_cell(pooling._four(1.4, 1.6, 1.5, 1.7), pooling.ENGINE)
        before = copy.deepcopy(entries)
        tuning.damped_entries(entries, self.UNIT)
        self.assertEqual(before, entries)

    def test_a_damped_value_lies_between_the_engine_and_the_pooled_one_inside_the_bounds(self):
        for value in (0.3, 0.5, 0.8, 1.3, 2.0, 3.9):
            _entries, damped = self._damped(value, value, value, value)
            with self.subTest(value=value):
                low, high = sorted((1.0, damped['pow']['full']))
                self.assertTrue(low < damped['pow']['value'] < high)
                self.assertTrue(tuning.BOUNDS[0] <= damped['pow']['value'] <= tuning.BOUNDS[1])

    def test_a_duo_goes_to_the_midpoint_of_its_first_share_and_the_second_takes_the_rest(self):
        entries = tuning.pool_cell(pooling._duo_cell(pooling.DUO, [1.1] * 4), pooling.DUO_ENGINE)
        damped = tuning.damped_entries(entries, unit_of(pooling.DUO, 'plain'))
        self.assertAlmostEqual(math.sqrt(1.1), damped['str']['value'])
        self.assertAlmostEqual(2 - math.sqrt(1.1), damped['int']['value'])
        self.assertEqual(['damped', 'damped'], [damped[stat]['reason'] for stat in pooling.DUO])
        self.assertEqual([1.1, 0.9], [round(damped[stat]['full'], 6) for stat in pooling.DUO])
        self.assertAlmostEqual(2.0, damped['str']['value'] + damped['int']['value'])

    def test_a_duo_whose_first_share_moves_less_than_a_unit_at_the_midpoint_keeps_both_at_the_engine(self):
        unit = unit_of(pooling.DUO, 'plain')
        entries = tuning.pool_cell(pooling._duo_cell(pooling.DUO, [1.0 + 1.6 / unit] * 4), pooling.DUO_ENGINE)
        self.assertEqual({'str', 'int'}, {stat for stat in tuning.applied_ratios(entries) if stat in pooling.DUO})
        damped = tuning.damped_entries(entries, unit)
        self.assertEqual([(1.0, 'unchanged'), (1.0, 'unchanged')],
                         [(damped[stat]['value'], damped[stat]['reason']) for stat in pooling.DUO])
        self.assertEqual({}, {stat: value for stat, value in tuning.applied_ratios(damped).items()
                              if stat in pooling.DUO})


class TheDevChecksAreReadOnTheDevPairsAloneTests(SimpleTestCase):

    def _dev(self, **kwargs):
        return [pooling._pair(**kwargs) for _ in range(4)]

    def test_pairs_that_pass_every_check_fail_none(self):
        self.assertIsNone(tuning.dev_failure(self._dev()))

    def test_the_checks_the_dev_pairs_alone_can_fail_are_these_in_this_order(self):
        self.assertEqual(('dev_gain', 'panel_gain', 'loss', 'range', 'mp', 'ceiling'), tuning.DEV_CHECKS)

    def test_fewer_than_the_minimum_of_comparisons_is_no_dev_check(self):
        self.assertEqual('dev_runs', tuning.dev_failure(self._dev()[:3]))
        self.assertEqual('dev_runs', tuning.dev_failure(self._dev()[:3] + [pooling._pair(valid=False)]))
        self.assertNotIn('dev_runs', tuning.DEV_CHECKS)

    def test_each_check_is_named_when_it_fails(self):
        cases = {'dev_gain': [pooling._pair(gain_lo=-0.002)] * 3 + [pooling._pair()],
                 'panel_gain': [pooling._pair(panel_lo=-0.02)] * 3 + [pooling._pair()],
                 'loss': [pooling._pair(gain_lo=-0.02, gain_hi=0.1)] + self._dev()[1:],
                 'range': [pooling._pair(range_delta=-2)] * 3 + [pooling._pair()],
                 'mp': [pooling._pair(mp_delta=1)] + self._dev()[1:],
                 'ceiling': [pooling._pair(engine_share=0.4, table_share=0.9)] + self._dev()[1:]}
        for reason, dev in cases.items():
            with self.subTest(reason=reason):
                self.assertEqual(reason, tuning.dev_failure(dev))

    def test_it_names_the_same_check_the_acceptance_names_when_only_the_dev_pairs_fail(self):
        for dev in ([pooling._pair(gain_lo=-0.002)] * 3 + [pooling._pair()],
                    [pooling._pair(panel_lo=-0.02)] * 3 + [pooling._pair()],
                    [pooling._pair(gain_lo=-0.02, gain_hi=0.1)] + self._dev()[1:],
                    [pooling._pair(range_delta=-2)] * 3 + [pooling._pair()],
                    [pooling._pair(mp_delta=1)] + self._dev()[1:],
                    [pooling._pair(engine_share=0.4, table_share=0.9)] + self._dev()[1:]):
            verdict = pooling._accept(dev=dev)
            with self.subTest(reason=verdict['reason']):
                self.assertEqual(verdict['reason'], tuning.dev_failure(dev))

    def test_the_checks_of_the_test_pair_are_not_among_them(self):
        self.assertIsNone(tuning.dev_failure(self._dev()))
        for test in (pooling._pair(gain_hi=-0.001), pooling._pair(0.1, 0.1, panel_lo=-0.05),
                     pooling._pair(range_delta=-2), pooling._pair(mp_delta=1)):
            self.assertEqual('engine', pooling._accept(test=test)['status'])


class TheFullStepIsTriedAgainAtTheDampedOneTests(SimpleTestCase):

    def test_a_full_step_that_misses_the_dev_gain_ships_at_the_damped_step_when_that_gains(self):
        _runner_, record = _tune(full={'dev': 0.95})
        self.assertEqual(('shipped', None, 'damped'), (record['status'], record['reason'], record['step']))
        entry = record['ratios']['pow']
        self.assertAlmostEqual(DAMPED, entry['value'])
        self.assertEqual('damped', entry['reason'])
        self.assertAlmostEqual(FULL, entry['full'])
        self.assertEqual(['pow'], record['applied'])

    def test_each_check_the_dev_pairs_fail_calls_for_the_damped_step(self):
        for reason, full in (('dev_gain', {'dev': 0.95}), ('panel_gain', {'dev_panel': -0.2}),
                             ('range', {'range': 3}), ('mp', {'mp': 1})):
            with self.subTest(reason=reason):
                _runner_, record = _tune(full=full)
                self.assertEqual(('shipped', 'damped', reason), (record['status'], record['step'],
                                                                 record['fallback']['trigger']))

    def test_the_record_holds_the_dev_and_test_pairs_of_the_chosen_step(self):
        _runner_, record = _tune(full={'dev': 0.95})
        self.assertEqual([1.05] * 4, _dev_scores(record['dev']))
        self.assertEqual(1.05, record['test']['table']['u_acc']['lo'])
        self.assertAlmostEqual(0.05, record['u_acc_gain']['lo'])

    def test_it_records_the_step_chosen_and_both_dev_readings(self):
        _runner_, record = _tune(full={'dev': 0.95})
        fallback = record['fallback']
        self.assertEqual(('dev_gain', 'damped'), (fallback['trigger'], fallback['chosen']))
        self.assertEqual([0.95] * 4, _dev_scores(fallback['full']['dev']))
        self.assertEqual([1.05] * 4, _dev_scores(fallback['damped']['dev']))
        self.assertEqual(('dev_gain', None), (fallback['full']['failure'], fallback['damped']['failure']))
        self.assertAlmostEqual(-0.05, fallback['full']['u_acc_gain']['lo'])
        self.assertAlmostEqual(0.05, fallback['damped']['u_acc_gain']['lo'])
        self.assertEqual({'pow': FULL}, {stat: round(value, 9) for stat, value in fallback['full']['applied'].items()})
        self.assertAlmostEqual(DAMPED, fallback['damped']['applied']['pow'])

    def test_the_damped_dev_solves_keep_the_engine_sides_and_the_recorded_forbids(self):
        plain, _record = _tune()
        runner, record = _tune(full={'dev': 0.95})
        engine_calls = [call for call in runner.calls if call.ratios is None and call.instance.split != 'test']
        plain_engine = [call for call in plain.calls if call.ratios is None and call.instance.split != 'test']
        self.assertEqual(len(plain_engine), len(engine_calls))
        full, damped = runner.dev_table_calls('full'), runner.dev_table_calls('damped')
        self.assertEqual([call.instance.tier for call in full], [call.instance.tier for call in damped])
        self.assertEqual([call.forbid for call in full], [call.forbid for call in damped])
        self.assertEqual(4, len(damped))
        for call in damped:
            self.assertEqual(set(record['forbids'][call.instance.tier]), call.forbid)

    def test_the_damped_pairs_share_the_engine_evaluations_of_the_full_ones(self):
        _runner_, record = _tune(full={'dev': 0.95})
        fallback = record['fallback']
        self.assertEqual([pair['engine'] for pair in fallback['full']['dev']],
                         [pair['engine'] for pair in fallback['damped']['dev']])

    def test_the_test_pair_is_solved_once_and_at_the_step_chosen(self):
        runner, _record = _tune(full={'dev': 0.95})
        self.assertEqual(['damped'], [call.step for call in runner.test_table_calls()])
        self.assertEqual(2, len([call for call in runner.calls if call.instance.split == 'test']))

    def test_the_guarded_door_is_solved_at_the_step_chosen(self):
        cell = tuning.Cell('Iop', ('str',), 'glasscannon', '200')
        runner, record = _tune(cell, full={'dev': 0.95})
        guarded = [call for call in runner.calls if call.guarded and call.ratios is not None]
        self.assertEqual(1, len(guarded))
        self.assertEqual('damped', record['step'])
        self.assertAlmostEqual(record['ratios']['pow']['value'], guarded[0].ratios['pow'])
        self.assertAlmostEqual(record['ratios']['pow']['full'] ** 0.5 * record['ratios']['pow']['engine'] ** 0.5,
                               guarded[0].ratios['pow'])

    def test_a_full_step_that_passes_the_dev_pairs_is_not_tried_again(self):
        runner, record = _tune()
        self.assertEqual([], runner.dev_table_calls('damped'))
        self.assertEqual(('shipped', 'full'), (record['status'], record['step']))
        self.assertIsNone(record.get('fallback'))
        self.assertAlmostEqual(FULL, record['ratios']['pow']['value'])
        self.assertNotIn('full', record['ratios']['pow'])

    def test_a_full_step_that_fails_only_on_the_test_pair_is_not_tried_again(self):
        for full in ({'test': 0.95}, {'test_panel': -0.2}, {'test_panel': 0.0, 'test': 1.0}):
            with self.subTest(full=full):
                runner, record = _tune(full=full)
                self.assertEqual([], runner.dev_table_calls('damped'))
                self.assertEqual(('engine', 'full'), (record['status'], record['step']))

    def test_a_cell_with_no_usable_dev_pair_is_not_tried_again(self):
        runner, record = _tune(unproven=2)
        self.assertEqual('dev_runs', record['reason'])
        self.assertEqual([], runner.dev_table_calls('damped'))
        self.assertIsNone(record.get('fallback'))

    def test_a_cell_where_nothing_is_applied_has_no_step_to_damp(self):
        runner, record = _tune(factors={})
        self.assertEqual('no_change', record['reason'])
        self.assertEqual([], runner.table_calls)

    def test_neither_step_passing_keeps_the_full_one_and_its_reason(self):
        _runner_, record = _tune(full={'dev': 0.95}, damped={'dev': 0.97})
        self.assertEqual(('engine', 'dev_gain', 'full'), (record['status'], record['reason'], record['step']))
        self.assertAlmostEqual(FULL, record['ratios']['pow']['value'])
        self.assertEqual([0.95] * 4, _dev_scores(record['dev']))
        self.assertEqual(('dev_gain', 'full', 'dev_gain'), (record['fallback']['trigger'], record['fallback']['chosen'],
                                                            record['fallback']['damped']['failure']))

    def test_a_damped_step_that_loses_range_is_not_chosen(self):
        _runner_, record = _tune(full={'dev': 0.95}, damped={'range': 3})
        self.assertEqual(('engine', 'full', 'range'), (record['status'], record['step'],
                                                      record['fallback']['damped']['failure']))

    def test_the_step_is_chosen_without_the_test_pair(self):
        runner, record = _tune(full={'dev': 0.95}, damped={'test': 0.95, 'test_panel': 0.05})
        self.assertEqual(('engine', 'test_gain', 'damped'), (record['status'], record['reason'], record['step']))
        self.assertEqual(['damped'], [call.step for call in runner.test_table_calls()])

    def test_a_step_whose_test_pair_would_have_passed_is_not_preferred(self):
        runner, record = _tune(full={'dev': 1.04, 'range': 3, 'test': 1.2}, damped={'dev': 1.02, 'test': 0.9})
        self.assertEqual('damped', record['step'])
        self.assertEqual(['damped'], [call.step for call in runner.test_table_calls()])

    def test_a_move_that_the_midpoint_drops_leaves_no_damped_step(self):
        factors = {tier: 1.02 for tier in doors.FACTORS}
        runner, record = _tune(factors=factors, full={'dev': 0.95})
        self.assertEqual(['pow'], record['applied'])
        self.assertEqual(('engine', 'dev_gain', 'full'), (record['status'], record['reason'], record['step']))
        self.assertEqual([], runner.dev_table_calls('damped'))
        self.assertEqual(('dev_gain', 'full', None), (record['fallback']['trigger'], record['fallback']['chosen'],
                                                     record['fallback']['damped']))

    def test_a_cell_held_for_its_unverified_rows_is_not_tried_again(self):
        runner, record = _tune(doors.ECAFLIP, factors=doors.RISING, full={'dev': 0.95})
        self.assertEqual(('engine', 'dev_gain'), (record['status'], record['reason']))
        self.assertEqual(4, len(runner.dev_table_calls()))
        self.assertIsNone(record.get('fallback'))

    def test_the_numeraire_is_read_on_the_step_chosen(self):
        _runner_, record = _tune(full={'dev': 0.95}, item_sums={'pow': 100}, moves=None)
        self.assertAlmostEqual(DAMPED * 100, record['numeraire']['table_value'])

    def test_the_cells_the_damped_step_clamps_are_read_on_the_step_chosen(self):
        _runner_, record = _tune(full={'dev': 0.95})
        self.assertEqual([], record['clamped'])


class ADampedCellShipsAsTheTableWritesItTests(SimpleTestCase):

    def test_the_table_carries_the_damped_value_and_the_step(self):
        _runner_, record = _tune(full={'dev': 0.95})
        with tempfile.TemporaryDirectory() as parent:
            folder = os.path.join(parent, 'run-3')
            os.makedirs(folder)
            tuning.write_record(folder, record)
            with open(os.path.join(folder, 'run.json'), 'w', encoding='utf-8') as handle:
                json.dump({'solver': {}}, handle)
            table = tuning.ship_table(folder, 'dofus3')
        cell = table['cells']['Iop']['str']['plain']['200']
        self.assertEqual(('shipped', 'damped'), (cell['status'], cell['step']))
        self.assertAlmostEqual(DAMPED, cell['ratios']['pow']['value'])
        self.assertAlmostEqual(FULL, cell['ratios']['pow']['full'])
        self.assertNotIn('fallback', cell)

    def test_the_gate_reads_the_chosen_steps_gain_and_ceiling(self):
        _runner_, record = _tune(full={'dev': 0.95})
        self.assertTrue(tuning._cell_gained(record))
        self.assertFalse(tuning._ceiling_breached(record))
