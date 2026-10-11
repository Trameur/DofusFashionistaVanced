# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A shipped weight table carries the measurement behind each ratio and the digests of the engine and the split."""
import copy
import json
import os
import statistics
import tempfile
import warnings
from datetime import date

from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.data_versions import current_data_version
from chardata.weight_table import (BANDS, DIRECTORY, SCENARIOS, SHARE_STATS, TABLE_STATS, element_key, engine_digest,
                                   grid_element_sets)
from fashionistapulp.dofus_constants import CHARACTER_CLASSES

VERSION = 'dofus3'
PATH = os.path.join(DIRECTORY, '%s.json' % VERSION)
MEASUREMENT = {'value', 'builds', 'n', 'spread', 'data', 'date', 'source', 'weak', 'folds', 'engine'}
REASONS = {None, 'bound', 'pooled', 'unchanged', 'folds', 'switch', 'no_runs'}
WEAK_REASONS = {'folds', 'switch', 'no_runs'}
HEADER = {'generated', 'game_version', 'generator_version', 'engine_digest', 'split_digest', 'game_data_sha1',
          'data_version', 'repository_head', 'solver', 'lambda', 'run_sha1', 'created'}
CELL_KEYS = {class_name + '/' + element_key(played) + '/' + scenario + '/' + BANDS[0]
             for class_name in CHARACTER_CLASSES for played in grid_element_sets() for scenario in SCENARIOS}
TOLERANCE = 1e-9
ENGINE = 2.0
BUILDS = {'a': 2.0, 'b': 2.4, 'c': 2.2, 'd': 2.6}


def _close(first, second):
    return abs(first - second) <= TOLERANCE * max(1.0, abs(first), abs(second))


def entry_flaws(entry, applied_needs_runs=True):
    """What is wrong with the measurement behind one ratio, [] when it is whole."""
    if not isinstance(entry, dict) or not MEASUREMENT <= set(entry) or not set(entry) <= MEASUREMENT | {'reason'}:
        return ['not a measurement']
    flaws = []
    builds = list(entry['builds'].values()) if isinstance(entry['builds'], dict) else []
    reason = entry.get('reason')
    if reason not in REASONS:
        flaws.append('reason')
    if entry['n'] != len(builds):
        flaws.append('n')
    if builds and (len(entry['spread'] or ()) != 2 or not _close(entry['spread'][0], min(builds))
                   or not _close(entry['spread'][1], max(builds))):
        flaws.append('spread')
    if not isinstance(entry['folds'], list) or len(entry['folds']) != 2:
        flaws.append('folds')
    try:
        date.fromisoformat(entry['date'])
    except (TypeError, ValueError):
        flaws.append('date')
    if not str(entry['source']).startswith('tune/'):
        flaws.append('source')
    if not isinstance(entry['weak'], bool) or not isinstance(entry['value'], (int, float)):
        return flaws + ['types']
    engine, value = entry['engine'], entry['value']
    if entry['weak']:
        if reason not in WEAK_REASONS or not _close(value, engine):
            flaws.append('weak')
        return flaws
    if reason in WEAK_REASONS:
        flaws.append('weak')
    low, high = tuning.BOUNDS[0] * engine, tuning.BOUNDS[1] * engine
    if value < low - TOLERANCE or value > high + TOLERANCE:
        flaws.append('bounds')
    if reason is None and builds and not _close(value, statistics.median(builds)):
        flaws.append('median')
    if reason == 'bound' and not (_close(value, low) or _close(value, high)):
        flaws.append('bound')
    if reason == 'unchanged' and not _close(value, engine):
        flaws.append('unchanged')
    if applied_needs_runs and not _close(value, engine) and entry['n'] < tuning.MIN_DEV_RUNS:
        flaws.append('runs')
    return flaws


def header_flaws(header):
    """The mismatches that fail a table, and the data version one that only warns."""
    if not isinstance(header, dict) or not HEADER <= set(header):
        return ['header'], []
    instances = [instance for cell in tuning.lot1_cells() for instance in tuning.instances_for(cell)]
    flaws = [name for name, current in (('generator_version', tuning.GENERATOR_VERSION),
                                        ('engine_digest', engine_digest(VERSION)),
                                        ('split_digest', tuning.split_digest(instances)))
             if header[name] != current]
    if header['game_version'] != VERSION:
        flaws.append('game_version')
    warned = [] if header['data_version'] == current_data_version(VERSION) else ['data_version']
    return flaws, warned


def table_flaws(table):
    """[(where, flaw)] of a whole table: its header, its cells and the entries of its shipped cells."""
    flaws, warned = header_flaws(table.get('header'))
    out = [('header', flaw) for flaw in flaws]
    for warning in warned:
        warnings.warn('the weight table was tuned on another %s' % warning)
    for char_class, by_key in (table.get('cells') or {}).items():
        for key, by_scenario in by_key.items():
            for scenario, by_band in by_scenario.items():
                for band, cell in by_band.items():
                    where = '/'.join((char_class, key, scenario, band))
                    if where not in CELL_KEYS:
                        out.append((where, 'not a grid cell'))
                        continue
                    if cell.get('status') not in ('shipped', 'engine'):
                        out.append((where, 'status'))
                    if cell.get('status') == 'shipped':
                        out.extend(_shipped_flaws(where, cell))
                    for stat, entry in (cell.get('ratios') or {}).items():
                        if stat not in TABLE_STATS + SHARE_STATS:
                            out.append((where + '/' + stat, 'not a read stat'))
                        out.extend((where + '/' + stat, flaw) for flaw in entry_flaws(entry))
    return out


def _shipped_flaws(where, cell):
    flaws = []
    if cell.get('reason') is not None:
        flaws.append('reason')
    if (cell.get('blind_share') or 0) < tuning.BLIND_SHARE:
        flaws.append('blind')
    for name in ('u_acc_gain', 'test_gain'):
        gains = cell.get(name) or {}
        if set(gains) != {'lo', 'hi'} or any(gain is None or gain <= 0 for gain in gains.values()):
            flaws.append(name)
    entries = (cell.get('ratios') or {}).values()
    if not any(not entry.get('weak') and entry['value'] != entry['engine'] for entry in entries):
        flaws.append('nothing applied')
    return [(where, flaw) for flaw in flaws]


def _entry(**changes):
    builds = changes.pop('builds', dict(BUILDS))
    entry = {'value': statistics.median(builds.values()), 'builds': builds, 'n': len(builds),
             'spread': [min(builds.values()), max(builds.values())], 'engine': ENGINE, 'folds': [2.1, 2.5],
             'weak': False, 'data': current_data_version(VERSION), 'date': '2026-10-11', 'source': 'tune/run-1'}
    entry.update(changes)
    return entry


def _record(cell, ratios, **fields):
    return dict({'cell': cell, 'status': 'shipped', 'reason': None, 'blind_share': 0.9, 'rounds': 2,
                 'converged': True, 'u_acc_gain': {'lo': 0.02, 'hi': 0.03}, 'test_gain': {'lo': 0.01, 'hi': 0.02},
                 'pow_share': {'engine': 0.5, 'table': 0.55}, 'clamped': [], 'notes': [], 'ratios': ratios,
                 'applied': sorted(ratios)}, **fields)


class AWholeMeasurementPassesTests(SimpleTestCase):

    def test_a_pooled_median_of_four_builds_is_whole(self):
        self.assertEqual([], entry_flaws(_entry()))

    def test_the_median_is_the_value(self):
        self.assertEqual(2.3, _entry()['value'])

    def test_a_weak_entry_keeps_the_engine_value_and_names_why(self):
        for reason in sorted(WEAK_REASONS):
            with self.subTest(reason=reason):
                self.assertEqual([], entry_flaws(_entry(weak=True, value=ENGINE, reason=reason)))

    def test_a_value_clamped_to_a_bound_names_the_bound(self):
        self.assertEqual([], entry_flaws(_entry(value=tuning.BOUNDS[1] * ENGINE, reason='bound')))
        self.assertEqual([], entry_flaws(_entry(value=tuning.BOUNDS[0] * ENGINE, reason='bound')))

    def test_a_value_left_at_the_engine_by_rounding_names_it(self):
        self.assertEqual([], entry_flaws(_entry(value=ENGINE, reason='unchanged', builds={'a': 2.0, 'b': 2.0,
                                                                                         'c': 2.0, 'd': 2.0})))

    def test_a_value_pooled_over_the_siblings_may_differ_from_the_median_of_its_own_builds(self):
        self.assertEqual([], entry_flaws(_entry(value=3.1, reason='pooled')))

    def test_a_zero_engine_stat_stays_zero(self):
        self.assertEqual([], entry_flaws(_entry(engine=0.0, value=0.0, reason='unchanged', builds={'a': 0.0, 'b': 0.0,
                                                                                                'c': 0.0, 'd': 0.0})))


class EveryDefectOfAMeasurementIsFlaggedTests(SimpleTestCase):

    def _flags(self, **changes):
        return entry_flaws(_entry(**changes))

    def test_a_count_that_is_not_the_number_of_builds(self):
        self.assertIn('n', self._flags(n=5))

    def test_a_value_that_is_not_the_median(self):
        self.assertIn('median', self._flags(value=2.9))

    def test_a_spread_that_is_not_the_extremes(self):
        self.assertIn('spread', self._flags(spread=[2.0, 2.5]))

    def test_a_value_outside_the_bounds(self):
        self.assertIn('bounds', self._flags(value=tuning.BOUNDS[1] * ENGINE * 1.01, reason='pooled'))
        self.assertIn('bounds', self._flags(value=tuning.BOUNDS[0] * ENGINE * 0.99, reason='pooled'))

    def test_a_clamp_that_is_not_on_a_bound(self):
        self.assertIn('bound', self._flags(value=3.0, reason='bound'))

    def test_a_weak_entry_that_moved_or_names_no_reason(self):
        self.assertIn('weak', self._flags(weak=True, value=3.0, reason='folds'))
        self.assertIn('weak', self._flags(weak=True, value=ENGINE))
        self.assertIn('weak', self._flags(weak=True, value=ENGINE, reason='pooled'))

    def test_a_strong_entry_that_names_a_weak_reason(self):
        self.assertIn('weak', self._flags(reason='folds'))

    def test_an_applied_value_from_fewer_runs_than_the_minimum(self):
        self.assertIn('runs', self._flags(builds={'a': 2.0, 'b': 2.4, 'c': 2.2}))
        self.assertNotIn('runs', self._flags(builds={'a': 2.0, 'b': 2.0, 'c': 2.0}, value=ENGINE, reason='unchanged'))

    def test_a_missing_field_or_a_stray_one(self):
        for field in MEASUREMENT:
            entry = _entry()
            del entry[field]
            with self.subTest(missing=field):
                self.assertEqual(['not a measurement'], entry_flaws(entry))
        self.assertEqual(['not a measurement'], entry_flaws(_entry(extra=1)))
        self.assertEqual(['not a measurement'], entry_flaws(None))

    def test_a_date_that_is_not_a_date_and_a_source_that_is_not_a_run(self):
        self.assertIn('date', self._flags(date='soon'))
        self.assertIn('source', self._flags(source='bench/run'))
        self.assertIn('source', self._flags(source='tune'))

    def test_a_reason_the_pooling_never_gives(self):
        self.assertIn('reason', self._flags(reason='because'))


class ATableShippedFromARunCarriesItsDigestsTests(SimpleTestCase):

    def _run_folder(self, folder):
        ratios = {'pow': dict(_entry(), source='tune'), 'hp': dict(_entry(), source='tune')}
        tuning.write_record(folder, _record('Iop/str/plain/200', ratios))
        tuning.write_record(folder, dict(_record('Cra/agi/glasscannon/200', {}), status='engine', reason='blind'))
        return os.path.basename(os.path.normpath(folder))

    def _shipped(self):
        with tempfile.TemporaryDirectory() as parent:
            folder = os.path.join(parent, 'run-7')
            os.makedirs(folder)
            self._run_folder(folder)
            return tuning.ship_table(folder, VERSION)

    def test_the_header_holds_the_digests_the_checks_read(self):
        table = self._shipped()
        self.assertEqual(HEADER, set(table['header']))
        self.assertEqual(tuning.GENERATOR_VERSION, table['header']['generator_version'])
        self.assertEqual(engine_digest(VERSION), table['header']['engine_digest'])
        self.assertEqual(VERSION, table['header']['game_version'])
        self.assertEqual({'plain', 'glasscannon', 'tank'}, set(table['header']['lambda']))

    def test_the_shipped_table_passes_every_check(self):
        self.assertEqual([], table_flaws(self._shipped()))

    def _shipped_with(self, meta=None, **options):
        with tempfile.TemporaryDirectory() as parent:
            folder = os.path.join(parent, 'run-7')
            os.makedirs(folder)
            self._run_folder(folder)
            if meta is not None:
                with open(os.path.join(folder, 'run.json'), 'w', encoding='utf-8') as handle:
                    json.dump(meta, handle)
            return tuning.ship_table(folder, VERSION, **options)

    def test_the_header_names_the_solver_the_run_was_made_on(self):
        solver = {'name': 'PULP_CBC_CMD', 'time_limit': 77, 'threads': None}
        self.assertEqual(solver, self._shipped_with({'solver': solver})['header']['solver'])

    def test_a_solver_given_to_the_ship_wins_over_the_one_of_the_run(self):
        table = self._shipped_with({'solver': {'time_limit': 77}}, solver={'time_limit': 120})
        self.assertEqual({'time_limit': 120}, table['header']['solver'])

    def test_a_run_that_kept_no_solver_ships_an_empty_one(self):
        self.assertEqual({}, self._shipped_with({})['header']['solver'])
        self.assertEqual({}, self._shipped()['header']['solver'])

    def test_the_solver_facts_hold_the_limit_and_the_threads(self):
        facts = tuning.solver_facts(61)
        self.assertEqual({'name', 'time_limit', 'threads'}, set(facts))
        self.assertEqual(61, facts['time_limit'])

    def test_each_ratio_is_stamped_with_its_run(self):
        table = self._shipped()
        ratios = table['cells']['Iop']['str']['plain']['200']['ratios']
        self.assertEqual({'tune/run-7'}, {entry['source'] for entry in ratios.values()})

    def test_the_engine_cell_keeps_its_reason_and_no_ratios(self):
        cell = self._shipped()['cells']['Cra']['agi']['glasscannon']['200']
        self.assertEqual(('engine', 'blind', {}), (cell['status'], cell['reason'], cell['ratios']))

    def test_the_table_survives_a_round_trip_through_json(self):
        table = self._shipped()
        self.assertEqual([], table_flaws(json.loads(json.dumps(table))))

    def test_a_table_of_another_generator_version_fails(self):
        table = self._shipped()
        table['header']['generator_version'] = tuning.GENERATOR_VERSION + 1
        self.assertEqual([('header', 'generator_version')], table_flaws(table))

    def test_a_table_of_another_engine_fails(self):
        table = self._shipped()
        table['header']['engine_digest'] = '0' * 40
        self.assertEqual([('header', 'engine_digest')], table_flaws(table))

    def test_a_table_of_another_split_fails(self):
        table = self._shipped()
        table['header']['split_digest'] = '0' * 40
        self.assertEqual([('header', 'split_digest')], table_flaws(table))

    def test_a_table_of_another_data_version_only_warns(self):
        table = self._shipped()
        table['header']['data_version'] = 'older'
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            flaws = table_flaws(table)
        self.assertEqual([], flaws)
        self.assertTrue(any('data_version' in str(item.message) for item in caught))

    def test_a_cell_off_the_grid_fails(self):
        table = self._shipped()
        table['cells']['Iop']['str']['plain']['199'] = copy.deepcopy(table['cells']['Iop']['str']['plain']['200'])
        self.assertEqual([('Iop/str/plain/199', 'not a grid cell')], table_flaws(table))

    def test_a_shipped_cell_that_gained_nothing_fails(self):
        table = self._shipped()
        table['cells']['Iop']['str']['plain']['200']['u_acc_gain']['lo'] = 0.0
        self.assertEqual([('Iop/str/plain/200', 'u_acc_gain')], table_flaws(table))

    def test_a_shipped_cell_on_a_blind_class_fails(self):
        table = self._shipped()
        table['cells']['Iop']['str']['plain']['200']['blind_share'] = tuning.BLIND_SHARE - 0.01
        self.assertEqual([('Iop/str/plain/200', 'blind')], table_flaws(table))


class TheShippedFileCarriesItsMeasurementTests(SimpleTestCase):

    def setUp(self):
        if not os.path.isfile(PATH):
            self.skipTest('no weight table is shipped for %s' % VERSION)
        with open(PATH, encoding='utf-8') as handle:
            self.table = json.load(handle)

    def test_the_file_passes_every_check(self):
        self.assertEqual([], table_flaws(self.table))

    def test_the_file_says_it_is_generated(self):
        self.assertIn('do not edit', self.table['header']['generated'])

    def test_the_file_holds_only_the_cells_of_the_grid(self):
        held = {'/'.join((char_class, key, scenario, band)) for char_class, by_key in self.table['cells'].items()
                for key, by_scenario in by_key.items() for scenario, by_band in by_scenario.items() for band in by_band}
        self.assertLessEqual(held, CELL_KEYS)
