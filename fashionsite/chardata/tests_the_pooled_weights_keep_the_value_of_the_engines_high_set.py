# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The owned weights are rescaled by one factor, so that the engine's high set is worth the same under the table."""
from types import SimpleNamespace

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.tests_the_weight_table_carries_its_measurement import entry_flaws
from chardata.weight_table import unit_of

ENGINE = {'pow': 1.0, 'perspedam': 1.0, 'airresper': 0.5, 'hp': 0.2}
SUMS = {'pow': 200, 'perspedam': 30, 'airresper': 40, 'hp': 600}
#: the weight of one played point, large enough that every move below counts
UNIT = 100.0
ENGINE_VALUE = 1.0 * 200 + 1.0 * 30 + 0.5 * 40 + 0.2 * 600
TABLE_VALUE = 1.0 * 200 + 1.5 * 30 + 0.9 * 40 + 0.2 * 600


def _entry(stat, value, **more):
    return dict({'engine': ENGINE[stat], 'value': value, 'weak': False}, **more)


def _entries(**pooled):
    return {stat: _entry(stat, pooled.get(stat, ENGINE[stat])) for stat in ENGINE}


def _rise():
    """A cell where the resistance and the percent spell damage rise."""
    return _entries(perspedam=1.5, airresper=0.9)


def _worth(entries, stats=None):
    return sum(entries[stat]['value'] * SUMS[stat] for stat in (stats or entries))


class TheEngineSetKeepsItsValueTests(SimpleTestCase):

    def test_the_factor_is_the_engines_value_over_the_tables(self):
        record = tuning.rescale_to_numeraire(_rise(), ENGINE, SUMS, UNIT)
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, record['factor'])
        self.assertLess(record['factor'], 1.0)
        self.assertEqual((ENGINE_VALUE, TABLE_VALUE), (record['engine_value'], record['table_value']))

    def test_the_engine_high_set_is_worth_the_same_under_the_rescaled_weights(self):
        entries = _rise()
        tuning.rescale_to_numeraire(entries, ENGINE, SUMS, UNIT)
        self.assertAlmostEqual(ENGINE_VALUE, _worth(entries))

    def test_the_prices_among_the_owned_stats_stay_as_they_were_pooled(self):
        entries = _rise()
        tuning.rescale_to_numeraire(entries, ENGINE, SUMS, UNIT)
        for first, second in (('perspedam', 'airresper'), ('airresper', 'hp'), ('pow', 'perspedam')):
            with self.subTest(first=first, second=second):
                self.assertAlmostEqual(entries[first]['pooled'] / entries[second]['pooled'],
                                       entries[first]['value'] / entries[second]['value'])

    def test_the_pooled_value_is_kept_beside_the_rescaled_one(self):
        entries = _rise()
        tuning.rescale_to_numeraire(entries, ENGINE, SUMS, UNIT)
        self.assertEqual((1.5, 0.9), (entries['perspedam']['pooled'], entries['airresper']['pooled']))
        self.assertAlmostEqual(1.5 * ENGINE_VALUE / TABLE_VALUE, entries['perspedam']['value'])

    def test_a_stat_the_pooling_left_at_the_engine_moves_with_the_others(self):
        entries = _rise()
        entries['pow']['reason'] = 'unchanged'
        tuning.rescale_to_numeraire(entries, ENGINE, SUMS, UNIT)
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, entries['pow']['value'])
        self.assertNotIn('reason', entries['pow'])
        self.assertIn('pow', tuning.applied_ratios(entries))

    def test_the_record_names_the_owned_stats(self):
        record = tuning.rescale_to_numeraire(_rise(), ENGINE, SUMS, UNIT)
        self.assertEqual(['airresper', 'hp', 'perspedam', 'pow'], record['owned'])


class TheStatsTheTableDoesNotOwnStayTests(SimpleTestCase):

    def test_a_weak_stat_stays_at_the_engine_and_is_left_out_of_the_value(self):
        entries = dict(_rise(), ap={'engine': 184.0, 'value': 184.0, 'weak': True, 'reason': 'held'})
        record = tuning.rescale_to_numeraire(entries, dict(ENGINE, ap=184.0), dict(SUMS, ap=12), UNIT)
        self.assertEqual(184.0, entries['ap']['value'])
        self.assertNotIn('pooled', entries['ap'])
        self.assertNotIn('ap', record['owned'])
        self.assertAlmostEqual(ENGINE_VALUE / TABLE_VALUE, record['factor'])

    def test_a_stat_the_cell_weighs_at_zero_stays_at_zero(self):
        engine = dict(ENGINE, earthdam=0.0)
        entries = dict(_rise(), earthdam={'engine': 0.0, 'value': 0.0, 'weak': False})
        tuning.rescale_to_numeraire(entries, engine, dict(SUMS, earthdam=50), UNIT)
        self.assertEqual(0.0, entries['earthdam']['value'])

    def test_a_share_is_no_price(self):
        entries = dict(_rise(), str={'engine': 1.0, 'value': 1.2, 'weak': False})
        record = tuning.rescale_to_numeraire(entries, dict(ENGINE, str=1.0), dict(SUMS, str=300), UNIT)
        self.assertEqual(1.2, entries['str']['value'])
        self.assertNotIn('str', record['owned'])


class NothingIsRescaledWithoutAReasonTests(SimpleTestCase):

    def test_a_cell_that_applies_nothing_keeps_its_entries_and_a_factor_of_one(self):
        entries = _entries()
        record = tuning.rescale_to_numeraire(entries, ENGINE, SUMS, UNIT)
        self.assertEqual(1.0, record['factor'])
        self.assertEqual(_entries(), entries)

    def test_a_set_that_is_not_known_leaves_the_pooled_weights(self):
        entries = _rise()
        self.assertEqual(1.0, tuning.rescale_to_numeraire(entries, ENGINE, {}, UNIT)['factor'])
        self.assertEqual(_rise(), entries)

    def test_a_value_that_is_not_positive_leaves_the_pooled_weights(self):
        entries = _rise()
        record = tuning.rescale_to_numeraire(entries, ENGINE, {'pow': 0, 'hp': 0}, UNIT)
        self.assertEqual(1.0, record['factor'])
        self.assertEqual(_rise(), entries)

    def test_a_change_under_one_unit_of_weight_is_the_engine_value(self):
        entries = _rise()
        tuning.rescale_to_numeraire(entries, ENGINE, SUMS, 3.0)
        self.assertEqual(1.0, entries['pow']['value'])
        self.assertEqual('unchanged', entries['pow']['reason'])
        self.assertEqual(1.5 * ENGINE_VALUE / TABLE_VALUE, entries['perspedam']['value'])


class ALimitStillStopsTheRiseTests(SimpleTestCase):

    def test_a_stat_pushed_up_by_the_factor_stops_at_its_highest_limit(self):
        engine = {'pow': 1.0, 'hp': 0.2}
        entries = {'pow': {'engine': 1.0, 'value': 0.9, 'weak': False, 'limits': [0.25, 1.0]},
                   'hp': {'engine': 0.2, 'value': 0.1, 'weak': False}}
        record = tuning.rescale_to_numeraire(entries, engine, {'pow': 100, 'hp': 100}, UNIT)
        self.assertAlmostEqual(1.2, record['factor'])
        self.assertEqual((1.0, 'bound'), (entries['pow']['value'], entries['pow']['reason']))
        self.assertAlmostEqual(0.12, entries['hp']['value'])


class ARescaledEntryKeepsItsMeasurementTests(SimpleTestCase):

    def test_the_audit_of_a_shipped_table_accepts_the_rescaled_entries(self):
        unit = unit_of(('str',), 'plain')
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
        tuning.rescale_to_numeraire(entries, ENGINE, SUMS, unit)
        self.assertIn('pooled', entries['perspedam'])
        for stat, entry in entries.items():
            with self.subTest(stat=stat):
                self.assertEqual([], entry_flaws(dict(entry, data='3.7')))
