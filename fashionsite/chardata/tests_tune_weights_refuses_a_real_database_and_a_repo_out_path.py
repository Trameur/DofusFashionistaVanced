# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""tune_weights runs on an in-memory database into a folder outside the repository, and only --ship writes a table."""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
from types import SimpleNamespace
from unittest import mock, skipUnless

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase

from chardata import weight_tuning as tuning
from chardata.management.commands import tune_weights
from chardata.weight_table import DIRECTORY, engine_ratios

VERSION = 'dofus3'
IN_MEMORY = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'file:memorydb_default?mode=memory&cache=shared'}
ON_DISK = {'ENGINE': 'django.db.backends.sqlite3', 'NAME': 'C:/Users/nobody/db.sqlite3'}


class _Result(object):
    """A door's answer whose read is the engine's own, so a cell finds nothing to change."""

    def __init__(self, instance, ids):
        self.read_ratios = engine_ratios(instance.char_class, instance.elements, instance.scenario, VERSION)
        self.set_ids = tuple(ids)
        self.contributions = {item_id: 10.0 - item_id for item_id in range(1, 8)}
        self.item_sums = {}
        self.proven = True
        self.infeasible = False
        self.turn = 1000.0
        self.view = object()
        self.ehp = 5000.0
        self.seconds = 1.0
        self.wall = 1.5
        self.notes = []
        self.guard = None

    def read(self, lam):
        return tuning.Read(dict(self.read_ratios), set(), self.turn, self.ehp, 2.0)

    def u_fit(self, lam):
        return 1.0

    def evaluation(self):
        return {'valid': True, 'proven': True, 'T': self.turn, 'E': self.ehp, 'u_acc': {'lo': 1.0, 'hi': 1.0},
                'pow_share': 0.5, 'seconds': 1.0, 'set': list(self.set_ids)}


class _Runner(object):
    game_version = VERSION

    def __init__(self):
        self.calls = []
        self.closed = False

    def run(self, instance, ratios=None, forbid=(), time_limit=tuning.TIME_LIMIT, guarded=False, budget_factor=1):
        self.calls.append(tuning.instance_key(instance))
        return _Result(instance, (len(self.calls),))

    def close(self):
        self.closed = True


class _Command(SimpleTestCase):

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.out = os.path.join(folder.name, 'run')
        self.runner = _Runner()
        for patcher in (mock.patch.object(tune_weights, 'settings', SimpleNamespace(DATABASES={'default': IN_MEMORY})),
                        mock.patch.object(tune_weights, 'make_runner', side_effect=lambda version: self.runner)):
            patcher.start()
            self.addCleanup(patcher.stop)
        self.addCleanup(setattr, tune_weights, '_RUNNER', None)
        self.tables_before = self.tables()

    def tables(self):
        return sorted(os.listdir(DIRECTORY)) if os.path.isdir(DIRECTORY) else []

    def call(self, *args):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            call_command('tune_weights', *args, stdout=stdout)
        return stdout.getvalue()


class TheOutFolderIsOutsideTheRepositoryTests(_Command):

    def test_a_folder_inside_the_repository_is_refused_and_not_made(self):
        inside = os.path.join(tuning.repository_root(), 'tuner_out_that_must_not_exist')
        for args in (['--dry-run'], ['--plan'], ['--ship', self.out]):
            with self.subTest(args=args):
                with self.assertRaisesRegex(CommandError, 'outside the repository'):
                    self.call('--out', inside, *args)
                self.assertFalse(os.path.exists(inside))

    def test_the_repository_itself_and_its_subfolders_are_refused(self):
        root = tuning.repository_root()
        for path in (root, os.path.join(root, 'fashionsite'), os.path.join(root, 'fashionsite', 'chardata', 'x')):
            with self.subTest(path=path):
                with self.assertRaisesRegex(CommandError, 'outside the repository'):
                    self.call('--out', path, '--dry-run')

    def test_the_repository_root_is_the_one_holding_the_site(self):
        self.assertTrue(os.path.isdir(os.path.join(tuning.repository_root(), 'fashionsite', 'chardata')))
        self.assertTrue(os.path.isfile(os.path.join(tuning.repository_root(), '.gitattributes')))

    def test_a_folder_beside_the_repository_with_the_same_prefix_is_not_inside(self):
        beside = tuning.repository_root().rstrip('/\\') + '_beside'
        self.assertFalse(tuning.path_is_inside(beside, tuning.repository_root()))
        self.assertTrue(tuning.path_is_inside(os.path.join(tuning.repository_root(), 'a'), tuning.repository_root()))

    def test_a_folder_on_another_drive_is_outside(self):
        with mock.patch('os.path.commonpath', side_effect=ValueError("Paths don't have the same drive")):
            self.assertFalse(tuning.path_is_inside('D:/tuner', tuning.repository_root()))

    @skipUnless(os.name == 'nt', 'drive letters')
    def test_the_command_accepts_a_folder_on_a_drive_the_repository_is_not_on(self):
        repository_drive = os.path.splitdrive(os.path.abspath(tuning.repository_root()))[0].upper()
        other = next(letter + ':' for letter in 'ZYXWV' if letter + ':' != repository_drive)
        folder = other + '/tuner_out_that_must_not_exist'
        self.assertFalse(tuning.path_is_inside(folder, tuning.repository_root()))
        self.assertIn('570 cells', self.call('--out', folder, '--plan'))
        self.assertFalse(os.path.exists(folder))

    def test_a_folder_outside_is_made_and_used(self):
        self.call('--out', self.out, '--dry-run', '--processes', '1')
        self.assertTrue(os.path.isdir(self.out))

    def test_the_out_folder_is_required(self):
        with self.assertRaises(CommandError):
            call_command('tune_weights', '--dry-run')


class TheDatabaseIsInMemoryTests(_Command):

    def test_a_database_on_disk_is_refused_and_nothing_is_made(self):
        for database in (ON_DISK, {'ENGINE': 'django.db.backends.mysql', 'NAME': 'memory'},
                         {'ENGINE': 'django.db.backends.postgresql', 'NAME': 'memory'}, {}):
            for args in (['--dry-run'], []):
                with self.subTest(database=database, args=args):
                    with mock.patch.object(tune_weights, 'settings', SimpleNamespace(DATABASES={'default': database})):
                        with self.assertRaisesRegex(CommandError, 'in-memory sqlite'):
                            self.call('--out', self.out, '--processes', '1', *args)
                    self.assertFalse(os.path.exists(self.out))
        self.assertEqual([], self.runner.calls)

    def test_the_predicate_accepts_only_in_memory_sqlite(self):
        self.assertTrue(tuning.database_is_in_memory(IN_MEMORY))
        self.assertTrue(tuning.database_is_in_memory({'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}))
        self.assertFalse(tuning.database_is_in_memory(ON_DISK))
        self.assertFalse(tuning.database_is_in_memory({'ENGINE': 'django.db.backends.mysql', 'NAME': ':memory:'}))

    def test_the_plan_needs_no_database(self):
        with mock.patch.object(tune_weights, 'settings', SimpleNamespace(DATABASES={'default': ON_DISK})):
            self.assertIn('570 cells', self.call('--out', self.out, '--plan'))


class TheOptionsAreCheckedTests(_Command):

    def test_only_dofus_3_has_a_table(self):
        with self.assertRaises(CommandError):
            self.call('--out', self.out, '--version', 'beta', '--dry-run')

    def test_the_version_option_names_the_game_not_the_program(self):
        self.call('--out', self.out, '--version', VERSION, '--dry-run', '--processes', '1')

    def test_a_scenario_a_class_an_element_set_or_a_cell_that_does_not_exist_is_refused(self):
        for args in (['--scenarios', 'boss'], ['--classes', 'Nobody'], ['--elements', 'int+str'],
                     ['--cells', 'Iop/str'], ['--cells', 'Nobody/str/plain']):
            with self.subTest(args=args):
                with self.assertRaises(CommandError):
                    self.call('--out', self.out, '--processes', '1', *args)

    def test_a_folder_that_already_holds_a_run_needs_resume(self):
        os.makedirs(os.path.join(self.out, 'cells'))
        with open(os.path.join(self.out, 'cells', 'Iop__str__plain__200.json'), 'w') as handle:
            handle.write('{}')
        with self.assertRaisesRegex(CommandError, 'already holds a run'):
            self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1')
        self.assertEqual([], self.runner.calls)

    def test_resume_skips_the_cells_the_folder_holds(self):
        os.makedirs(os.path.join(self.out, 'cells'))
        with open(os.path.join(self.out, 'cells', 'Iop__str__plain__200.json'), 'w') as handle:
            handle.write('{}')
        text = self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1', '--resume')
        self.assertIn('0 of 0 groups finished', text)
        self.assertEqual([], self.runner.calls)

    def test_a_ship_of_a_folder_that_is_no_run_is_refused(self):
        os.makedirs(self.out)
        with self.assertRaisesRegex(CommandError, 'not a run folder'):
            self.call('--out', self.out, '--ship', self.out)
        self.assertEqual(self.tables_before, self.tables())


class ADryRunWritesNoTableTests(_Command):

    def test_it_tunes_the_two_smoke_instances_and_reports_them(self):
        text = self.call('--out', self.out, '--dry-run', '--processes', '1')
        self.assertIn('dry run: 2 instances, no table written', text)
        with open(os.path.join(self.out, 'dry.json'), encoding='utf-8') as handle:
            report = json.load(handle)
        self.assertEqual(['Iop/str/glasscannon/200/high', 'Cra/agi/plain/200/high'],
                         [item['instance'] for item in report])
        self.assertEqual(['Iop/str/glasscannon/200/high', 'Cra/agi/plain/200/high'], self.runner.calls)

    def test_it_writes_no_cell_and_no_table_and_closes_the_runner(self):
        self.call('--out', self.out, '--dry-run', '--processes', '1')
        self.assertFalse(os.path.exists(os.path.join(self.out, 'cells')))
        self.assertEqual(self.tables_before, self.tables())
        self.assertTrue(self.runner.closed)

    def test_it_logs_each_round_to_the_run_folder(self):
        self.call('--out', self.out, '--dry-run', '--processes', '1')
        logs = [name for name in os.listdir(self.out) if name.startswith('rounds_')]
        self.assertEqual(1, len(logs))
        with open(os.path.join(self.out, logs[0]), encoding='utf-8') as handle:
            rounds = [json.loads(line) for line in handle]
        self.assertEqual(2, len(rounds))
        for item in rounds:
            fields = {'instance', 'round', 'u_fit', 'u_acc', 'T', 'E', 'changed', 'set', 'proven', 'seconds'}
            self.assertLessEqual(fields, set(item))

    def test_the_rounds_of_a_dry_run_are_capped(self):
        self.assertEqual(2, tuning.DRY_ROUNDS)

    def test_warm_solves_one_throwaway_door_first(self):
        self.call('--out', self.out, '--dry-run', '--processes', '1', '--warm')
        self.assertEqual(3, len(self.runner.calls))
        self.assertEqual(self.runner.calls[0], self.runner.calls[1])


class ARunWritesRecordsAndOnlyShipWritesTheTableTests(_Command):

    def test_a_run_writes_a_record_per_cell_and_the_meta_and_no_table(self):
        text = self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1')
        self.assertIn('1 of 1 groups finished', text)
        with open(os.path.join(self.out, 'cells', 'Iop__str__plain__200.json'), encoding='utf-8') as handle:
            record = json.load(handle)
        self.assertEqual(('engine', 'no_change'), (record['status'], record['reason']))
        with open(os.path.join(self.out, 'run.json'), encoding='utf-8') as handle:
            meta = json.load(handle)
        self.assertEqual((VERSION, tuning.GENERATOR_VERSION), (meta['version'], meta['generator_version']))
        self.assertEqual(self.tables_before, self.tables())
        self.assertTrue(self.runner.closed)

    def test_a_run_solves_the_four_dev_instances_and_nothing_else_when_nothing_changes(self):
        self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1')
        self.assertEqual(['Iop/str/plain/200/high', 'Iop/str/plain/200/mid', 'Iop/str/plain/200/rest',
                          'Iop/str/plain/200/tail'], self.runner.calls)

    def test_the_run_keeps_the_item_data_it_was_tuned_on(self):
        self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1')
        with open(os.path.join(self.out, 'run.json'), encoding='utf-8') as handle:
            meta = json.load(handle)
        self.assertEqual(tuning._data_version(VERSION), meta['data_version'])
        self.assertTrue(meta['data_version'])
        self.assertEqual(tuning.game_data_sha1(VERSION), meta['game_data_sha1'])
        self.assertTrue(meta['game_data_sha1'])

    def test_the_run_keeps_its_solver_settings_and_the_table_carries_them(self):
        self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1', '--time-limit', '77')
        with open(os.path.join(self.out, 'run.json'), encoding='utf-8') as handle:
            solver = json.load(handle)['solver']
        self.assertEqual(77, solver['time_limit'])
        with tempfile.TemporaryDirectory() as tables:
            with mock.patch.object(tune_weights, 'DIRECTORY', tables):
                self.call('--out', os.path.join(os.path.dirname(self.out), 'ship'), '--ship', self.out)
            with open(os.path.join(tables, '%s.json' % VERSION), encoding='utf-8') as handle:
                table = json.load(handle)
        self.assertEqual(solver, table['header']['solver'])

    def test_ship_writes_the_table_of_a_run_folder_into_the_directory_of_tables(self):
        self.call('--out', self.out, '--cells', 'Iop/str/plain', '--processes', '1')
        with tempfile.TemporaryDirectory() as tables:
            with mock.patch.object(tune_weights, 'DIRECTORY', tables):
                other = os.path.join(os.path.dirname(self.out), 'ship')
                text = self.call('--out', other, '--ship', self.out)
            with open(os.path.join(tables, '%s.json' % VERSION), encoding='utf-8') as handle:
                table = json.load(handle)
        self.assertIn('0 cells shipped', text)
        self.assertEqual(VERSION, table['header']['game_version'])
        self.assertEqual('engine', table['cells']['Iop']['str']['plain']['200']['status'])
        self.assertEqual(self.tables_before, self.tables())


class ThePlanIsAProjectionTests(_Command):

    def test_it_names_the_cells_and_the_hours(self):
        text = self.call('--out', self.out, '--plan', '--processes', '5')
        self.assertIn('570 cells', text)
        self.assertIn('on 5 processes', text)
        self.assertFalse(os.path.exists(self.out))

    def test_a_filter_narrows_it(self):
        text = self.call('--out', self.out, '--plan', '--scenarios', 'plain', '--classes', 'Iop')
        self.assertIn('10 cells', text)


def apps_ready_in_the_worker(job):
    from django.apps import apps
    return apps.ready


_POOL_SCRIPT = '''
import json
import os
import sys
sys.path.append(os.path.join(os.getcwd(), '..', 'fashionistapulp'))
import django
django.setup()
from chardata.management.commands import tune_weights
from chardata.tests_tune_weights_refuses_a_real_database_and_a_repo_out_path import apps_ready_in_the_worker
print(json.dumps(list(tune_weights._pool_map(apps_ready_in_the_worker, [1, 2, 3, 4], 2))))
'''


class TheSpawnedWorkersSetDjangoUpTests(SimpleTestCase):

    def test_every_worker_of_a_two_process_pool_has_its_apps_loaded_before_its_first_job(self):
        site = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env = dict(os.environ, DJANGO_SETTINGS_MODULE='fashionsite.settings_test')
        out = subprocess.run([sys.executable, '-c', _POOL_SCRIPT], capture_output=True, env=env, cwd=site,
                             timeout=300)
        lines = [line for line in out.stdout.decode('utf-8', 'replace').splitlines() if line.startswith('[')]
        self.assertTrue(lines, out.stderr.decode('utf-8', 'replace')[-800:])
        self.assertEqual([True] * 4, json.loads(lines[-1]))
