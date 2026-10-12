# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The factor between the engine's value of its high set and the table's is recorded, and no price is rescaled by it."""
import copy
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.tests_the_weight_table_carries_its_measurement import entry_flaws

ENGINE = {'pow': 1.0, 'perspedam': 1.0, 'airresper': 0.5, 'hp': 0.2}
SUMS = {'pow': 200, 'perspedam': 30, 'airresper': 40, 'hp': 600}
ENGINE_VALUE = 1.0 * 200 + 1.0 * 30 + 0.5 * 40 + 0.2 * 600
TABLE_VALUE = 1.0 * 200 + 1.5 * 30 + 0.9 * 40 + 0.2 * 600


def _entry(stat, value, **more):
    return dict({'engine': ENGINE[stat], 'value': value, 'weak': False}, **more)


def _entries(**pooled):
    return {stat: _entry(stat, pooled.get(stat, ENGINE[stat])) for stat in ENGINE}


def _rise():
    """A cell where the resistance and the percent spell damage rise."""
    return _entries(perspedam=1.5, airresper=0.9)


class TheFactorIsOnlyReadTests(SimpleTestCase):

    def test_the_factor_is_the_engines_value_over_the_tables(self):
        record = tuning.numeraire_factor(_rise(), ENGINE, SUMS)
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, record['factor'])
        self.assertLess(record['factor'], 1.0)
        self.assertEqual((ENGINE_VALUE, TABLE_VALUE), (record['engine_value'], record['table_value']))

    def test_a_table_set_worth_less_gives_a_factor_above_one_and_changes_nothing(self):
        entries = _entries(pow=0.5, perspedam=0.5)
        before = copy.deepcopy(entries)
        record = tuning.numeraire_factor(entries, ENGINE, SUMS)
        self.assertGreater(record['factor'], 1.0)
        self.assertEqual(before, entries)

    def test_no_entry_is_changed(self):
        entries = _rise()
        entries['pow']['reason'] = 'unchanged'
        before = copy.deepcopy(entries)
        tuning.numeraire_factor(entries, ENGINE, SUMS)
        self.assertEqual(before, entries)
        self.assertEqual(before['pow']['value'], entries['pow']['value'])
        for entry in entries.values():
            self.assertNotIn('pooled', entry)

    def test_the_record_names_the_owned_stats(self):
        record = tuning.numeraire_factor(_rise(), ENGINE, SUMS)
        self.assertEqual(['airresper', 'hp', 'perspedam', 'pow'], record['owned'])


class TheStatsTheTableDoesNotOwnAreLeftOutTests(SimpleTestCase):

    def test_a_weak_stat_is_left_out_of_the_value(self):
        entries = dict(_rise(), ap={'engine': 184.0, 'value': 184.0, 'weak': True, 'reason': 'held'})
        record = tuning.numeraire_factor(entries, dict(ENGINE, ap=184.0), dict(SUMS, ap=12))
        self.assertNotIn('ap', record['owned'])
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, record['factor'])

    def test_a_stat_the_cell_weighs_at_zero_adds_nothing(self):
        engine = dict(ENGINE, earthdam=0.0)
        entries = dict(_rise(), earthdam={'engine': 0.0, 'value': 0.0, 'weak': False})
        record = tuning.numeraire_factor(entries, engine, dict(SUMS, earthdam=50))
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, record['factor'])

    def test_a_share_is_no_price(self):
        entries = dict(_rise(), str={'engine': 1.0, 'value': 1.2, 'weak': False})
        record = tuning.numeraire_factor(entries, dict(ENGINE, str=1.0), dict(SUMS, str=300))
        self.assertNotIn('str', record['owned'])
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, record['factor'])


class NoFactorIsDrawnWithoutAReasonTests(SimpleTestCase):

    def test_a_cell_that_applies_nothing_has_a_factor_of_one(self):
        record = tuning.numeraire_factor(_entries(), ENGINE, SUMS)
        self.assertEqual((1.0, None, None), (record['factor'], record['engine_value'], record['table_value']))

    def test_a_set_that_is_not_known_has_a_factor_of_one(self):
        self.assertEqual(1.0, tuning.numeraire_factor(_rise(), ENGINE, {})['factor'])

    def test_a_value_that_is_not_positive_has_a_factor_of_one(self):
        record = tuning.numeraire_factor(_rise(), ENGINE, {'pow': 0, 'hp': 0})
        self.assertEqual(1.0, record['factor'])


class APooledEntryKeepsItsMeasurementTests(SimpleTestCase):

    def test_the_audit_of_a_shipped_table_accepts_the_pooled_entries(self):
        plan = {split: [tier for tier, planned in tuning.INSTANCE_PLAN if planned == split]
                for split in tuning.DEV_SPLITS}
        runs = []
        for split in tuning.DEV_SPLITS:
            for which in range(2):
                instance = tuning.Instance('Iop', ('str',), 'plain', '200', plan[split][which], split)
                run = tuning.TuneRun(instance)
                run.engine_ratios = dict(ENGINE)
                read = tuning.Read({}, set(), 1000.0, 5000.0, 2.0)
                ratios = {'pow': 1.0, 'perspedam': 1.5 + 0.05 * which, 'airresper': 0.9, 'hp': 0.2}
                run.rounds = [tuning.Round(0, ratios, SimpleNamespace(proven=True), read, 1.0, {})]
                run.best = 0
                runs.append(run)
        stamp = {'data': '3.7', 'date': '2026-10-12', 'source': 'tune/run-1'}
        entries = tuning.pool_cell(runs, ENGINE, stamp=stamp)
        self.assertAlmostEqual(1.525, entries['perspedam']['value'])
        for stat, entry in entries.items():
            with self.subTest(stat=stat):
                self.assertEqual([], entry_flaws(dict(entry, data='3.7')))
