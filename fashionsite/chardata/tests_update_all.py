# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
import copy
import contextlib
import io
import json
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import threading
import time
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

    VERSION_FILE = ('FASHIONISTA_TOUCH_VERSION = "1.74"\nFASHIONISTA_RETRO_VERSION = "1.49"\n'
                    'FASHIONISTA_VERSION = "3.6.11.15"\nFASHIONISTA_BETA_VERSION = "3.7.0.0"\n'
                    'FASHIONISTA_DOFUS2_VERSION = "2.73.3.13"\n'
                    'WATCHED_RETRO_ASSET_DIGEST = "old"\nWATCHED_RETRO_ASSET_COUNT = 10\nLOCAL_EDIT = True\n')
    TARGETS = {'dofus3': '3.6.12.16', 'beta': '3.7.1.1', 'dofus2': '2.73.3.14'}

    def settings(self):
        settings = self.root / 'fashionsite/fashionsite/settings_test.py'
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('', encoding='utf-8')

    def args(self):
        return SimpleNamespace(running_file=self.root / 'RUNNING.md', step_timeout=60)

    def database(self, key, *ids):
        path = audit.database_path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.unlink(missing_ok=True)
        with audit.writable(path) as connection:
            connection.execute('CREATE TABLE items(id INTEGER)')
            connection.executemany('INSERT INTO items VALUES (?)', [(item,) for item in ids])
        return path

    def item_ids(self, key):
        with audit.readonly(audit.database_path(key)) as connection:
            return [row[0] for row in connection.execute('SELECT id FROM items ORDER BY id')]

    def image(self, relative, colour='red'):
        from PIL import Image
        path = audit.STATIC / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new('RGB', (2, 2), colour).save(path)
        return path

    def versions_run(self, keys):
        self.settings()
        (self.root / 'fashionista_version.py').write_text(self.VERSION_FILE, encoding='utf-8')
        audit.DATA.mkdir(parents=True, exist_ok=True)
        for key in keys:
            self.database(key, 1, 2)
            (audit.DATA / ('dofus_constants_%s.py' % key)).write_text('OLD = True\n', encoding='utf-8')
        rows = [{'key': key, 'current': updater.read_metadata()[updater.METADATA[key]],
                 'available': self.TARGETS[key], 'source': {'version': self.TARGETS[key]}} for key in keys]
        return rows, {row['key']: row for row in rows}

    def fake_import(self, command):
        job = updater.read_json(Path(command[-1]))
        key = job['key']
        with audit.writable(audit.database_path(key)) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        (audit.DATA / ('dofus_constants_%s.py' % key)).write_text('NEW = True\n', encoding='utf-8')
        translations = self.root / 'fashionsite/chardata/dynamic_translations.py'
        translations.parent.mkdir(parents=True, exist_ok=True)
        with translations.open('a', encoding='utf-8') as handle:
            handle.write('# %s\n' % key)
        return key

    def execute(self, rows, keys, images, run, by_key, snapshot=None):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), \
                mock.patch.object(updater, 'check_configuration'), \
                mock.patch.object(updater, 'probe', side_effect=lambda key: by_key[key]), \
                mock.patch.object(updater, 'run_command', side_effect=run), \
                mock.patch.object(updater, 'RETRY_DELAY', 0), \
                mock.patch.object(audit, 'snapshot', return_value=snapshot or {}), \
                mock.patch.object(audit, 'compare', return_value={'errors': [], 'warnings': []}):
            code = updater.execute(rows, keys, images, self.args())
        report_dir = next(updater.REPORTS.glob('2*'))
        recap = (report_dir / 'RECAP.md').read_text(encoding='utf-8')
        return code, updater.read_json(report_dir / 'report.json'), recap, output.getvalue()

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
            with self.assertRaisesRegex(ValueError, 'Incomplete archive'):
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
                with self.assertRaisesRegex(ValueError, 'Touch build'):
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
        with self.assertRaisesRegex(ValueError, 'downgrade refused'):
            self.touch_probe(current='1.74.6')

    def test_console_and_report_separate_touch_build_from_assets(self):
        row = dict(self.touch_probe(current='1.74'), images=False)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            updater.show_versions([row])
        report = updater.report_markdown({'status': updater.IMPORTED, 'directory': 'report', 'versions': [row]})
        for rendered in (output.getvalue(), report):
            self.assertIn('Game build available: 1.74.5', rendered)
            self.assertIn('CDN assets: 3.3.6_hash', rendered)
            self.assertNotIn('Importable data: 3.3.6', rendered)
        self.assertIn('4. Dofus Touch (local version: 1.74)', output.getvalue())
        self.assertIn('is not the game build', output.getvalue())
        self.assertNotIn('is not the game build', report)
        self.assertIn('## Dofus Touch: NOT STARTED', report)

    def test_each_game_label_is_written_after_its_import_and_kept_when_tests_fail(self):
        self.settings()
        version_file = self.root / 'fashionista_version.py'
        for key, version in (('dofus3', '3.6.12.16'), ('beta', '3.7.1.1'), ('dofus2', '2.73.3.14'),
                             ('touch', '1.74.5'), ('retro', '1.49.5')):
            for exit_code in (0, 1):
                with self.subTest(key=key, exit_code=exit_code):
                    version_file.write_text(self.VERSION_FILE, encoding='utf-8')
                    row = {'key': key, 'current': updater.read_metadata()[updater.METADATA[key]],
                           'available': version, 'source': {'build': version}}
                    reports = self.root / ('reports-%s-%s' % (key, exit_code))
                    def run(command, log, **kwargs):
                        log.write_text('ok', encoding='utf-8')
                        if log.stem in ('generation', 'weapons', 'django'):
                            self.assertEqual(log.stem != 'weapons', kwargs['django'])
                            self.assertEqual(version, updater.read_metadata()[updater.METADATA[key]])
                            self.assertIn(key, updater.read_json(reports / 'state.json'))
                        return {'exit_code': exit_code if log.stem == 'django' else 0,
                                'log': str(log), 'seconds': .1}
                    with mock.patch.object(updater, 'REPORTS', reports), \
                            mock.patch.object(updater, 'check_configuration'), \
                            mock.patch.object(updater, 'probe', return_value=row), \
                            mock.patch.object(updater, 'run_command', side_effect=run), \
                            mock.patch.object(audit, 'snapshot', return_value={}), \
                            mock.patch.object(audit, 'compare', return_value={'errors': [], 'warnings': []}), \
                            contextlib.redirect_stdout(io.StringIO()):
                        self.assertEqual(2 * exit_code, updater.execute([row], [key], {key: False}, self.args()))
                    self.assertEqual(version, updater.read_metadata()[updater.METADATA[key]])
                    self.assertIn('LOCAL_EDIT = True', version_file.read_text(encoding='utf-8'))
                    self.assertIn(key, updater.read_json(reports / 'state.json'))

    def test_exclusive_work_is_refused_without_removing_someone_elses_marker(self):
        running = self.root / 'RUNNING.md'
        running.write_text('# Work\n## En cours\nother rebuild\n', encoding='utf-8')
        with self.assertRaisesRegex(RuntimeError, 'already running'):
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
        with mock.patch.object(updater, 'process_snapshot', return_value=processes), \
                contextlib.redirect_stdout(io.StringIO()):
            with updater.exclusive(running):
                self.assertIn('pid=%d' % os.getpid(), running.read_text(encoding='utf-8'))
        self.assertFalse((self.root / '.update-data.lock').exists())
        self.assertNotIn('update_all pid=', running.read_text(encoding='utf-8'))

    def test_an_orphaned_running_marker_is_recovered_without_a_lock_file(self):
        running = self.root / 'RUNNING.md'
        running.write_text('## En cours\n\nupdate_all pid=999999 2026-09-22T20:52:15\n', encoding='utf-8')
        processes = [{'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}]
        with mock.patch.object(updater, 'process_snapshot', return_value=processes), \
                contextlib.redirect_stdout(io.StringIO()):
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
                with mock.patch.object(updater, 'process_snapshot', return_value=[own]), \
                        contextlib.redirect_stdout(io.StringIO()):
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
                {'pid': 12, 'parent': 999999, 'name': 'python', 'command': 'update_all.py --worker job.json'},
                {'pid': 13, 'parent': 1, 'name': 'python', 'command': 'update_data_touch.py'},
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

    def test_a_python_program_unrelated_to_the_repository_does_not_keep_the_lock(self):
        marker = 'update_all pid=999999 2026-09-22T20:52:15+02:00'
        lock = self.root / '.update-data.lock'
        running = self.root / 'RUNNING.md'
        own = {'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}
        for process in (
                {'pid': 12, 'parent': 999999, 'name': 'python', 'command': 'python -m pylsp'},
                {'pid': 14, 'parent': 1, 'name': 'python', 'command': ''}):
            with self.subTest(process=process):
                lock.write_text(marker, encoding='utf-8')
                running.write_text('## En cours\n' + marker + '\n', encoding='utf-8')
                with mock.patch.object(updater, 'process_snapshot', return_value=[own, process]), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with updater.exclusive(running):
                        pass
                self.assertFalse(lock.exists())

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
                        mock.patch.object(updater, 'run_command', side_effect=run), \
                        mock.patch.object(updater.sys, 'argv', []), contextlib.redirect_stdout(io.StringIO()):
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
        with self.assertRaisesRegex(ValueError, 'Corrupted backup'):
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

    def test_preserved_mount_looks_follow_the_ankama_id_and_type_through_a_rename(self):
        audit.DATA.mkdir(parents=True)
        before = self.root / 'previous.db'
        after = audit.database_path('dofus3')
        with audit.writable(before) as db:
            db.executescript("CREATE TABLE items(id, ankama_id, ankama_type, name);"
                             "INSERT INTO items VALUES(1, 123, 'mounts', 'Mount'), (2, 123, 'equipment', 'Hat');"
                             "CREATE TABLE mount_looks(item, look); INSERT INTO mount_looks VALUES(1, 'appearance');")
        with audit.writable(after) as db:
            db.executescript("CREATE TABLE items(id, ankama_id, ankama_type, name);"
                             "INSERT INTO items VALUES(7, 123, 'mounts', 'Renamed Mount'), (8, 123, 'equipment', 'Hat');")
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
        with mock.patch.object(updater.importlib, 'import_module', return_value=module), mock.patch.object(updater, 'run_command', side_effect=run), mock.patch.object(updater.sys, 'argv', []), \
                mock.patch.object(updater, 'RETRY_DELAY', 0), contextlib.redirect_stdout(io.StringIO()):
            with self.assertRaisesRegex(RuntimeError, 'Step failed'):
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
            with mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                    mock.patch.object(updater, 'run_command', side_effect=run), \
                    mock.patch.object(updater.sys, 'argv', []), contextlib.redirect_stdout(io.StringIO()):
                updater.worker(job)
            self.assertEqual(1, len(commands))
            if version == 'touch':
                self.assertIn('--skip-images', commands[0])

    def run_worker(self, key, label, command, run, available='3.6.10.0'):
        module = SimpleNamespace(__file__='legacy.py')
        def main():
            module.run_step(label, command)
        module.main = main
        job = self.root / 'job.json'
        updater.write_json(job, {'key': key, 'images': False, 'available': available, 'timeout': 60})
        output = io.StringIO()
        with mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                mock.patch.object(updater, 'run_command', side_effect=run), \
                mock.patch.object(updater.sys, 'argv', []), \
                mock.patch.object(updater.time, 'sleep') as sleep, contextlib.redirect_stdout(output):
            try:
                updater.worker(job)
            except RuntimeError as exc:
                return sleep, output.getvalue(), exc
        return sleep, output.getvalue(), None

    WATCHED_FILE = ('FASHIONISTA_TOUCH_VERSION = "1.74"\nFASHIONISTA_RETRO_VERSION = "1.49"\n'
                    'WATCHED_RETRO_BUILD = "1.49.3.1"\nWATCHED_TOUCH_ASSETS = "3.3.5_old"\n'
                    "WATCHED_RETRO_LANG = {\n    'items': '1260',\n    'spells': '1254',\n}\n"
                    'WATCHED_RETRO_ASSET_DIGEST = "old"\nWATCHED_RETRO_ASSET_COUNT = 10\n')

    def test_an_import_names_its_source_for_the_version_watch(self):
        path = self.root / 'fashionista_version.py'
        path.write_text(self.WATCHED_FILE, encoding='utf-8')
        touch = {'key': 'touch', 'available': '1.74.5', 'images': False,
                 'source': {'build': '1.74.5', 'assets': '3.3.6_new'}}
        retro = {'key': 'retro', 'available': '1.49.5', 'images': True,
                 'source': {'build': '1.49.5.2', 'languages': {'fr': {'items': '1261', 'spells': '1254'}},
                            'image_digest': 'new', 'image_count': 12}}
        with contextlib.redirect_stdout(io.StringIO()):
            updater.set_game_versions([touch, retro])
        metadata = updater.read_metadata()
        self.assertEqual('3.3.6_new', metadata['WATCHED_TOUCH_ASSETS'])
        self.assertEqual('1.49.5.2', metadata['WATCHED_RETRO_BUILD'])
        self.assertEqual({'items': '1261', 'spells': '1254'}, metadata['WATCHED_RETRO_LANG'])
        self.assertEqual(('new', 12), (metadata['WATCHED_RETRO_ASSET_DIGEST'],
                                       metadata['WATCHED_RETRO_ASSET_COUNT']))
        restored = updater.transplant_label(path.read_text(encoding='utf-8'), self.WATCHED_FILE, 'retro')
        path.write_text(restored, encoding='utf-8')
        metadata = updater.read_metadata()
        self.assertEqual(('1.49', '1.49.3.1', 'old'), (metadata['FASHIONISTA_RETRO_VERSION'],
                                                       metadata['WATCHED_RETRO_BUILD'],
                                                       metadata['WATCHED_RETRO_ASSET_DIGEST']))
        self.assertEqual('3.3.6_new', metadata['WATCHED_TOUCH_ASSETS'])

    def test_retro_images_left_alone_keep_the_watched_render_digest(self):
        path = self.root / 'fashionista_version.py'
        path.write_text(self.WATCHED_FILE, encoding='utf-8')
        retro = {'key': 'retro', 'available': '1.49.5', 'images': False,
                 'source': {'build': '1.49.5.2', 'image_digest': 'new', 'image_count': 12}}
        with contextlib.redirect_stdout(io.StringIO()):
            updater.set_game_versions([retro])
        self.assertEqual('old', updater.read_metadata()['WATCHED_RETRO_ASSET_DIGEST'])

    def test_the_real_version_file_holds_every_watched_constant(self):
        import fashionista_version
        for names in updater.WATCHED.values():
            for name in names:
                self.assertTrue(hasattr(fashionista_version, name), name)

    def test_a_step_that_failed_twice_is_not_listed_as_saved_by_its_retry(self):
        retried = {'step': 'item-images', 'exit_code': 0, 'retried': {'error': 'x', 'log': 'l'}}
        failed = {'step': 'items/dump', 'exit_code': 1, 'retried': {'error': 'x', 'log': 'l'}}
        row = {'key': 'wakfu', 'status': updater.RESTORED, 'steps': [retried, failed]}
        block = '\n'.join(updater.version_block(row))
        self.assertIn('on the second attempt: ' + updater.step_title('item-images'), block)
        self.assertNotIn(updater.step_title('items/dump'), block.split('on the second attempt')[1])

    def test_a_network_step_is_tried_again_once_after_20_seconds(self):
        calls = []
        def run(command, log, *args, **kwargs):
            calls.append(command)
            log.write_text('Failed to retrieve equipment data for fr.\n' if len(calls) == 1 else 'ok\n', encoding='utf-8')
            return {'exit_code': 0, 'log': str(log), 'seconds': .1}
        sleep, output, error = self.run_worker('dofus3', 'items/download', ['python', 'get_equipments.py'], run)
        self.assertIsNone(error)
        self.assertEqual(2, len(calls))
        sleep.assert_called_once_with(20)
        step = updater.read_json(self.root / 'dofus3-steps.json')[0]
        self.assertEqual(0, step['exit_code'])
        self.assertIn('Failed to retrieve', step['retried']['error'])
        self.assertIn('Failed to retrieve', Path(step['retried']['log']).read_text(encoding='utf-8'))
        self.assertIn('Second attempt', Path(step['log']).read_text(encoding='utf-8'))
        self.assertIn('trying again in 20 s', output)

    def test_a_local_step_or_a_timed_out_download_is_not_tried_again(self):
        for label, failure in (('items/transform', None), ('items/download', TimeoutError('Timed out'))):
            with self.subTest(label=label):
                calls = []
                def run(command, log, *args, **kwargs):
                    calls.append(command)
                    if failure:
                        raise failure
                    log.write_text('Traceback (most recent call last):\nValueError: bad\n', encoding='utf-8')
                    return {'exit_code': 1, 'log': str(log)}
                sleep, output, error = self.run_worker('dofus3', label, ['python', 'script.py'], run)
                self.assertRegex(str(error), 'Step failed')
                self.assertEqual(1, len(calls))
                sleep.assert_not_called()

    def test_wakfu_spells_are_harvested_for_the_build_being_imported(self):
        commands = []
        def run(command, log, *args, **kwargs):
            commands.append(command)
            log.write_text('ok\n', encoding='utf-8')
            return {'exit_code': 0, 'log': str(log)}
        self.run_worker('wakfu', 'data/spells fr', ['python', 'itemscraper/get_spells_wakfu.py', '--lang', 'fr'],
                        run, available='1.93.1.62')
        self.assertEqual(['--version', '1.93.1.62'], commands[0][-2:])

    def test_unknown_stats_are_reported_without_zero_count_noise(self):
        self.assertEqual(['Missing translation for New stat'], updater.log_notices([
            'Missing translation for New stat', '0 unresolved', 'No warnings', 'Missing translation for New stat']))

    def test_a_failed_pipeline_is_restored_before_releasing_the_lock(self):
        self.settings()
        version_file = self.root / 'fashionista_version.py'
        original = version_file.read_bytes()
        row = {'key': 'dofus3', 'current': '3.6.9.0', 'available': '3.6.10.0', 'source': {'version': '3.6.10.0'}}
        def run(command, log, **kwargs):
            version_file.write_text('FASHIONISTA_VERSION = "3.6.10.0"', encoding='utf-8')
            log.write_text('failed', encoding='utf-8')
            return {'exit_code': 1, 'log': str(log), 'seconds': .1}
        original_restore = audit.restore_runtime
        def restore(manifest, source, **kwargs):
            self.assertTrue((self.root / '.update-data.lock').exists())
            return original_restore(manifest, source, **kwargs)
        with mock.patch.object(audit, 'restore_runtime', side_effect=restore):
            code, report, recap, output = self.execute([row], ['dofus3'], {'dofus3': False}, run, {'dofus3': row})
        self.assertEqual(1, code)
        self.assertEqual(original, version_file.read_bytes())
        self.assertFalse((self.root / '.update-data.lock').exists())
        self.assertFalse((updater.REPORTS / 'state.json').exists())
        self.assertEqual('FAILED', report['status'])
        self.assertEqual('FAILED, RESTORED', report['versions'][0]['status'])
        self.assertEqual([], report['checks'])

    def test_a_failed_version_is_restored_and_the_next_versions_still_run(self):
        rows, by_key = self.versions_run(['dofus3', 'beta', 'dofus2'])
        imported = []
        def run(command, log, **kwargs):
            log.write_text('ok', encoding='utf-8')
            if '--worker' not in command:
                return {'exit_code': 0, 'log': str(log), 'seconds': .1}
            key = self.fake_import(command)
            imported.append(key)
            if key == 'beta':
                updater.write_json(log.parent / 'beta-steps.json', [
                    {'step': 'items/load-db', 'exit_code': 1, 'log': 'load.log', 'error': 'disk I/O error'}])
                return {'exit_code': 1, 'log': str(log)}
            return {'exit_code': 0, 'log': str(log)}
        code, report, recap, output = self.execute(rows, ['dofus3', 'beta', 'dofus2'],
                                                   dict.fromkeys(by_key, False), run, by_key)
        self.assertEqual(1, code)
        self.assertEqual(['dofus3', 'beta', 'dofus2'], imported)
        self.assertEqual(['IMPORTED', 'FAILED, RESTORED', 'IMPORTED'], [row['status'] for row in report['versions']])
        self.assertEqual('PARTLY IMPORTED', report['status'])
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))
        self.assertEqual([1, 2], self.item_ids('beta'))
        self.assertEqual([1, 2, 99], self.item_ids('dofus2'))
        self.assertEqual('OLD = True\n', (audit.DATA / 'dofus_constants_beta.py').read_text(encoding='utf-8'))
        metadata = updater.read_metadata()
        self.assertEqual(('3.6.12.16', '3.7.0.0', '2.73.3.14'), (metadata['FASHIONISTA_VERSION'],
                         metadata['FASHIONISTA_BETA_VERSION'], metadata['FASHIONISTA_DOFUS2_VERSION']))
        self.assertEqual(['dofus2', 'dofus3'], sorted(updater.read_json(updater.REPORTS / 'state.json')))
        self.assertIn('## Dofus 3 Beta: FAILED, RESTORED', recap)
        self.assertIn('Cause: Loading the database: disk I/O error', recap)
        self.assertIn('Dofus 3 Beta: FAILED, RESTORED\n  Cause: Loading the database: disk I/O error', output)
        self.assertTrue(recap.startswith('# PARTLY IMPORTED\n'))
        self.assertNotIn('Restore to finish', recap)

    def test_a_test_suite_failure_keeps_the_data_and_lists_the_failing_tests(self):
        rows, by_key = self.versions_run(['dofus3'])
        failures = ['FAIL: test_icons (chardata.tests.ItemDatabaseIntegrityTests.test_icons)',
                    'ERROR: test_shiny (chardata.tests_temporix.TheReviewOfTheModeTests.test_shiny)']
        def run(command, log, **kwargs):
            if '--worker' in command:
                self.fake_import(command)
            log.write_text('\n'.join(failures + ['FAILED (failures=1, errors=1)']) if log.stem == 'django' else 'ok',
                           encoding='utf-8')
            return {'exit_code': int(log.stem == 'django'), 'log': str(log), 'seconds': .1}
        code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False}, run, by_key)
        self.assertEqual(2, code)
        self.assertEqual('IMPORTED, TESTS TO REVIEW', report['status'])
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))
        self.assertEqual('3.6.12.16', updater.read_metadata()['FASHIONISTA_VERSION'])
        for failure in failures:
            self.assertIn(failure, recap)
        self.assertIn(str(next(updater.REPORTS.glob('2*')) / 'django.log'), recap)
        self.assertIn('To undo this update: `py update_all.py --restore "%s"`\n' % report['directory'], recap)
        self.assertNotIn('Next steps', recap)
        self.assertIn('Full Django suite: 2 failing tests (ItemDatabaseIntegrityTests.test_icons, '
                      'TheReviewOfTheModeTests.test_shiny)', output)

    def test_a_generation_failure_restores_only_the_version_it_names(self):
        rows, by_key = self.versions_run(['dofus3', 'beta'])
        checks = []
        def run(command, log, **kwargs):
            if '--worker' in command:
                self.fake_import(command)
            else:
                checks.append(log.stem)
            text = 'ok'
            if log.stem == 'generation':
                text = ("FAIL: test_each_dofus_version_can_generate_and_render_a_build (chardata.tests_update_generation."
                        "UpdateGenerationTests.test_each_dofus_version_can_generate_and_render_a_build) (version='dofus3')")
            log.write_text(text, encoding='utf-8')
            return {'exit_code': int(log.stem == 'generation'), 'log': str(log), 'seconds': .1}
        code, report, recap, output = self.execute(rows, ['dofus3', 'beta'], {'dofus3': False, 'beta': False},
                                                   run, by_key)
        self.assertEqual(1, code)
        self.assertEqual(['generation', 'generation-after-restore', 'weapons', 'django'], checks)
        self.assertEqual(['FAILED, RESTORED', 'IMPORTED'], [row['status'] for row in report['versions']])
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual([1, 2, 99], self.item_ids('beta'))
        self.assertEqual('OLD = True\n', (audit.DATA / 'dofus_constants_dofus3.py').read_text(encoding='utf-8'))
        self.assertEqual('NEW = True\n', (audit.DATA / 'dofus_constants_beta.py').read_text(encoding='utf-8'))
        metadata = updater.read_metadata()
        self.assertEqual(('3.6.11.15', '3.7.1.1'), (metadata['FASHIONISTA_VERSION'], metadata['FASHIONISTA_BETA_VERSION']))
        self.assertIn('LOCAL_EDIT = True', (self.root / 'fashionista_version.py').read_text(encoding='utf-8'))
        self.assertEqual(['beta'], list(updater.read_json(updater.REPORTS / 'state.json')))
        self.assertEqual(['fashionsite/chardata/dynamic_translations.py'], report['versions'][0]['kept_shared'])
        self.assertIn('Restored versions: Dofus 3', recap)
        self.assertIn('New check after the restore: OK', recap)
        self.assertIn('the site can no longer generate a build', recap)
        self.assertNotIn('generate a set', recap)
        self.assertEqual([], updater.checks_to_review(report))

    def test_two_versions_that_cannot_build_are_restored_last_first(self):
        rows, by_key = self.versions_run(['dofus3', 'beta'])
        translations = self.root / 'fashionsite/chardata/dynamic_translations.py'
        start = translations.read_text(encoding='utf-8') if translations.exists() else None
        def run(command, log, **kwargs):
            if '--worker' in command:
                self.fake_import(command)
            text = 'ok'
            if log.stem == 'generation':
                text = '\n'.join(
                    "FAIL: test_each_dofus_version_can_generate_and_render_a_build (chardata.tests_update_generation."
                    "UpdateGenerationTests.test_each_dofus_version_can_generate_and_render_a_build) (version='%s')"
                    % key for key in ('dofus3', 'beta'))
            log.write_text(text, encoding='utf-8')
            return {'exit_code': int(log.stem == 'generation'), 'log': str(log), 'seconds': .1}
        code, report, recap, output = self.execute(rows, ['dofus3', 'beta'], {'dofus3': False, 'beta': False},
                                                   run, by_key)
        self.assertEqual(['FAILED, RESTORED', 'FAILED, RESTORED'], [row['status'] for row in report['versions']])
        self.assertEqual([[], []], [row.get('kept_shared', []) for row in report['versions']])
        now = translations.read_text(encoding='utf-8') if translations.exists() else None
        self.assertEqual(start, now)
        self.assertIn('Build generation', output)

    def test_ctrl_c_restores_the_version_in_progress_and_stops(self):
        rows, by_key = self.versions_run(['dofus3', 'beta'])
        started = []
        def run(command, log, **kwargs):
            started.append(self.fake_import(command))
            raise KeyboardInterrupt
        code, report, recap, output = self.execute(rows, ['dofus3', 'beta'], {'dofus3': False, 'beta': False},
                                                   run, by_key)
        self.assertEqual(130, code)
        self.assertEqual(['dofus3'], started)
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual('INTERRUPTED', report['status'])
        self.assertEqual('FAILED, RESTORED', report['versions'][0]['status'])
        self.assertFalse((self.root / '.update-data.lock').exists())

    def test_a_failed_version_gets_its_lost_images_back_and_keeps_new_downloads(self):
        rows, by_key = self.versions_run(['dofus3'])
        lost = self.image('chardata/items/60x60/Old-60-60.png')
        updated = self.image('chardata/items/60x60/Kept-60-60.png')
        before = {'images': {'paths': {'item:1': 'chardata/items/60x60/Old-60-60.png'}, 'problems': {}}}
        def run(command, log, **kwargs):
            self.fake_import(command)
            lost.unlink()
            self.image('chardata/items/60x60/Kept-60-60.png', 'blue')
            self.image('chardata/items/60x60/New-60-60.png', 'green')
            return {'exit_code': 1, 'log': str(log), 'error': 'download failed'}
        code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': True}, run, by_key, before)
        self.assertEqual(1, code)
        self.assertTrue(lost.is_file())
        self.assertIsNone(audit.image_problem(lost))
        self.assertTrue((audit.STATIC / 'chardata/items/60x60/New-60-60.png').is_file())
        from PIL import Image
        with Image.open(updated) as image:
            self.assertEqual((0, 0, 255), image.getpixel((0, 0)))
        self.assertEqual(['fashionsite/chardata/static/chardata/items/60x60/Old-60-60.png'],
                         report['versions'][0]['images_restored'])
        changed = updater.read_json(next(updater.REPORTS.glob('2*')) / 'images-changed.json')
        self.assertIn('fashionsite/chardata/static/chardata/items/60x60/New-60-60.png', changed)
        self.assertNotIn('fashionsite/chardata/static/chardata/items/60x60/Old-60-60.png', changed)

    def test_a_locked_database_is_refused_before_any_import(self):
        rows, by_key = self.versions_run(['dofus3'])
        holder = sqlite3.connect(audit.database_path('dofus3'))
        self.addCleanup(holder.close)
        holder.execute('BEGIN EXCLUSIVE')
        run = mock.Mock()
        code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False}, run, by_key)
        self.assertEqual(1, code)
        run.assert_not_called()
        self.assertEqual([], report['versions'])
        self.assertIn('Database open in another program', output)
        self.assertIn(str(audit.database_path('dofus3')), recap)

    def test_an_idle_connection_counts_as_a_busy_database_on_windows(self):
        if os.name != 'nt':
            self.skipTest('Windows file sharing')
        path = self.database('dofus3', 1)
        self.assertFalse(updater.database_in_use(path))
        idle = sqlite3.connect(path)
        idle.execute('SELECT * FROM items').fetchall()
        self.assertTrue(updater.database_in_use(path))
        idle.close()
        self.assertFalse(updater.database_in_use(path))

    def test_restore_goes_past_a_locked_file_and_reports_it(self):
        names = ['fashionsite/chardata/spell_reference/touch.json', 'fashionsite/chardata/spell_states/touch.json',
                 'fashionista_version.py']
        for name in names:
            (self.root / name).parent.mkdir(parents=True, exist_ok=True)
            (self.root / name).write_text('old ' + name, encoding='utf-8')
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['touch'], False, saved)
        for name in names:
            (self.root / name).write_text('new', encoding='utf-8')
        attempts = []
        replace = audit.replace_file
        pause = time.sleep
        def locked(source, destination, **kwargs):
            destination = Path(destination)
            attempts.append(destination)
            if destination.parent.name == 'spell_reference' or (
                    destination.parent.name == 'spell_states' and attempts.count(destination) < 3):
                raise PermissionError('locked')
            replace(source, destination, **kwargs)
        with mock.patch.object(audit, 'replace_file', side_effect=locked), \
                mock.patch.object(audit.time, 'sleep', side_effect=lambda seconds: pause(.05)):
            unrestored = audit.restore_runtime(manifest, saved, wait=1)
        self.assertEqual(['fashionsite/chardata/spell_reference/touch.json'], unrestored)
        self.assertEqual('new', (self.root / names[0]).read_text(encoding='utf-8'))
        for name in names[1:]:
            self.assertEqual('old ' + name, (self.root / name).read_text(encoding='utf-8'))
        self.assertEqual([], list(self.root.rglob('*.restore-tmp')))

    def test_the_restore_command_finishes_a_partial_restore(self):
        (self.root / 'fashionista_version.py').write_text(self.VERSION_FILE, encoding='utf-8')
        directory = updater.REPORTS / 'run'
        self.database('dofus3', 1, 2)
        self.database('beta', 1, 2)
        image = self.image('chardata/spells/Pression.png')
        updater.write_json(updater.REPORTS / 'state.json', {'dofus3': {'source': 'old'}})
        updater.write_json(directory / 'state-before.json', {'dofus3': {'source': 'old'}})
        audit.backup_runtime([], True, directory / 'images', shared=False)
        audit.backup_runtime(['dofus3'], False, directory / 'dofus3')
        with audit.writable(audit.database_path('dofus3')) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        (self.root / 'fashionista_version.py').write_text('FASHIONISTA_VERSION = "3.6.12.16"\n', encoding='utf-8')
        audit.backup_runtime(['beta'], False, directory / 'beta')
        with audit.writable(audit.database_path('beta')) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        self.image('chardata/spells/Pression.png', 'blue')
        self.image('chardata/spells/Added.png')
        updater.write_json(updater.REPORTS / 'state.json', {'dofus3': {'source': 'new', 'report': str(directory)},
                                                            'beta': {'source': 'new', 'report': str(directory)}})
        with mock.patch.object(audit, 'replace_file', side_effect=PermissionError('locked')):
            partial = audit.restore_runtime(updater.read_json(directory / 'beta/manifest.json'), directory / 'beta',
                                            wait=0)
        self.assertIn('fashionistapulp/fashionistapulp/items_beta.db', partial)
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code = updater.main(['--restore', str(directory), '--running-file', str(self.root / 'RUNNING.md')])
        self.assertEqual(0, code, output.getvalue())
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual([1, 2], self.item_ids('beta'))
        self.assertEqual(self.VERSION_FILE, (self.root / 'fashionista_version.py').read_text(encoding='utf-8'))
        from PIL import Image
        with Image.open(image) as restored:
            self.assertEqual((255, 0, 0), restored.getpixel((0, 0)))
        self.assertFalse((audit.STATIC / 'chardata/spells/Added.png').exists())
        self.assertEqual({'dofus3': {'source': 'old'}}, updater.read_json(updater.REPORTS / 'state.json'))
        self.assertFalse((self.root / '.update-data.lock').exists())

    def test_a_moving_source_stops_before_any_pipeline_command(self):
        settings = self.root / 'fashionsite/fashionsite/settings_test.py'
        settings.parent.mkdir(parents=True)
        settings.write_text('', encoding='utf-8')
        row = {'key': 'dofus3', 'current': 'old', 'available': 'new', 'source': {'version': 'new'}}
        args = SimpleNamespace(running_file=self.root / 'RUNNING.md', step_timeout=60)
        with mock.patch.object(updater, 'check_configuration'), \
                mock.patch.object(updater, 'probe', return_value={'source': {'version': 'newer'}}), \
                mock.patch.object(updater, 'run_command') as run, mock.patch.object(audit, 'snapshot', return_value={}), \
                contextlib.redirect_stdout(io.StringIO()):
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
        with mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                mock.patch.object(updater, 'run_command') as run, \
                mock.patch.object(audit, 'preserve_table') as preserve, \
                mock.patch.object(updater.sys, 'argv', []), contextlib.redirect_stdout(io.StringIO()):
            updater.worker(job)
        run.assert_not_called()
        preserve.assert_called_once()
        steps = updater.read_json(self.root / 'dofus3-steps.json')
        self.assertEqual(2, len(steps))
        self.assertTrue(all(step['warning'] and step['kept'] for step in steps))

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
        self.assertIn('Dofus 3: FAILED, RESTORED\n  Cause: Creating the SQL dump: ' + error, output.getvalue())

    def restore(self, *arguments):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = updater.main(['--restore', *map(str, arguments), '--running-file', str(self.root / 'RUNNING.md')])
        return code, output.getvalue()

    def succeed(self, command, log, **kwargs):
        log.write_text('ok', encoding='utf-8')
        if '--worker' in command:
            self.fake_import(command)
        return {'exit_code': 0, 'log': str(log), 'seconds': .1}

    def test_restoring_a_database_also_removes_its_journal_files(self):
        database = self.database('dofus3', 1, 2)
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['dofus3'], False, saved)
        with audit.writable(database) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        sidecars = [database.with_name(database.name + suffix) for suffix in ('-journal', '-wal', '-shm')]
        for sidecar in sidecars:
            sidecar.write_bytes(b'hot')
        self.assertEqual([], audit.restore_runtime(manifest, saved, wait=0))
        self.assertEqual([], [path for path in sidecars if path.exists()])
        self.assertEqual([1, 2], self.item_ids('dofus3'))

    def test_a_locked_journal_leaves_its_database_unrestored(self):
        database = self.database('dofus3', 1, 2)
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['dofus3'], False, saved)
        with audit.writable(database) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        journal = database.with_name(database.name + '-journal')
        journal.write_bytes(b'hot')
        replace = os.replace
        def locked(source, destination):
            if Path(source) == journal:
                raise PermissionError('locked')
            return replace(source, destination)
        with mock.patch.object(audit.os, 'replace', locked):
            unrestored = audit.restore_runtime(manifest, saved, wait=0)
        self.assertEqual(['fashionistapulp/fashionistapulp/items.db'], unrestored)
        self.assertEqual(b'hot', journal.read_bytes())
        journal.unlink()
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))

    def test_a_database_that_cannot_be_replaced_keeps_its_journal(self):
        database = self.database('dofus3', 1, 2)
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['dofus3'], False, saved)
        with audit.writable(database) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        journal = database.with_name(database.name + '-journal')
        journal.write_bytes(b'hot')
        with mock.patch.object(audit, 'replace_file', side_effect=PermissionError('locked')):
            unrestored = audit.restore_runtime(manifest, saved, wait=0)
        self.assertEqual(['fashionistapulp/fashionistapulp/items.db'], unrestored)
        self.assertEqual(b'hot', journal.read_bytes())
        self.assertEqual([], list(database.parent.glob('*.restore-aside')))

    def test_the_lock_names_the_run_and_a_marker_covers_each_import(self):
        rows, by_key = self.versions_run(['dofus3'])
        seen = []
        def run(command, log, **kwargs):
            if '--worker' in command:
                seen.append(((self.root / '.update-data.lock').read_text(encoding='utf-8'),
                             updater.importing_path(log.parent, 'dofus3').exists()))
            return self.succeed(command, log)
        code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False}, run, by_key)
        self.assertEqual(0, code)
        self.assertTrue(seen[0][0].endswith(' run=%s' % report['directory']))
        self.assertTrue(seen[0][1])
        self.assertFalse(updater.importing_path(Path(report['directory']), 'dofus3').exists())

    def test_an_import_cut_short_blocks_the_next_launch_until_its_version_is_restored(self):
        rows, by_key = self.versions_run(['dofus3'])
        crashed = updater.REPORTS / 'crashed-run'
        audit.backup_runtime(['dofus3'], False, crashed / 'dofus3')
        updater.write_json(crashed / 'state-before.json', {})
        with audit.writable(audit.database_path('dofus3')) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        updater.importing_path(crashed, 'dofus3').write_text('update_all pid=999999\n', encoding='utf-8')
        (self.root / '.update-data.lock').write_text(
            'update_all pid=999999 2026-09-24T03:00:00+02:00 run=%s' % crashed, encoding='utf-8')
        own = [{'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}]
        run = mock.Mock()
        with mock.patch.object(updater, 'process_snapshot', return_value=own):
            code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False}, run, by_key)
        command = 'py update_all.py --restore "%s" --versions dofus3' % crashed
        self.assertEqual(1, code)
        run.assert_not_called()
        self.assertIn(command, recap)
        self.assertIn(command, output)
        self.assertIn('backups kept: ' + str(crashed), output)
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))
        code, output = self.restore(crashed, '--versions', 'dofus3')
        self.assertEqual(0, code, output)
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual({}, updater.pending_imports())

    def imported_pair(self):
        rows, by_key = self.versions_run(['dofus3', 'beta'])
        code, report, recap, output = self.execute(rows, ['dofus3', 'beta'], {'dofus3': False, 'beta': False},
                                                   self.succeed, by_key)
        self.assertEqual(0, code, output)
        return Path(report['directory'])

    def test_a_scoped_restore_of_the_last_version_leaves_the_earlier_one(self):
        directory = self.imported_pair()
        code, output = self.restore(directory, '--versions', 'beta')
        self.assertEqual(0, code, output)
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))
        self.assertEqual([1, 2], self.item_ids('beta'))
        metadata = updater.read_metadata()
        self.assertEqual(('3.6.12.16', '3.7.0.0'), (metadata['FASHIONISTA_VERSION'], metadata['FASHIONISTA_BETA_VERSION']))
        self.assertEqual(['dofus3'], list(updater.read_json(updater.REPORTS / 'state.json')))
        self.assertEqual('NEW = True\n', (audit.DATA / 'dofus_constants_dofus3.py').read_text(encoding='utf-8'))
        self.assertEqual('OLD = True\n', (audit.DATA / 'dofus_constants_beta.py').read_text(encoding='utf-8'))

    def test_a_scoped_restore_of_an_earlier_version_keeps_what_a_later_one_wrote(self):
        directory = self.imported_pair()
        code, output = self.restore(directory, '--versions', 'dofus3')
        self.assertEqual(0, code, output)
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual([1, 2, 99], self.item_ids('beta'))
        metadata = updater.read_metadata()
        self.assertEqual(('3.6.11.15', '3.7.1.1'), (metadata['FASHIONISTA_VERSION'], metadata['FASHIONISTA_BETA_VERSION']))
        self.assertIn('LOCAL_EDIT = True', (self.root / 'fashionista_version.py').read_text(encoding='utf-8'))
        self.assertEqual('OLD = True\n', (audit.DATA / 'dofus_constants_dofus3.py').read_text(encoding='utf-8'))
        self.assertEqual(['beta'], list(updater.read_json(updater.REPORTS / 'state.json')))
        self.assertIn('Files kept, also changed by a newer version: '
                      'fashionsite/chardata/dynamic_translations.py', output)

    def test_an_incomplete_restore_stops_the_run_and_names_only_its_version(self):
        rows, by_key = self.versions_run(['dofus3', 'beta', 'dofus2'])
        def run(command, log, **kwargs):
            result = self.succeed(command, log)
            if '--worker' in command and updater.read_json(Path(command[-1]))['key'] == 'beta':
                return dict(result, exit_code=1, error='download failed')
            return result
        original = audit.restore_runtime
        def restore(manifest, source, **kwargs):
            locked = ['fashionistapulp/fashionistapulp/items_beta.db'] if source.name == 'beta' else []
            return original(manifest, source, **kwargs) + locked
        with mock.patch.object(audit, 'restore_runtime', side_effect=restore):
            code, report, recap, output = self.execute(rows, ['dofus3', 'beta', 'dofus2'],
                                                       dict.fromkeys(by_key, False), run, by_key)
        self.assertEqual(1, code)
        self.assertEqual(['IMPORTED', 'RESTORE INCOMPLETE', 'NOT STARTED'],
                         [row['status'] for row in report['versions']])
        self.assertIn('the restore of Dofus 3 Beta is incomplete', report['versions'][2]['cause'])
        self.assertEqual([1, 2], self.item_ids('dofus2'))
        self.assertEqual([], report['checks'])
        self.assertIn('Tests not run: a restore is incomplete', recap)
        command = 'py update_all.py --restore "%s" --versions beta`' % report['directory']
        self.assertIn(command, recap)
        self.assertIn(command[:-1] + '\n', output)
        self.assertIn('To undo this update: `py update_all.py --restore "%s"`' % report['directory'], recap)
        directory = Path(report['directory'])
        self.assertEqual(['beta.importing'], sorted(path.name for path in directory.glob('*.importing')))

    def test_an_interrupted_restore_still_gives_the_command_to_finish_it(self):
        rows, by_key = self.versions_run(['dofus3'])
        def run(command, log, **kwargs):
            self.fake_import(command)
            raise KeyboardInterrupt
        with mock.patch.object(audit, 'restore_runtime', side_effect=KeyboardInterrupt):
            code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False}, run, by_key)
        self.assertEqual(130, code)
        self.assertEqual('RESTORE INCOMPLETE', report['versions'][0]['status'])
        self.assertEqual([], report['versions'][0]['unrestored'])
        command = 'py update_all.py --restore "%s" --versions dofus3' % report['directory']
        self.assertIn(command, recap)
        self.assertIn(command, output)

    def test_generation_runs_again_after_a_restore_and_what_still_fails_is_to_review(self):
        rows, by_key = self.versions_run(['dofus3', 'beta'])
        failures = {'generation': 'dofus3', 'generation-after-restore': 'beta'}
        def run(command, log, **kwargs):
            result = self.succeed(command, log)
            if log.stem in failures:
                log.write_text("FAIL: test_x (chardata.tests_update_generation.UpdateGenerationTests.test_x)"
                               " (version='%s')" % failures[log.stem], encoding='utf-8')
                return dict(result, exit_code=1)
            return result
        code, report, recap, output = self.execute(rows, ['dofus3', 'beta'], {'dofus3': False, 'beta': False},
                                                   run, by_key)
        check = report['checks'][0]
        self.assertEqual(['FAILED, RESTORED', 'IMPORTED'], [row['status'] for row in report['versions']])
        self.assertEqual(['dofus3'], check['restored'])
        self.assertEqual(1, check['after_restore']['exit_code'])
        self.assertEqual([check], updater.checks_to_review(report))
        self.assertEqual('PARTLY IMPORTED, TESTS TO REVIEW', report['status'])
        self.assertIn('New check after the restore: FAILED', recap)
        self.assertIn("1 failing test (UpdateGenerationTests.test_x (version='beta'))", output)
        self.assertEqual([1, 2, 99], self.item_ids('beta'))

    def test_a_dead_launcher_pid_reused_by_another_program_does_not_keep_the_lock(self):
        marker = 'update_all pid=999999 2026-09-22T20:52:15+02:00'
        lock = self.root / '.update-data.lock'
        running = self.root / 'RUNNING.md'
        own = {'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}
        for process in ({'pid': 999999, 'parent': 1, 'name': 'chrome.exe', 'command': 'chrome.exe --type=renderer'},
                        {'pid': 55, 'parent': 999999, 'name': 'conhost.exe', 'command': 'conhost.exe 0x4'}):
            with self.subTest(process=process):
                lock.write_text(marker, encoding='utf-8')
                running.write_text('## En cours\n' + marker + '\n', encoding='utf-8')
                with mock.patch.object(updater, 'process_snapshot', return_value=[own, process]), \
                        contextlib.redirect_stdout(io.StringIO()):
                    with updater.exclusive(running):
                        self.assertIn('pid=%d' % os.getpid(), lock.read_text(encoding='utf-8'))
                self.assertFalse(lock.exists())

    def test_a_running_dev_server_keeps_the_lock_and_says_what_to_close(self):
        marker = 'update_all pid=999999 2026-09-22T20:52:15+02:00'
        lock = self.root / '.update-data.lock'
        lock.write_text(marker, encoding='utf-8')
        own = {'pid': os.getpid(), 'parent': 0, 'name': 'python', 'command': 'tests'}
        server = {'pid': 77, 'parent': 1, 'name': 'python.exe', 'command': 'python manage.py runserver'}
        with mock.patch.object(updater, 'process_snapshot', return_value=[own, server]):
            with self.assertRaisesRegex(RuntimeError, r'pid 77: python manage\.py runserver\)\. Close it '
                                                      r'\(the dev server included\), then run update_all\.py again'):
                with updater.exclusive(self.root / 'RUNNING.md'):
                    self.fail('lock taken')
        self.assertEqual(marker, lock.read_text(encoding='utf-8'))

    def test_restoring_a_run_older_than_the_last_import_needs_force(self):
        (self.root / 'fashionista_version.py').write_text(self.VERSION_FILE, encoding='utf-8')
        self.database('dofus3', 1, 2)
        older = updater.REPORTS / '20260923T100000000000-1'
        newer = updater.REPORTS / '20260924T100000000000-2'
        audit.backup_runtime(['dofus3'], False, older / 'dofus3')
        updater.write_json(older / 'state-before.json', {})
        newer.mkdir(parents=True)
        with audit.writable(audit.database_path('dofus3')) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        updater.write_json(updater.REPORTS / 'state.json', {'dofus3': {'source': 'new', 'report': str(newer)}})
        code, output = self.restore(older)
        self.assertEqual(1, code)
        self.assertIn('Dofus 3: a newer run imported this version: ' + str(newer), output)
        self.assertIn('--force', output)
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))
        code, output = self.restore(older, '--force')
        self.assertEqual(0, code, output)
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual({}, updater.read_json(updater.REPORTS / 'state.json'))

    def test_a_newer_run_that_imported_another_version_also_needs_force(self):
        (self.root / 'fashionista_version.py').write_text(self.VERSION_FILE, encoding='utf-8')
        self.database('dofus3', 1, 2)
        older = updater.REPORTS / '20260923T100000000000-1'
        newer = updater.REPORTS / '20260924T100000000000-2'
        audit.backup_runtime(['dofus3'], False, older / 'dofus3')
        updater.write_json(older / 'state-before.json', {})
        newer.mkdir(parents=True)
        with audit.writable(audit.database_path('dofus3')) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        updater.write_json(updater.REPORTS / 'state.json', {
            'dofus3': {'source': 'old', 'report': str(older)},
            'beta': {'source': 'new', 'report': str(newer)}})
        code, output = self.restore(older)
        self.assertEqual(1, code)
        self.assertIn('Dofus 3 Beta: a newer run imported this version: ' + str(newer),
                      output)
        self.assertEqual([1, 2, 99], self.item_ids('dofus3'))

    def test_restore_reports_a_missing_backup_file_and_still_restores_the_rest(self):
        (self.root / 'fashionista_version.py').write_text(self.VERSION_FILE, encoding='utf-8')
        self.database('dofus3', 1, 2)
        reference = self.root / 'fashionsite/chardata/spell_reference/dofus3.json'
        reference.parent.mkdir(parents=True)
        reference.write_text('old', encoding='utf-8')
        directory = updater.REPORTS / 'run'
        updater.write_json(directory / 'state-before.json', {})
        audit.backup_runtime(['dofus3'], False, directory / 'dofus3')
        with audit.writable(audit.database_path('dofus3')) as connection:
            connection.execute('INSERT INTO items VALUES (99)')
        reference.write_text('new', encoding='utf-8')
        updater.write_json(updater.REPORTS / 'state.json', {'dofus3': {'source': 'new', 'report': str(directory)}})
        (directory / 'dofus3/fashionsite/chardata/spell_reference/dofus3.json').unlink()
        code, output = self.restore(directory)
        self.assertEqual(1, code)
        self.assertIn('Files not restored:\n  fashionsite/chardata/spell_reference/dofus3.json', output)
        self.assertIn('--restore "%s" --versions dofus3' % directory.resolve(), output)
        self.assertEqual([1, 2], self.item_ids('dofus3'))
        self.assertEqual({}, updater.read_json(updater.REPORTS / 'state.json'))

    def test_restore_errors_are_reported_without_a_traceback(self):
        directory = updater.REPORTS / 'run'
        audit.backup_runtime(['dofus3'], False, directory / 'dofus3')
        (directory / 'dofus3/fashionista_version.py').write_text('damaged', encoding='utf-8')
        code, output = self.restore(directory)
        self.assertEqual(1, code)
        self.assertIn('Restore failed: Corrupted backup: fashionista_version.py', output)
        with updater.update_guard():
            code, output = self.restore(directory)
        self.assertEqual(1, code)
        self.assertIn('Restore failed: Another update holds the lock', output)
        code, output = self.restore(directory, '--versions', 'dofus4')
        self.assertIn('Restore failed: Unknown choice: dofus4', output)
        self.assertNotIn('Traceback', output)

    def test_ctrl_c_in_the_final_phase_still_releases_the_lock_and_writes_the_report(self):
        for target in ('record_changed_images', 'remove_running_marker'):
            with self.subTest(target=target):
                rows, by_key = self.versions_run(['dofus3'])
                (self.root / 'RUNNING.md').write_text('## En cours\n(rien)\n', encoding='utf-8')
                with mock.patch.object(updater, 'REPORTS', self.root / ('reports-' + target)), \
                        mock.patch.object(updater, target, side_effect=KeyboardInterrupt):
                    code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False},
                                                               self.succeed, by_key)
                self.assertEqual(130, code)
                self.assertTrue(report['status'].startswith('INTERRUPTED'))
                self.assertTrue(recap.startswith('# INTERRUPTED'))
                self.assertFalse((self.root / '.update-data.lock').exists())

    def test_a_database_left_as_it_was_is_not_replaced(self):
        database = self.database('dofus3', 1, 2)
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['dofus3'], False, saved)
        name = 'fashionistapulp/fashionistapulp/items.db'
        self.assertEqual(audit.file_digest(database), manifest['live'][name])
        with mock.patch.object(audit, 'replace_file', side_effect=PermissionError('locked')):
            self.assertEqual([], audit.restore_runtime(manifest, saved, only=[name], wait=0))

    @contextlib.contextmanager
    def fake_git(self, checkouts):
        def git(*args):
            self.assertEqual(('checkout', 'HEAD', '--'), args[:3])
            checkouts.append(args[3:])
            for name in args[3:]:
                (self.root / name).write_text('head', encoding='utf-8')
            return ''
        names = ['itemscraper/all_mounts.json', 'itemscraper/all_sets.json', 'itemscraper/beta/all_items.json']
        with mock.patch.object(audit, 'in_work_tree', return_value=True), \
                mock.patch.object(audit, 'tracked_data_files', return_value=names), \
                mock.patch.object(audit, 'modified_data_files', return_value={'itemscraper/beta/all_items.json': True}), \
                mock.patch.object(audit, 'git', side_effect=git):
            yield

    def tracked_files(self):
        scraper = self.root / 'itemscraper'
        (scraper / 'beta').mkdir(parents=True)
        files = {name: scraper / name for name in ('beta/all_items.json', 'all_sets.json', 'all_mounts.json')}
        files['beta/all_items.json'].write_text('local edit', encoding='utf-8')
        files['all_sets.json'].write_text('head', encoding='utf-8')
        files['all_mounts.json'].write_text('head', encoding='utf-8')
        return files

    def test_tracked_data_files_a_failed_version_changed_go_back(self):
        files = self.tracked_files()
        checkouts = []
        with self.fake_git(checkouts):
            backup = self.root / 'run/beta'
            audit.record_tracked(backup)
            files['beta/all_items.json'].write_text('import output', encoding='utf-8')
            files['all_sets.json'].write_text('import output', encoding='utf-8')
            self.assertEqual(([], []), audit.restore_tracked(backup))
        self.assertEqual('local edit', files['beta/all_items.json'].read_text(encoding='utf-8'))
        self.assertEqual('head', files['all_sets.json'].read_text(encoding='utf-8'))
        self.assertEqual([('itemscraper/all_sets.json',)], checkouts)
        self.assertEqual(['beta/all_items.json'], [path.relative_to(backup / 'tracked/itemscraper').as_posix()
                                                   for path in (backup / 'tracked').rglob('*.json')])

    def test_a_tracked_file_a_later_version_changed_again_is_kept(self):
        files = self.tracked_files()
        checkouts = []
        with self.fake_git(checkouts):
            backup = self.root / 'run/dofus3'
            audit.record_tracked(backup)
            files['all_sets.json'].write_text('dofus3 output', encoding='utf-8')
            audit.record_tracked_after(backup)
            files['all_sets.json'].write_text('beta output, longer', encoding='utf-8')
            self.assertEqual(([], ['itemscraper/all_sets.json']), audit.restore_tracked(backup))
        self.assertEqual('beta output, longer', files['all_sets.json'].read_text(encoding='utf-8'))
        self.assertEqual([], checkouts)

    def test_a_failed_version_puts_back_the_tracked_data_files_it_changed(self):
        rows, by_key = self.versions_run(['dofus3', 'beta'])
        files = self.tracked_files()
        written = {'dofus3': 'all_mounts.json', 'beta': 'all_sets.json'}
        def run(command, log, **kwargs):
            result = self.succeed(command, log)
            if '--worker' in command:
                key = updater.read_json(Path(command[-1]))['key']
                files[written[key]].write_text(key + ' output', encoding='utf-8')
                if key == 'beta':
                    return dict(result, exit_code=1, error='download failed')
            return result
        checkouts = []
        with self.fake_git(checkouts):
            code, report, recap, output = self.execute(rows, ['dofus3', 'beta'], {'dofus3': False, 'beta': False},
                                                       run, by_key)
        self.assertEqual(['IMPORTED', 'FAILED, RESTORED'], [row['status'] for row in report['versions']])
        self.assertEqual('head', files['all_sets.json'].read_text(encoding='utf-8'))
        self.assertEqual('dofus3 output', files['all_mounts.json'].read_text(encoding='utf-8'))
        self.assertEqual('local edit', files['beta/all_items.json'].read_text(encoding='utf-8'))
        self.assertEqual([('itemscraper/all_sets.json',)], checkouts)
        self.assertTrue((Path(report['directory']) / 'dofus3/tracked-after.json').is_file())

    def test_retro_backs_up_its_damage_spell_file(self):
        names = {audit.relative_name(path) for path in audit.version_files('retro')}
        self.assertIn('itemscraper/retro/retro_damage_spells.json', names)

    def test_each_version_backs_up_its_spell_modifier_file(self):
        for version in ('dofus3', 'beta', 'dofus2', 'retro', 'touch'):
            with self.subTest(version=version):
                names = {audit.relative_name(path) for path in audit.version_files(version)}
                self.assertIn('fashionsite/chardata/spell_modifiers/%s.json' % version, names)

    def test_a_restore_takes_the_spell_modifier_file_back(self):
        modifiers = self.root / 'fashionsite/chardata/spell_modifiers/dofus3.json'
        modifiers.parent.mkdir(parents=True)
        modifiers.write_text('{"data_version": "old"}', encoding='utf-8')
        saved = self.root / 'backup'
        manifest = audit.backup_runtime(['dofus3'], False, saved, shared=False)
        modifiers.write_text('{"data_version": "new"}', encoding='utf-8')
        audit.restore_runtime(manifest, saved)
        self.assertEqual('{"data_version": "old"}', modifiers.read_text(encoding='utf-8'))

    def test_the_wakfu_snapshot_records_the_mirror_counts(self):
        scraper = self.root / 'itemscraper'
        (scraper / 'wakfu_raw/1.93.1.62').mkdir(parents=True)
        (scraper / 'transformed_wakfu.json').write_text('{"version": "1.93.1.62", "equipment": []}', encoding='utf-8')
        (scraper / 'wakfu_raw/1.93.1.62/recipes.json').write_text('[{"id": 1}, {"id": 2}]', encoding='utf-8')
        expected = {'build': '1.93.1.62', 'recipes.json': 2}
        self.assertEqual(expected, audit.wakfu_mirror_counts())
        self.assertEqual(expected, audit.empty_snapshot('wakfu')['mirror'])
        self.assertEqual({}, audit.empty_snapshot('dofus3')['mirror'])

    def test_the_image_backup_skips_the_collected_static_copy(self):
        kept = self.image('chardata/items/60x60/A-60-60.png')
        collected = self.root / 'fashionsite/staticfiles/chardata/items/60x60/A-60-60.png'
        collected.parent.mkdir(parents=True)
        collected.write_bytes(kept.read_bytes())
        self.assertEqual({kept}, audit.image_files())
        self.assertEqual((1, kept.stat().st_size), audit.image_backup_size())

    def test_an_image_backup_that_would_fill_the_disk_is_refused(self):
        rows, by_key = self.versions_run(['dofus3'])
        self.image('chardata/items/60x60/A-60-60.png')
        run = mock.Mock()
        with mock.patch.object(updater.shutil, 'disk_usage', return_value=SimpleNamespace(total=10, used=0, free=10)):
            code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': True}, run, by_key)
        self.assertEqual(1, code)
        run.assert_not_called()
        self.assertRegex(recap, r'Not enough disk space for the image backup: \d+ bytes needed, '
                                r'10 bytes free')

    def main_output(self, *arguments, answer=''):
        row = {'key': 'dofus3', 'current': '3.6.11.15', 'available': '3.6.12.16', 'official': '3.6.12.16',
               'source': {}, 'changed': True, 'warnings': [], 'error': None}
        output = io.StringIO()
        with mock.patch.object(updater, 'discover', return_value=[row]), \
                mock.patch('builtins.input', return_value=answer), contextlib.redirect_stdout(output):
            code = updater.main(list(arguments) + ['--running-file', str(self.root / 'RUNNING.md')])
        return code, output.getvalue()

    def test_the_dry_run_estimates_the_image_backup_and_says_which_test_restores(self):
        self.settings()
        self.image('chardata/items/60x60/A-60-60.png')
        code, output = self.main_output('--dry-run', '--versions', 'dofus3', '--images', 'yes')
        self.assertEqual(0, code)
        self.assertRegex(output, r'Image backup: 1 file, \d+ bytes, about 1 min; .* free on the disk')
        self.assertIn('If build generation fails for a version, that version is restored; '
                      'other failing tests keep the data.', output)
        self.assertIn('Choice: Dofus 3 (with images)', output)
        self.assertIn('1. Dofus 3 (local version: 3.6.11.15)', output)
        self.assertIn('Importable data: 3.6.12.16 | Ankama client: 3.6.12.16', output)

    def test_the_list_gives_the_size_of_the_reports_folder(self):
        (updater.REPORTS / 'run').mkdir(parents=True)
        (updater.REPORTS / 'run/RECAP.md').write_bytes(b'x' * 2048)
        code, output = self.main_output('--list')
        self.assertEqual(0, code)
        self.assertIn('Backups and logs in %s: 2.0 KB (1 file)' % updater.REPORTS, output)

    def old_image_backups(self):
        runs = []
        for number in range(6):
            directory = updater.REPORTS / ('2026092%dT000000000000-1' % number)
            (directory / 'images/fashionsite').mkdir(parents=True)
            (directory / 'images/fashionsite/a.png').write_bytes(b'png')
            (directory / 'images/manifest.json').write_text('{}', encoding='utf-8')
            os.utime(directory / 'images/manifest.json', (1_000_000 + number, 1_000_000 + number))
            runs.append(directory)
        legacy = updater.REPORTS / '20260919T000000000000-1'
        (legacy / 'backup/fashionsite/staticfiles').mkdir(parents=True)
        (legacy / 'backup/fashionsite/staticfiles/b.png').write_bytes(b'png')
        (legacy / 'backup/manifest.json').write_text('{}', encoding='utf-8')
        os.utime(legacy / 'backup/manifest.json', (999_000, 999_000))
        return runs, legacy

    def test_old_image_backups_are_deleted_only_after_the_owner_types_yes(self):
        for confirmation in ('yes', 'oui'):
            with self.subTest(confirmation=confirmation), \
                    mock.patch.object(updater, 'REPORTS', self.root / ('reports-' + confirmation)):
                runs, legacy = self.old_image_backups()
                updater.importing_path(runs[0], 'dofus3').write_text('pid', encoding='utf-8')
                for arguments, answer in ((('--clean-reports',), 'y'), (('--clean-reports', '--yes'), '')):
                    code, output = self.main_output(*arguments, answer=answer)
                    self.assertEqual(0, code)
                    self.assertIn('Nothing deleted.', output)
                    self.assertTrue(all((run / 'images').is_dir() for run in runs))
                code, output = self.main_output('--clean-reports', answer=confirmation)
                self.assertIn('Kept, restore unfinished: ' + str(runs[0]), output)
                self.assertEqual([True, False, False, True, True, True], [(run / 'images').is_dir() for run in runs])
                self.assertFalse((legacy / 'backup/fashionsite/staticfiles').exists())
                self.assertTrue((legacy / 'backup/manifest.json').exists())

    def test_a_report_written_with_the_french_statuses_still_keeps_its_images(self):
        runs, legacy = self.old_image_backups()
        updater.write_json(runs[1] / 'report.json', {'status': 'ÉCHEC, RESTAURATION INCOMPLÈTE'})
        updater.write_json(runs[2] / 'report.json', {'status': 'FAILED, ' + updater.RESTORE_INCOMPLETE})
        code, output = self.main_output('--clean-reports', answer='yes')
        self.assertEqual(0, code)
        self.assertEqual([False, True, True, True, True, True], [(run / 'images').is_dir() for run in runs])

    def test_kept_dofusdb_steps_are_stated_once_and_zero_counts_collapse(self):
        row = {'key': 'dofus3', 'status': updater.IMPORTED, 'current': 'a', 'available': 'b', 'images': False,
               'warnings': [], 'steps': [
                   {'step': 'mount-looks', 'exit_code': 0, 'warning': 'x', 'kept': True},
                   {'step': 'monster-grades', 'exit_code': 0, 'warning': 'y', 'kept': True},
                   {'step': 'items/transform', 'exit_code': 0, 'notices': ['Unknown stat X']}],
               'diff': {'items_added': [], 'items_removed': [], 'items_changed': [{'id': 1}], 'spell_changes': {},
                        'new_stats': [], 'new_image_problems': {}, 'errors': [], 'warnings': []}}
        text = '\n'.join(updater.version_block(row))
        self.assertEqual(1, text.count('DofusDB disabled'))
        self.assertIn('not refreshed (DofusDB disabled): Mount appearances, Monster grades', text)
        self.assertIn('- Steps with warnings: Transforming items\n', text + '\n')
        self.assertIn('- Items: +0, -0, 1 changed', text)
        self.assertIn('- No change: spells, stats, images', text)
        self.assertNotIn('Spells: +0', text)

    def test_console_step_numbers_match_the_log_file_numbers(self):
        module = SimpleNamespace(__file__='legacy.py')
        def main():
            module.run_step('items/download', ['python', 'get_equipments.py'])
            module.run_step('items/transform', ['python', 'get_equipments2.py'])
        module.main = main
        logs = []
        def run(command, log, *args, **kwargs):
            logs.append(log.name)
            log.write_text('ok\n', encoding='utf-8')
            return {'exit_code': 0, 'log': str(log), 'seconds': .1}
        job = self.root / 'job.json'
        updater.write_json(job, {'key': 'dofus3', 'images': False, 'available': '3.6.10.0', 'timeout': 60})
        output = io.StringIO()
        with mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                mock.patch.object(updater, 'run_command', side_effect=run), \
                mock.patch.object(updater.sys, 'argv', []), contextlib.redirect_stdout(output):
            updater.worker(job)
        self.assertEqual(['dofus3-01-items-download.log', 'dofus3-02-items-transform.log'], logs)
        self.assertIn('Dofus 3 | 01 | Downloading items: OK', output.getvalue())
        self.assertIn('Dofus 3 | 02 | Transforming items: OK', output.getvalue())

    def test_a_failing_check_without_test_lines_prints_its_error(self):
        rows, by_key = self.versions_run(['dofus3'])
        def run(command, log, **kwargs):
            result = self.succeed(command, log)
            if log.stem == 'weapons':
                log.write_text('Traceback (most recent call last):\nKeyError: dofus3\n', encoding='utf-8')
                return dict(result, exit_code=1, error='KeyError: dofus3')
            return result
        code, report, recap, output = self.execute(rows, ['dofus3'], {'dofus3': False}, run, by_key)
        self.assertEqual(2, code)
        self.assertIn('Weapon check: FAILED, KeyError: dofus3; log ', output)
        self.assertNotIn('0 tests', output)

    def test_a_new_patch_is_noted_once_by_the_launcher(self):
        (self.root / 'fashionista_version.py').write_text(
            'FASHIONISTA_VERSION = "3.6.11.15"\nPATCH_TIMELINE = {\n    \'dofus3\': [\n'
            '        (\'2026-01-01\', \'3.6\'),\n    ],\n}\n', encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            updater.set_game_versions([{'key': 'dofus3', 'available': '3.7.0.1'}])
        self.assertIn('[progress] Dofus 3: start of patch 3.7 noted in PATCH_TIMELINE', output.getvalue())
        self.assertNotIn('[version]', output.getvalue())
        self.assertIn("'3.7'),", (self.root / 'fashionista_version.py').read_text(encoding='utf-8'))

    def test_the_running_section_ends_at_the_next_heading(self):
        running = self.root / 'RUNNING.md'
        running.write_text('## En cours\n(rien)\n\n## History\nold rebuild 2026-09-01\n', encoding='utf-8')
        with updater.exclusive(running):
            text = running.read_text(encoding='utf-8')
            self.assertLess(text.index('update_all pid='), text.index('## History'))
        self.assertIn('old rebuild 2026-09-01', running.read_text(encoding='utf-8'))
        self.assertNotIn('update_all pid=', running.read_text(encoding='utf-8'))


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
print('[progress] child ready', flush=True)
deadline = time.monotonic() + 5
while not Path(sys.argv[1]).exists():
    if time.monotonic() > deadline:
        raise SystemExit(2)
    time.sleep(.01)
print('[progress] end without newline', end='', flush=True)
"""
        class Output(io.StringIO):
            def write(self, value):
                if 'child ready' in value:
                    ready.touch()
                return super().write(value)
        output = Output()
        log = self.directory / 'stream.log'
        with contextlib.redirect_stdout(output):
            result = updater.run_command([sys.executable, '-c', script, str(ready)], log,
                                         relay_progress=True, title='Import', timeout=10)
        self.assertEqual(0, result['exit_code'], log.read_text(encoding='utf-8'))
        self.assertIn('child ready', output.getvalue())
        self.assertIn('end without newline', output.getvalue())
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
            if 'running' in message:
                heartbeat.set()
        with mock.patch.object(updater, 'HEARTBEAT_SECONDS', .01), mock.patch.object(updater, 'progress', side_effect=report):
            with updater.phase('Backup'):
                self.assertTrue(heartbeat.wait(5))
        self.assertIn('done', messages[-1])

    def test_timeout_stops_the_child_and_retains_its_log(self):
        log = self.directory / 'timeout.log'
        script = "import time; print('ready', flush=True); time.sleep(60)"
        processes = []
        original = subprocess.Popen
        def start(*args, **kwargs):
            process = original(*args, **kwargs)
            processes.append(process)
            return process
        with mock.patch.object(updater.subprocess, 'Popen', side_effect=start), \
                contextlib.redirect_stdout(io.StringIO()), \
                self.assertRaisesRegex(TimeoutError, r'^Timed out \(0 s\): Dofus 3 \| 02 \| Loading the database$'):
            updater.run_command([sys.executable, '-c', script], log, timeout=.2,
                                title='Dofus 3 | 02 | Loading the database')
        self.assertIsNotNone(processes[0].poll())
        self.assertIn('Command:', log.read_text(encoding='utf-8'))

    def test_the_real_work_tree_lists_its_tracked_scraper_data(self):
        if not audit.in_work_tree():
            self.skipTest('not a git work tree')
        names = audit.tracked_data_files()
        self.assertIn('itemscraper/retro/retro_damage_spells.json', names)
        self.assertTrue(all(name.startswith('itemscraper/') and name.endswith('.json') for name in names))
        self.assertTrue(all(name.endswith('.json') for name in audit.modified_data_files()))

    def test_every_pipeline_step_has_a_readable_title(self):
        labels = set()
        for script in Path(updater.__file__).parent.glob('update_data*.py'):
            source = script.read_text(encoding='utf-8')
            labels.update(re.findall(r'''\bstep\(\s*f?["']([^"']+)["']''', source))
        labels = {label.replace('{lang}', 'es').replace('%s', 'fr') for label in labels}
        self.assertGreater(len(labels), 50)
        for label in labels:
            with self.subTest(label=label):
                title = updater.step_title(label)
                self.assertNotEqual(label, title)
                self.assertNotIn('/', title)
        self.assertEqual('Downloading spells (fr)', updater.step_title('data/spells fr'))
        self.assertEqual('Downloading languages (es)', updater.step_title('lang/download-es'))

    def test_the_search_names_each_game_in_full(self):
        output = io.StringIO()
        with mock.patch.object(updater, 'fetch_json', side_effect=OSError('offline')), \
                mock.patch.object(updater, 'probe', side_effect=OSError('offline')), \
                contextlib.redirect_stdout(output):
            rows = updater.discover()
        self.assertEqual(list(updater.VERSIONS), [row['key'] for row in rows])
        for name in ('Dofus 3', 'Dofus 3 Beta', 'Dofus 2', 'Dofus Touch', 'Dofus Retro', 'Wakfu'):
            self.assertIn('Checking for updates: %s\n' % name, output.getvalue())
        with self.assertRaisesRegex(ValueError, '^Dofus 3 Beta: source unavailable'):
            updater.selection('beta', rows)

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
        self.assertTrue(any('NEW STAT' in line for line in result['warnings']))

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
        self.assertTrue(any('Inconsistent dump' in error for error in audit.compare(before, after)['errors']))

    def test_losing_an_existing_shared_image_is_a_regression(self):
        before = self.baseline()
        before['images']['paths'] = {'spell:2': 'spells/existing.png'}
        after = copy.deepcopy(before)
        after['images']['problems']['spell:2'] = {'path': 'spells/existing.png'}
        self.assertTrue(any('Existing image lost' in error for error in audit.compare(before, after)['errors']))

    def wakfu_pair(self, recipes, jobs):
        before = self.baseline()
        before.update(version='wakfu', mirror={'build': '1.92.1.60', 'recipes.json': 5616})
        before['tables'] = {'items': 7617, 'stats': 34, 'stats_of_item': 50562, 'sets': 195, 'item_craft_jobs': 4455}
        after = copy.deepcopy(before)
        after['mirror'] = {'build': '1.93.1.62', 'recipes.json': recipes}
        after['tables']['item_craft_jobs'] = jobs
        return before, after

    def test_a_wakfu_table_that_shrinks_with_its_mirror_source_is_only_a_warning(self):
        result = audit.compare(*self.wakfu_pair(5428, 4210))
        self.assertEqual([], result['errors'])
        self.assertIn('item_craft_jobs: 4455 -> 4210 rows, the Ankama source recipes.json shrank too '
                      '(5616 -> 5428)', result['warnings'])

    def test_a_wakfu_loss_beyond_what_its_source_lost_still_blocks(self):
        for recipes, jobs in ((5428, 3000), (5616, 4210), (5700, 4210)):
            with self.subTest(recipes=recipes, jobs=jobs):
                errors = audit.compare(*self.wakfu_pair(recipes, jobs))['errors']
                self.assertTrue(any(error.startswith('item_craft_jobs: lost more than 3%') for error in errors))

    def test_an_item_kept_after_ankama_removed_it_is_counted_as_hidden(self):
        before = self.baseline()
        after = copy.deepcopy(before)
        after['items']['1']['removed'] = 1
        result = audit.compare(before, after)
        self.assertEqual([], result['errors'])
        self.assertEqual(['1'], result['items_hidden'])
        self.assertIn('- Items removed by Ankama, kept hidden for saved builds: 1',
                      updater.diff_lines(result))

    def test_the_mirror_rule_is_for_wakfu_only(self):
        before, after = self.wakfu_pair(5428, 4210)
        before['version'] = after['version'] = 'dofus3'
        before['tables'].update(weapon_hits=1, weapon_ap=1)
        after['tables'].update(weapon_hits=1, weapon_ap=1)
        self.assertTrue(any('item_craft_jobs' in error for error in audit.compare(before, after)['errors']))
