import copy
import contextlib
import io
import json
import os
from pathlib import Path
import sqlite3
import subprocess
import tempfile
import threading
from types import SimpleNamespace
from unittest import TestCase, mock

import update_all as updater
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
import update_audit as audit


class UpdateLauncherTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(updater, 'ROOT', self.root).start()
        mock.patch.object(updater, 'REPORTS', self.root / '.update-reports').start()
        mock.patch.object(audit, 'ROOT', self.root).start()
        mock.patch.object(audit, 'DATA', self.root / 'fashionistapulp/fashionistapulp').start()
        mock.patch.object(audit, 'STATIC', self.root / 'fashionsite/chardata/static').start()
        (self.root / 'fashionista_version.py').write_text('FASHIONISTA_VERSION = "3.6.9.0"\n', encoding='utf-8')

    def test_an_unavailable_source_cannot_be_selected_and_wakfu_is_explicit(self):
        rows = [{'key': key, 'error': 'offline' if key == 'beta' else None, 'changed': True}
                for key in updater.VERSIONS]
        self.assertEqual(['dofus3', 'dofus2', 'touch', 'retro'], updater.selection('all', rows))
        self.assertEqual(['touch', 'wakfu'], updater.selection('4,6', rows))
        self.assertEqual([], updater.selection('', rows))
        with self.assertRaises(ValueError):
            updater.selection('beta', rows)
        with self.assertRaises(ValueError):
            updater.selection('99', rows)

    def test_the_importable_version_uses_the_matching_api_and_archive(self):
        assets = [{'name': name + '.json'} for name in ('spells', 'effects', 'breeds', 'monsters', 'recipes', 'en', 'fr', 'es', 'pt', 'de')]
        catalog = {'games': {'dofus': {'platforms': {'windows': {'dofus3': '6.0_3.6.11.0'}}}}}
        with mock.patch.object(updater, 'fetch_json', side_effect=[
                {'version': '3.6.10.0'}, {'tag_name': '3.6.10.0', 'assets': assets}]) as fetch:
            row = updater.probe('dofus3', catalog)
        self.assertEqual('3.6.10.0', row['available'])
        self.assertTrue(row['warnings'])
        self.assertTrue(fetch.call_args_list[1].args[0].endswith('/releases/tags/3.6.10.0'))

    def test_an_incomplete_archive_is_not_importable(self):
        with mock.patch.object(updater, 'fetch_json', side_effect=[{'version': '3.6.10.0'}, {'assets': []}]):
            with self.assertRaisesRegex(ValueError, 'incomplète'):
                updater.probe('dofus3')

    def test_retro_probe_loads_the_flat_itemscraper_modules(self):
        manifest = {key: '123' for key in ('items', 'itemstats', 'itemsets', 'crafts', 'classes', 'effects', 'spells')}
        metadata = {'FASHIONISTA_RETRO_VERSION': '1.49', 'WATCHED_RETRO_BUILD': 'old',
                    'WATCHED_RETRO_ASSET_DIGEST': 'old',
                    'WATCHED_RETRO_LANG': {key: 'old' for key in manifest}}
        catalog = {'games': {'retro': {'platforms': {'windows': {'main': 'retro_1.49.5.5656.445'}}}}}
        with mock.patch.object(updater, 'read_metadata', return_value=metadata), \
                mock.patch('download_retro_langs.fetch_manifest', return_value=manifest), \
                mock.patch('check_game_versions.retro_asset_entries', return_value=[{'name': 'clip.swf'}]), \
                mock.patch('check_game_versions.retro_asset_digest', return_value='digest'):
            row = updater.probe('retro', catalog)
        self.assertEqual('1.49.5', row['available'])
        self.assertEqual('1.49.5.5656.445', row['source']['build'])
        self.assertTrue(row['changed'])

    def test_touch_reads_the_build_shown_by_the_official_client(self):
        script = b'window.appInfo={version:"3.14.2"};window.buildVersion="1.74.5";assets="3.3.6_hash";'
        with mock.patch.object(updater.urllib.request, 'urlopen', return_value=io.BytesIO(script)):
            self.assertEqual('1.74.5', updater.touch_build_version())

    def test_a_missing_or_ambiguous_touch_build_is_not_guessed(self):
        for script in (b'<html>Unavailable</html>', b'window.appInfo={version:"3.14.2"}',
                       b'window.buildVersion="1.74.5";window.buildVersion="1.74.6";',
                       b'window.buildVersion="1.74.5-beta";'):
            with self.subTest(script=script), mock.patch.object(
                    updater.urllib.request, 'urlopen', return_value=io.BytesIO(script)):
                with self.assertRaisesRegex(ValueError, 'Build Touch'):
                    updater.touch_build_version()

    def test_retro_shortens_only_a_valid_build(self):
        for raw in ('1.49.5', '1.49.5.5656.445-401e092', '6.0_1.49.5.5656.445-401e092'):
            self.assertEqual('1.49.5', updater.retro_game_version(raw))
        for raw in ('1.49', 'unknown', '1.49.5trailing'):
            with self.assertRaises(ValueError):
                updater.retro_game_version(raw)

    def touch_probe(self, build='1.74.5', previous=None, current='1.74.5', assets='3.3.6_hash'):
        config = {'assetsUrl': 'https://dofustouch.cdn.ankama.com/assets/' + assets,
                  'serverLanguages': ['fr', 'en'], 'dataUrl': 'https://example.invalid'}
        metadata = {'FASHIONISTA_TOUCH_VERSION': current, 'WATCHED_TOUCH_ASSETS': '3.3.6_hash'}
        state = {'touch': {'source': previous}} if previous else {}
        with mock.patch.object(updater, 'fetch_json', return_value=config), \
                mock.patch.object(updater, 'touch_build_version', return_value=build), \
                mock.patch.object(updater, 'read_metadata', return_value=metadata), \
                mock.patch.object(updater, 'read_json', return_value=state):
            return updater.probe('touch')

    def test_touch_build_and_resources_move_independently(self):
        previous = self.touch_probe()['source']
        self.assertFalse(self.touch_probe(previous=previous)['changed'])
        self.assertTrue(self.touch_probe(build='1.74.6', previous=previous)['changed'])
        row = self.touch_probe(assets='3.3.7_hash', previous=previous)
        self.assertTrue(row['changed'])
        self.assertEqual('1.74.5', row['available'])

    def test_old_touch_state_is_revalidated_without_inventing_a_local_build(self):
        previous = self.touch_probe()['source']
        del previous['build']
        row = self.touch_probe(previous=previous, current='1.74')
        self.assertEqual('1.74', row['current'])
        self.assertEqual('1.74.5', row['available'])
        self.assertTrue(row['changed'])
        with self.assertRaisesRegex(ValueError, 'rétrogradation'):
            self.touch_probe(current='1.74.6')

    def test_console_and_report_separate_touch_build_from_assets(self):
        row = dict(self.touch_probe(current='1.74'), images=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            updater.show_versions([row])
        report = updater.report_markdown({'status': 'VALIDÉ', 'directory': 'report', 'versions': [row]})
        for rendered in (output.getvalue(), report):
            self.assertIn('Build du jeu disponible : 1.74.5', rendered)
            self.assertIn('Ressources CDN : 3.3.6_hash', rendered)
            self.assertNotIn('Importable : 3.3.6', rendered)

    def test_game_labels_are_restored_when_validation_fails(self):
        settings = self.root / 'fashionsite/fashionsite/settings_test.py'
        settings.parent.mkdir(parents=True)
        settings.write_text('', encoding='utf-8')
        version_file = self.root / 'fashionista_version.py'
        for key, version in (('dofus3', '3.6.12.16'), ('beta', '3.7.1.1'), ('dofus2', '2.73.3.14'),
                             ('touch', '1.74.5'), ('retro', '1.49.5')):
            for exit_code in (0, 1):
                with self.subTest(key=key, exit_code=exit_code):
                    original = ('FASHIONISTA_TOUCH_VERSION = "1.74"\nFASHIONISTA_RETRO_VERSION = "1.49"\n'
                                'FASHIONISTA_VERSION = "3.6.11.15"\nFASHIONISTA_BETA_VERSION = "3.7.0.0"\n'
                                'FASHIONISTA_DOFUS2_VERSION = "2.73.3.13"\n'
                                'WATCHED_RETRO_ASSET_DIGEST = "old"\nWATCHED_RETRO_ASSET_COUNT = 10\nLOCAL_EDIT = True\n')
                    version_file.write_text(original, encoding='utf-8')
                    row = {'key': key, 'current': updater.read_metadata()[updater.METADATA[key]],
                           'available': version, 'source': {'build': version}}
                    reports = self.root / ('reports-%s-%s' % (key, exit_code))
                    args = SimpleNamespace(running_file=self.root / 'RUNNING.md', step_timeout=60)
                    def run(command, log, **kwargs):
                        log.write_text('ok', encoding='utf-8')
                        if log.stem in ('generation', 'weapons', 'django'):
                            self.assertEqual(log.stem != 'weapons', kwargs['django'])
                        if log.stem == 'django':
                            self.assertEqual(row['current'], updater.read_metadata()[updater.METADATA[key]])
                        return {'exit_code': exit_code if log.stem == 'django' else 0,
                                'log': str(log), 'seconds': .1}
                    with mock.patch.object(updater, 'REPORTS', reports), \
                            mock.patch.object(updater, 'check_configuration'), \
                            mock.patch.object(updater, 'probe', return_value=row), \
                            mock.patch.object(updater, 'run_command', side_effect=run), \
                            mock.patch.object(audit, 'snapshot', return_value={}), \
                            mock.patch.object(audit, 'compare', return_value={'errors': [], 'warnings': []}):
                        self.assertEqual(exit_code, updater.execute([row], [key], {key: False}, args))
                    if exit_code:
                        self.assertEqual(original, version_file.read_text(encoding='utf-8'))
                        self.assertFalse((reports / 'state.json').exists())
                    else:
                        self.assertEqual(version, updater.read_metadata()[updater.METADATA[key]])
                        self.assertIn('LOCAL_EDIT = True', version_file.read_text(encoding='utf-8'))

    def test_exclusive_work_is_refused_without_removing_someone_elses_marker(self):
        running = self.root / 'RUNNING.md'
        running.write_text('# Work\n## En cours\nother rebuild\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'déjà'):
            with updater.exclusive(running):
                self.fail('lock accepted')
        self.assertIn('other rebuild', running.read_text(encoding='utf-8'))
        self.assertFalse((self.root / '.update-data.lock').exists())

    def test_our_marker_is_removed_even_after_an_error(self):
        running = self.root / 'RUNNING.md'
        running.write_text('## En cours\n(rien)\n', encoding='utf-8')
        with self.assertRaises(ValueError):
            with updater.exclusive(running):
                self.assertIn('update_all pid=', running.read_text(encoding='utf-8'))
                raise ValueError('failure')
        self.assertNotIn('update_all pid=', running.read_text(encoding='utf-8'))
        self.assertFalse((self.root / '.update-data.lock').exists())

    def test_a_second_launcher_does_not_remove_the_existing_lock(self):
        running = self.root / 'missing-running.md'
        with updater.exclusive(running):
            with self.assertRaises(FileExistsError):
                with updater.exclusive(running):
                    pass
            self.assertTrue((self.root / '.update-data.lock').exists())

    def test_a_separate_process_cannot_take_the_active_guard(self):
        script = """import sys
from pathlib import Path
import update_all as u
u.ROOT = Path(sys.argv[1])
try:
    with u.update_guard():
        raise SystemExit(2)
except FileExistsError:
    pass
"""
        with updater.update_guard():
            result = subprocess.run([sys.executable, '-c', script, str(self.root)],
                                    cwd=Path(updater.__file__).parent, capture_output=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)

    def test_forced_process_exit_releases_the_guard_and_allows_marker_recovery(self):
        script = """import os, sys
from pathlib import Path
import update_all as u
u.ROOT = Path(sys.argv[1])
with u.exclusive(u.ROOT / 'RUNNING.md'):
    os._exit(0)
"""
        running = self.root / 'RUNNING.md'
        running.write_text('## En cours\n\n(rien)\n', encoding='utf-8')
        result = subprocess.run([sys.executable, '-c', script, str(self.root)],
                                cwd=Path(updater.__file__).parent, capture_output=True, timeout=15)
        self.assertEqual(0, result.returncode, result.stderr)
        self.assertTrue((self.root / '.update-data.lock').exists())
        processes = [{'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}]
        with mock.patch.object(updater, 'process_snapshot', return_value=processes):
            with updater.exclusive(running):
                self.assertIn('pid=%d' % os.getpid(), running.read_text(encoding='utf-8'))
        self.assertFalse((self.root / '.update-data.lock').exists())
        self.assertNotIn('update_all pid=', running.read_text(encoding='utf-8'))

    def test_an_orphaned_running_marker_is_recovered_without_a_lock_file(self):
        running = self.root / 'RUNNING.md'
        running.write_text('## En cours\n\nupdate_all pid=999999 2026-09-22T20:52:15\n', encoding='utf-8')
        processes = [{'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}]
        with mock.patch.object(updater, 'process_snapshot', return_value=processes):
            with updater.exclusive(running):
                self.assertNotIn('999999', running.read_text(encoding='utf-8'))
        self.assertNotIn('update_all pid=', running.read_text(encoding='utf-8'))

    def test_a_dead_launcher_marker_is_recovered_but_other_work_is_preserved(self):
        marker = 'update_all pid=999999 2026-09-22T20:52:15+02:00'
        lock = self.root / '.update-data.lock'
        running = self.root / 'RUNNING.md'
        own = {'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}
        for other in ('', '\nother rebuild'):
            with self.subTest(other=other):
                lock.write_text(marker, encoding='utf-8')
                running.write_text('## En cours\n' + marker + other + '\n', encoding='utf-8')
                with mock.patch.object(updater, 'process_snapshot', return_value=[own]):
                    if other:
                        with self.assertRaisesRegex(RuntimeError, 'other rebuild'):
                            with updater.exclusive(running):
                                self.fail('other work ignored')
                        self.assertIn('other rebuild', running.read_text(encoding='utf-8'))
                    else:
                        with updater.exclusive(running):
                            self.assertIn('pid=%s' % os.getpid(), lock.read_text(encoding='utf-8'))
                self.assertNotIn(marker, running.read_text(encoding='utf-8'))
                self.assertFalse(lock.exists())

    def test_active_or_unverifiable_processes_keep_the_old_lock(self):
        marker = 'update_all pid=999999 2026-09-22T20:52:15+02:00'
        lock = self.root / '.update-data.lock'
        running = self.root / 'RUNNING.md'
        own = {'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}
        for process in (
                {'pid': 999999, 'parent': 1, 'name': 'python', 'command': 'update_all.py'},
                {'pid': 12, 'parent': 999999, 'name': 'python', 'command': 'worker.py'},
                {'pid': 13, 'parent': 1, 'name': 'python', 'command': 'update_data_touch.py'},
                {'pid': 14, 'parent': 1, 'name': 'python', 'command': ''},
                None):
            with self.subTest(process=process):
                lock.write_text(marker, encoding='utf-8')
                running.write_text('## En cours\n' + marker + '\n', encoding='utf-8')
                with mock.patch.object(updater, 'process_snapshot', return_value=[own, process] if process else []):
                    with self.assertRaises(RuntimeError):
                        with updater.exclusive(running):
                            self.fail('active lock accepted')
                self.assertEqual(marker, lock.read_text(encoding='utf-8'))
                self.assertIn(marker, running.read_text(encoding='utf-8'))

    def test_worker_passes_the_target_version_without_changing_the_site_label(self):
        for key, setter in (('dofus3', 'set_version'), ('beta', 'set_beta_version'), ('dofus2', 'set_dofus2_version')):
            with self.subTest(key=key):
                module = SimpleNamespace(__file__='legacy.py')
                write = mock.Mock()
                setattr(module, setter, write)
                def main():
                    version = module.__dict__[setter](updater.sys.argv[2])
                    self.assertEqual('3.7.1.1', version)
                    module.run_step('spells/download', ['python', 'download_raw_data.py', version])
                module.main = main
                def run(command, log, *args, **kwargs):
                    self.assertIn('3.7.1.1', command)
                    log.write_text('ok', encoding='utf-8')
                    return {'exit_code': 0, 'log': str(log)}
                job = self.root / 'job.json'
                updater.write_json(job, {'key': key, 'images': False, 'available': '3.7.1.1', 'timeout': 60})
                with mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                        mock.patch.object(updater, 'run_command', side_effect=run), mock.patch.object(updater.sys, 'argv', []):
                    updater.worker(job)
                write.assert_not_called()

    def test_backup_restores_local_edits_and_removes_new_output(self):
        data = audit.DATA
        data.mkdir(parents=True)
        constants = data / 'dofus_constants.py'
        constants.write_text('LOCAL_CHANGE = True\n', encoding='utf-8')
        database = audit.database_path('touch')
        with audit.writable(database) as conn:
            conn.execute('CREATE TABLE items(id INTEGER)')
            conn.execute('INSERT INTO items VALUES (1)')
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['touch'], False, saved)
        constants.write_text('BROKEN = True\n', encoding='utf-8')
        with audit.writable(database) as conn:
            conn.execute('DELETE FROM items')
        reference = self.root / 'fashionsite/chardata/spell_reference/touch.json'
        reference.parent.mkdir(parents=True)
        reference.write_text('{}', encoding='utf-8')
        audit.restore_runtime(manifest, saved)
        self.assertEqual('LOCAL_CHANGE = True\n', constants.read_text(encoding='utf-8'))
        with audit.readonly(database) as conn:
            self.assertEqual([(1,)], conn.execute('SELECT * FROM items').fetchall())
        self.assertFalse(reference.exists())

    def test_bad_backup_is_rejected_before_any_restoration(self):
        saved = self.root / 'backup'
        manifest = audit.backup_runtime([], False, saved)
        (saved / 'fashionista_version.py').write_text('damaged', encoding='utf-8')
        with self.assertRaisesRegex(ValueError, 'altérée'):
            audit.restore_runtime(manifest, saved)

    def test_restoration_does_not_rewrite_unchanged_images(self):
        directory = audit.STATIC / 'chardata/items'
        directory.mkdir(parents=True)
        changed = directory / 'changed.png'
        unchanged = directory / 'unchanged.png'
        changed.write_bytes(b'old')
        unchanged.write_bytes(b'same')
        saved = self.root / 'backup'
        manifest = audit.backup_runtime([], True, saved)
        changed.write_bytes(b'new')
        with mock.patch.object(audit, 'replace_file', wraps=audit.replace_file) as replace:
            audit.restore_runtime(manifest, saved)
        self.assertEqual(b'old', changed.read_bytes())
        self.assertEqual([changed], [call.args[1] for call in replace.call_args_list])

    def test_preserved_mount_looks_survive_the_next_reload_from_dump(self):
        audit.DATA.mkdir(parents=True)
        before = self.root / 'previous.db'
        after = audit.database_path('dofus3')
        with audit.writable(before) as db:
            db.executescript("CREATE TABLE items(id, ankama_id, name); INSERT INTO items VALUES(1, 123, 'Mount');"
                             "CREATE TABLE mount_looks(item, look); INSERT INTO mount_looks VALUES(1, 'appearance');")
        with audit.writable(after) as db:
            db.executescript("CREATE TABLE items(id, ankama_id, name); INSERT INTO items VALUES(7, 123, 'Mount');")
        audit.preserve_table(before, after, 'mount_looks')
        with audit.writable(':memory:') as reloaded:
            reloaded.executescript((audit.DATA / 'item_db_dumped.dump').read_text(encoding='utf-8'))
            self.assertEqual([(7, 'appearance')], reloaded.execute('SELECT * FROM mount_looks').fetchall())

    def test_a_download_that_prints_failure_but_exits_zero_stops_the_pipeline(self):
        calls = []
        module = SimpleNamespace(__file__='legacy.py')
        def main():
            module.run_step('items/download', ['python', 'download.py'])
            calls.append('would rebuild')
        module.main = main
        def run(command, log, *args, **kwargs):
            log.write_text('Failed to retrieve equipment data for fr.\nFinished\n', encoding='utf-8')
            return {'exit_code': 0, 'log': str(log)}
        job = self.root / 'job.json'
        updater.write_json(job, {'key': 'dofus3', 'images': False, 'available': '3.6.10.0', 'timeout': 60})
        with mock.patch.object(updater.importlib, 'import_module', return_value=module), mock.patch.object(updater, 'run_command', side_effect=run), mock.patch.object(updater.sys, 'argv', []):
            with self.assertRaisesRegex(RuntimeError, 'Étape échouée'):
                updater.worker(job)
        self.assertEqual([], calls)
        self.assertEqual(1, updater.read_json(self.root / 'dofus3-steps.json')[0]['exit_code'])
        self.assertIn('Failed to retrieve', updater.read_json(self.root / 'dofus3-steps.json')[0]['error'])

    def test_without_images_skips_retro_artwork_and_touch_spell_icons(self):
        for version in ('touch', 'retro'):
            module = SimpleNamespace(__file__='legacy.py')
            def main():
                module.run_step('monsters/artworks', ['python', 'artwork.py'])
                module.run_step('spells/build', ['python', 'get_spells_touch.py'])
            module.main = main
            commands = []
            def run(command, log, *args, **kwargs):
                commands.append(command)
                log.write_text('ok\n', encoding='utf-8')
                return {'exit_code': 0, 'log': str(log)}
            job = self.root / 'job.json'
            updater.write_json(job, {'key': version, 'images': False, 'available': 'tag', 'timeout': 60})
            with mock.patch.object(updater.importlib, 'import_module', return_value=module), mock.patch.object(updater, 'run_command', side_effect=run), mock.patch.object(updater.sys, 'argv', []):
                updater.worker(job)
            self.assertEqual(1, len(commands))
            if version == 'touch':
                self.assertIn('--skip-images', commands[0])

    def test_unknown_stats_are_reported_without_zero_count_noise(self):
        self.assertEqual(['Missing translation for New stat'], updater.log_notices([
            'Missing translation for New stat', '0 unresolved', 'No warnings', 'Missing translation for New stat']))

    def test_failed_validation_restores_files_before_releasing_the_lock(self):
        settings = self.root / 'fashionsite/fashionsite/settings_test.py'
        settings.parent.mkdir(parents=True)
        settings.write_text('', encoding='utf-8')
        version_file = self.root / 'fashionista_version.py'
        original = version_file.read_bytes()
        row = {'key': 'dofus3', 'current': '3.6.9.0', 'available': '3.6.10.0', 'source': {'version': '3.6.10.0'}}
        args = SimpleNamespace(running_file=self.root / 'RUNNING.md', step_timeout=60)
        def run(command, log, **kwargs):
            version_file.write_text('FASHIONISTA_VERSION = "3.6.10.0"', encoding='utf-8')
            log.write_text('failed test' if log.stem == 'django' else 'ok', encoding='utf-8')
            return {'exit_code': 1 if log.stem == 'django' else 0, 'log': str(log), 'seconds': .1}
        original_restore = audit.restore_runtime
        def restore(manifest, source):
            self.assertTrue((self.root / '.update-data.lock').exists())
            original_restore(manifest, source)
        with mock.patch.object(updater, 'check_configuration'), mock.patch.object(updater, 'probe', return_value=row), mock.patch.object(updater, 'run_command', side_effect=run), mock.patch.object(audit, 'snapshot', return_value={}), mock.patch.object(audit, 'compare', return_value={'errors': [], 'warnings': []}), mock.patch.object(audit, 'restore_runtime', side_effect=restore):
            code = updater.execute([row], ['dofus3'], {'dofus3': False}, args)
        self.assertEqual(1, code)
        self.assertEqual(original, version_file.read_bytes())
        self.assertFalse((self.root / '.update-data.lock').exists())
        self.assertFalse((updater.REPORTS / 'state.json').exists())
        report = updater.read_json(next(updater.REPORTS.glob('*/report.json')))
        self.assertIn('RESTAURÉS', report['status'])
        self.assertEqual(3, len(report['checks']))

    def test_a_moving_source_stops_before_any_pipeline_command(self):
        settings = self.root / 'fashionsite/fashionsite/settings_test.py'
        settings.parent.mkdir(parents=True)
        settings.write_text('', encoding='utf-8')
        row = {'key': 'dofus3', 'current': 'old', 'available': 'new', 'source': {'version': 'new'}}
        args = SimpleNamespace(running_file=self.root / 'RUNNING.md', step_timeout=60)
        with mock.patch.object(updater, 'check_configuration'), mock.patch.object(updater, 'probe', return_value={'source': {'version': 'newer'}}), mock.patch.object(updater, 'run_command') as run, mock.patch.object(audit, 'snapshot', return_value={}):
            self.assertEqual(1, updater.execute([row], ['dofus3'], {'dofus3': False}, args))
        run.assert_not_called()

    def test_no_dofusdb_command_runs_including_the_monster_image_downloader(self):
        module = SimpleNamespace(__file__='legacy.py')
        def main():
            module.run_step('monster-images', ['python', 'download_monster_images.py'])
            module.run_step('monster-grades', ['python', 'store_dofusdb_monster_grades.py'])
        module.main = main
        job = self.root / 'job.json'
        updater.write_json(job, {'key': 'dofus3', 'images': True, 'available': '3.6.10.0', 'timeout': 60})
        with mock.patch.object(updater.importlib, 'import_module', return_value=module), mock.patch.object(updater, 'run_command') as run, mock.patch.object(audit, 'preserve_table') as preserve, mock.patch.object(updater.sys, 'argv', []):
            updater.worker(job)
        run.assert_not_called()
        preserve.assert_called_once()
        steps = updater.read_json(self.root / 'dofus3-steps.json')
        self.assertEqual(2, len(steps))
        self.assertTrue(all(step['warning'] for step in steps))

    def test_pipeline_failure_names_the_step_and_cause_in_the_console(self):
        settings = self.root / 'fashionsite/fashionsite/settings_test.py'
        settings.parent.mkdir(parents=True)
        settings.write_text('', encoding='utf-8')
        row = {'key': 'dofus3', 'current': '3.6.11.15', 'available': '3.6.12.16', 'source': {}}
        args = SimpleNamespace(running_file=self.root / 'RUNNING.md', step_timeout=60)
        error = "ModuleNotFoundError: No module named 'fashionistapulp.fashionistapulp'"
        def run(command, log, **kwargs):
            updater.write_json(log.parent / 'dofus3-steps.json', [
                {'step': 'items/dump', 'exit_code': 1, 'log': 'dump.log', 'error': error}])
            return {'exit_code': 1, 'log': str(log)}
        output = io.StringIO()
        with contextlib.redirect_stdout(output), mock.patch.object(updater, 'check_configuration'), \
                mock.patch.object(updater, 'probe', return_value=row), \
                mock.patch.object(updater, 'run_command', side_effect=run), \
                mock.patch.object(audit, 'snapshot', return_value={}), \
                mock.patch.object(audit, 'compare', return_value={'errors': [], 'warnings': []}):
            self.assertEqual(1, updater.execute([row], ['dofus3'], {'dofus3': False}, args))
        self.assertIn('Cause : dofus3 : items/dump : ' + error, output.getvalue())


class UpdateCommandTests(TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)

    def test_the_real_dump_script_uses_the_scraper_import_path(self):
        for name in ('transformed_equipment.json', 'transformed_sets.json'):
            (self.directory / name).write_text('[]', encoding='utf-8')
        dump = self.directory / 'items.dump'
        log = self.directory / 'dump.log'
        with contextlib.redirect_stdout(io.StringIO()):
            result = updater.run_command(
                [sys.executable, 'get_equipments3.py', '--input-dir', str(self.directory), '--dump-output', str(dump)],
                log, cwd=updater.ROOT / 'itemscraper', timeout=30)
        self.assertEqual(0, result['exit_code'], log.read_text(encoding='utf-8'))
        with audit.writable(':memory:') as database:
            database.executescript(dump.read_text(encoding='utf-8'))
            self.assertGreater(database.execute('SELECT COUNT(*) FROM stats').fetchone()[0], 0)

    def test_django_commands_keep_the_application_import_paths(self):
        log = self.directory / 'django-import.log'
        script = 'from fashionistapulp.dofus_constants import STAT_ORDER; from fashionsite import settings_test'
        with contextlib.redirect_stdout(io.StringIO()):
            result = updater.run_command([sys.executable, '-c', script], log, django=True, timeout=30)
        self.assertEqual(0, result['exit_code'], log.read_text(encoding='utf-8'))

    def test_existing_retro_renderers_are_detected_without_overwriting_configuration(self):
        flash = self.directory / 'Documents/fashionista-loop/tools/flash'
        for relative in ('jdk-21-jre/bin/java.exe', 'ffdec/ffdec.jar', 'resvg/resvg.exe'):
            path = flash / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
        with mock.patch.object(updater.Path, 'home', return_value=self.directory), \
                mock.patch.dict(updater.os.environ, {'JAVA_EXE': '', 'FFDEC_JAR': 'configured.jar', 'RESVG_EXE': ''}):
            env = updater.environment()
        self.assertEqual('configured.jar', env['FFDEC_JAR'])
        self.assertEqual(str(flash / 'jdk-21-jre/bin/java.exe'), env['JAVA_EXE'])
        self.assertEqual(str(flash / 'resvg/resvg.exe'), env['RESVG_EXE'])

    def test_child_progress_is_live_and_bulk_output_stays_in_the_log(self):
        ready = self.directory / 'ready'
        script = """import sys, time
from pathlib import Path
print('\\n'.join('detail %d' % n for n in range(500)))
print('[suivi] enfant prêt', flush=True)
deadline = time.monotonic() + 5
while not Path(sys.argv[1]).exists():
    if time.monotonic() > deadline:
        raise SystemExit(2)
    time.sleep(.01)
print('[suivi] fin sans retour', end='', flush=True)
"""
        class Output(io.StringIO):
            def write(self, value):
                if 'enfant prêt' in value:
                    ready.touch()
                return super().write(value)
        output = Output()
        log = self.directory / 'stream.log'
        with contextlib.redirect_stdout(output):
            result = updater.run_command([sys.executable, '-c', script, str(ready)], log,
                                         relay_progress=True, title='Import', timeout=10)
        self.assertEqual(0, result['exit_code'], log.read_text(encoding='utf-8'))
        self.assertIn('enfant prêt', output.getvalue())
        self.assertIn('fin sans retour', output.getvalue())
        self.assertNotIn('detail 499', output.getvalue())
        self.assertIn('detail 499', log.read_text(encoding='utf-8'))
        self.assertEqual(3, len(output.getvalue().splitlines()))

    def test_a_failed_command_returns_its_exact_cause(self):
        log = self.directory / 'failure.log'
        with contextlib.redirect_stdout(io.StringIO()):
            result = updater.run_command([sys.executable, '-c', "raise RuntimeError('import impossible')"], log)
        self.assertNotEqual(0, result['exit_code'])
        self.assertEqual('RuntimeError: import impossible', result['error'])
        self.assertIn('Traceback', log.read_text(encoding='utf-8'))

    def test_slow_python_phases_report_progress_and_stop_the_heartbeat(self):
        heartbeat = threading.Event()
        messages = []
        def report(message):
            messages.append(message)
            if 'en cours' in message:
                heartbeat.set()
        with mock.patch.object(updater, 'HEARTBEAT_SECONDS', .01), mock.patch.object(updater, 'progress', side_effect=report):
            with updater.phase('Sauvegarde'):
                self.assertTrue(heartbeat.wait(5))
        self.assertIn('terminé', messages[-1])

    def test_timeout_stops_the_child_and_retains_its_log(self):
        log = self.directory / 'timeout.log'
        script = "import time; print('prêt', flush=True); time.sleep(60)"
        processes = []
        original = subprocess.Popen
        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process
        with mock.patch.object(updater.subprocess, 'Popen', side_effect=start), \
                contextlib.redirect_stdout(io.StringIO()), self.assertRaises(TimeoutError):
            updater.run_command([sys.executable, '-c', script], log, timeout=.2)
        self.assertIsNotNone(processes[0].poll())
        self.assertIn('Commande :', log.read_text(encoding='utf-8'))

    def test_windows_database_replacement_retries_a_transient_lock(self):
        import load_item_db as loader
        source = self.directory / 'new.db'
        target = self.directory / 'items.db'
        source.write_bytes(b'new')
        target.write_bytes(b'old')
        replace = os.replace
        calls = []
        def temporarily_locked(*args):
            calls.append(args)
            if len(calls) == 1:
                raise PermissionError('locked')
            replace(*args)
        with mock.patch.object(loader.platform, 'system', return_value='Windows'), \
                mock.patch.object(loader.os, 'replace', side_effect=temporarily_locked), \
                mock.patch.object(loader.time, 'sleep'), contextlib.redirect_stdout(io.StringIO()):
            loader._replace_db_file(source, target)
        self.assertEqual(b'new', target.read_bytes())
        self.assertEqual(2, len(calls))

    def test_a_persistent_database_lock_preserves_both_files(self):
        import load_item_db as loader
        source = self.directory / 'new.db'
        target = self.directory / 'items.db'
        source.write_bytes(b'new')
        target.write_bytes(b'old')
        with mock.patch.object(loader.platform, 'system', return_value='Windows'), \
                mock.patch.object(loader.os, 'replace', side_effect=PermissionError('locked')), \
                self.assertRaises(PermissionError):
            loader._replace_db_file(source, target, timeout=0)
        self.assertEqual(b'old', target.read_bytes())
        self.assertEqual(b'new', source.read_bytes())

    def test_replacement_recovers_after_a_real_windows_sqlite_reader_closes(self):
        if os.name != 'nt':
            self.skipTest('Windows file locking')
        import load_item_db as loader
        source = self.directory / 'new.db'
        target = self.directory / 'items.db'
        source.write_bytes(b'new')
        connection = sqlite3.connect(target)
        self.addCleanup(connection.close)
        connection.execute('CREATE TABLE items(id)')
        connection.commit()
        class Output(io.StringIO):
            def write(self, value):
                if 'temporarily blocked' in value:
                    connection.close()
                return super().write(value)
        output = Output()
        with contextlib.redirect_stdout(output), mock.patch.object(loader.time, 'sleep'):
            loader._replace_db_file(source, target)
        self.assertIn('temporarily blocked', output.getvalue())
        self.assertEqual(b'new', target.read_bytes())

    def test_a_failed_database_build_releases_the_temporary_file(self):
        import load_item_db as loader
        dump = self.directory / 'broken.dump'
        target = self.directory / 'new.db'
        dump.write_text('CREATE TABLE items(id); INVALID SQL;', encoding='utf-8')
        with mock.patch.object(loader.platform, 'system', return_value='Windows'), self.assertRaises(sqlite3.Error):
            loader._build_db_file(target, dump)
        target.unlink()


class UpdateInventoryTests(TestCase):
    def baseline(self):
        return {'version': 'dofus3', 'integrity': ['ok'], 'tables': {key: 100 for key in ('items', 'stats', 'stats_of_item', 'sets', 'weapon_hits', 'weapon_ap')},
                'stats': {'str': {'name': 'Strength'}}, 'items': {'1': {'id': 1, 'name': 'Sword', 'ankama_id': 40, 'ankama_type': 'equipment'}},
                'legacy_ids': {}, 'spells': {'Iop:1': {'hash': 'old'}}, 'orphaned': {},
                'images': {'problems': {'item:1': {'path': 'missing.png'}}}}

    def test_empty_tables_and_new_stats_are_highlighted(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        after['tables']['weapon_hits'] = 0
        after['stats']['new'] = {'name': 'New characteristic'}
        result = audit.compare(before, after)
        self.assertTrue(any('weapon_hits' in line for line in result['errors']))
        self.assertTrue(any('NOUVELLE STAT' in line for line in result['warnings']))

    def test_reused_item_ids_are_errors_but_a_legacy_alias_is_safe(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        after['items']['1']['ankama_id'] = 99
        self.assertTrue(audit.compare(before, after)['errors'])
        after['items']['2'] = dict(before['items']['1'], id=2)
        after['legacy_ids']['1'] = '2'
        self.assertEqual([], audit.compare(before, after)['errors'])

    def test_preexisting_missing_images_are_distinguished_from_new_ones(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        after['images']['problems']['item:2'] = {'path': 'new-missing.png'}
        result = audit.compare(before, after)
        self.assertEqual(['item:2'], list(result['new_image_problems']))
        self.assertEqual([], result['errors'])

    def test_lost_tables_are_detected_even_when_they_were_empty(self):
        before = self.baseline()
        before['tables']['optional'] = 0
        after = copy.deepcopy(before)
        del after['tables']['optional']
        self.assertTrue(any('optional' in error for error in audit.compare(before, after)['errors']))

    def test_new_source_effects_are_reported_even_if_the_database_drops_them(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        after['source_stats'] = {'New unhandled stat': 3}
        self.assertTrue(any('New unhandled stat' in warning for warning in audit.compare(before, after)['warnings']))

    def test_a_stale_dump_blocks_validation(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        after['dump_errors'] = ['weapon_hits: 0']
        self.assertTrue(any('Dump incohérent' in error for error in audit.compare(before, after)['errors']))

    def test_losing_an_existing_shared_image_is_a_regression(self):
        before = self.baseline()
        before['images']['paths'] = {'spell:2': 'spells/existing.png'}
        after = copy.deepcopy(before)
        after['images']['problems']['spell:2'] = {'path': 'spells/existing.png'}
        self.assertTrue(any('Image existante perdue' in error for error in audit.compare(before, after)['errors']))
