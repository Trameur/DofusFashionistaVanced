# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A stat that took the value of its class, element count and scenario in place of its own builds' records that it
did, and which group it was, whatever the bounds, the unit or the damped step did to the value afterwards."""
import json

from django.test import SimpleTestCase

from chardata import tests_a_weight_cell_ships_only_when_both_folds_agree as pooling
from chardata import weight_tuning as tuning
from chardata.weight_table import unit_of

ENGINE = pooling.ENGINE
UNIT = pooling.UNIT
GROUP = ['Iop', 1, 'plain']


def _disagreeing_cell():
    return pooling._four(1.2, 1.2, 2.0, 2.0)


def _siblings(value):
    return [pooling._run(split, which, pow=value) for split, which in pooling.FOLDS] * 2


def _pooled(value=1.5):
    cell = _disagreeing_cell()
    return tuning.pool_cell(cell, ENGINE, cell + _siblings(value))


class AStatThatTookTheGroupValueIsFlaggedTests(SimpleTestCase):

    def test_the_entry_says_it_was_pooled_and_over_which_group(self):
        entry = _pooled()['pow']
        self.assertEqual((False, 'pooled', 1.5), (entry['weak'], entry['reason'], entry['value']))
        self.assertIs(True, entry['pooled'])
        self.assertEqual(GROUP, entry['group'])

    def test_a_group_is_a_class_a_number_of_elements_and_a_scenario(self):
        cell = pooling._duo_cell(pooling.DUO, [0.95, 0.95, 1.1, 1.1])
        entries = tuning.pool_cell(cell, pooling.DUO_ENGINE, cell + pooling._duo_cell(('str', 'cha'), [1.06] * 4))
        self.assertEqual(['Iop', 2, 'plain'], entries['str']['group'])

    def test_a_stat_that_used_its_own_median_is_not_flagged(self):
        entry = pooling._pow(pooling._four(1.4, 1.6, 1.5, 1.7))
        self.assertNotIn('pooled', entry)
        self.assertNotIn('group', entry)

    def test_a_stat_the_group_could_not_rescue_is_not_flagged(self):
        cell = _disagreeing_cell()
        entry = pooling._pow(cell, group=cell + pooling._four(1.1, 1.1, 2.2, 2.2))
        self.assertEqual((True, 'folds'), (entry['weak'], entry['reason']))
        self.assertNotIn('pooled', entry)
        self.assertNotIn('group', entry)

    def test_a_stat_with_no_group_to_read_is_not_flagged(self):
        entry = pooling._pow(_disagreeing_cell())
        self.assertNotIn('pooled', entry)

    def test_the_flag_changes_no_value(self):
        entry = _pooled()['pow']
        plain = {name: field for name, field in entry.items() if name not in ('pooled', 'group')}
        self.assertEqual({'builds', 'n', 'engine', 'folds', 'weak', 'spread', 'value', 'reason'}, set(plain))
        self.assertEqual(1.5, plain['value'])

    def test_the_group_comes_back_from_a_json_file_as_written(self):
        entry = json.loads(json.dumps(_pooled()['pow']))
        self.assertEqual((True, GROUP), (entry['pooled'], entry['group']))


class TheFlagSurvivesWhatHappensToThePooledValueTests(SimpleTestCase):

    def test_a_value_the_bounds_clamp_keeps_it(self):
        entry = _pooled(6.0)['pow']
        self.assertEqual(('bound', 4.0), (entry['reason'], entry['value']))
        self.assertEqual((True, GROUP), (entry['pooled'], entry['group']))

    def test_a_move_under_a_unit_of_weight_keeps_it(self):
        entry = _pooled(1.0 + 0.4 / UNIT)['pow']
        self.assertEqual(('pooled', ENGINE['pow']), (entry['reason'], entry['value']))
        self.assertEqual((True, GROUP), (entry['pooled'], entry['group']))

    def test_the_damped_entry_keeps_it_beside_the_full_value(self):
        entries = _pooled(4.0)
        damped = tuning.damped_entries(entries, UNIT)['pow']
        self.assertEqual(('damped', 4.0), (damped['reason'], damped['full']))
        self.assertAlmostEqual(2.0, damped['value'])
        self.assertEqual((True, GROUP), (damped['pooled'], damped['group']))

    def test_the_damped_step_does_not_change_the_pooled_entry(self):
        entries = _pooled(4.0)
        tuning.damped_entries(entries, UNIT)
        self.assertEqual(('pooled', True), (entries['pow']['reason'], entries['pow']['pooled']))

    def test_a_duos_second_share_follows_the_first_in_both_steps(self):
        cell = pooling._duo_cell(pooling.DUO, [0.95, 0.95, 1.1, 1.1])
        entries = tuning.pool_cell(cell, pooling.DUO_ENGINE, cell + pooling._duo_cell(('str', 'cha'), [1.3] * 4))
        for step in (entries, tuning.damped_entries(entries, unit_of(pooling.DUO, 'plain'))):
            for stat in pooling.DUO:
                with self.subTest(stat=stat):
                    self.assertEqual((True, ['Iop', 2, 'plain']), (step[stat]['pooled'], step[stat]['group']))

    def test_a_second_share_that_follows_a_weak_first_one_is_not_flagged(self):
        cell = pooling._duo_cell(pooling.DUO, [0.95, 0.95, 1.1, 1.1])
        entries = tuning.pool_cell(cell, pooling.DUO_ENGINE)
        self.assertEqual([True, True], [entries[stat]['weak'] for stat in pooling.DUO])
        for stat in pooling.DUO:
            self.assertNotIn('pooled', entries[stat])
            self.assertNotIn('group', entries[stat])
