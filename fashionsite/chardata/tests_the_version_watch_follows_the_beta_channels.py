# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The version watch reads Touch's early channel and the Retro beta release, and leaves every other version as it was."""
import contextlib
import io
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
from unittest import mock

from django.test import SimpleTestCase

import fashionista_version
import update_all as updater

from chardata.tests import itemscraper_module

TOUCH_WATCHED = '3.4.3_abc'
RETRO_WATCHED = '1.50.0.5770.137-36058be'
RETRO_ROOT = 'https://dofusretro.cdn.ankama.com/static-data/638/lang'
RETRO_LANG = {'items': '100434', 'itemstats': '100437', 'itemsets': '100465', 'crafts': '100465',
              'effects': '100465', 'classes': '100463', 'spells': '100461'}
METADATA = {'FASHIONISTA_TOUCHBETA_VERSION': '1.75.0', 'WATCHED_TOUCH_BETA_ASSETS': TOUCH_WATCHED,
            'FASHIONISTA_RETROBETA_VERSION': '1.50.0', 'WATCHED_RETROBETA_BUILD': RETRO_WATCHED,
            'WATCHED_RETROBETA_LANG_ROOT': RETRO_ROOT, 'WATCHED_RETROBETA_LANG': RETRO_LANG}


def early_config(assets):
    return {'assetsUrl': 'https://dofustouch.cdn.ankama.com/assets/' + assets, 'serverLanguages': ['fr', 'en'],
            'dataUrl': 'https://early.invalid'}


def probe_touch_beta(assets=TOUCH_WATCHED, build='1.75.0', state=None, config=None, unreachable=False):
    reader = mock.Mock(side_effect=OSError('behind login') if unreachable else None,
                       return_value=config if config is not None else early_config(assets))
    with mock.patch.object(updater, 'read_metadata', return_value=METADATA), \
            mock.patch.object(updater, 'read_json', return_value=state or {}), \
            mock.patch.object(updater, 'fetch_json', side_effect=AssertionError('no login source')), \
            mock.patch.object(updater.touch_channels, 'read_config', reader), \
            mock.patch.object(updater, 'touch_build_version', return_value=build) as builder:
        row = updater.probe('touchbeta')
    return row, reader, builder


def probe_retro_beta(build='6.0_' + RETRO_WATCHED, root=RETRO_ROOT, state=None, catalog=None, lang=None):
    import cytrus_cdn
    import download_retro_langs
    catalog = catalog or {'games': {'retro': {'platforms': {'windows': {'main': 'x', 'beta': build}}}}}
    with mock.patch.object(updater, 'read_metadata', return_value=METADATA), \
            mock.patch.object(updater, 'read_json', return_value=state or {}), \
            mock.patch.object(cytrus_cdn, 'download_manifest', return_value=b'manifest') as manifest, \
            mock.patch.object(download_retro_langs, 'fetch_manifest',
                              return_value={**(lang or RETRO_LANG), 'dialog': '1'}), \
             mock.patch.object(download_retro_langs, 'lang_root', return_value=root) as resolved:
        row = updater.probe('retrobeta', catalog)
    return row, manifest, resolved


class TouchBetaFollowsTheEarlyBundleTests(SimpleTestCase):

    def test_the_bundle_its_data_was_built_from_is_no_change(self):
        row, reader, builder = probe_touch_beta()
        self.assertEqual((False, None, False), (row['changed'], row['error'], row.get('older', False)))
        self.assertEqual(TOUCH_WATCHED, row['current_data'])
        reader.assert_called_once_with('early')
        builder.assert_called_once_with('early')

    def test_a_newer_early_bundle_marks_touch_beta_moved_and_selects_it(self):
        row, _reader, _builder = probe_touch_beta(assets='3.4.4_def')
        self.assertEqual((True, None), (row['changed'], row['error']))
        self.assertEqual('3.4.4_def', row['source']['assets'])
        self.assertEqual(['touchbeta'], updater.selection('touchbeta', [row]))

    def test_the_same_bundle_number_with_another_hash_is_a_move(self):
        row, _reader, _builder = probe_touch_beta(assets='3.4.3_other')
        self.assertTrue(row['changed'])

    def test_a_newer_early_build_with_the_same_bundle_is_a_move(self):
        row, _reader, _builder = probe_touch_beta(build='1.75.1')
        self.assertTrue(row['changed'])
        self.assertEqual('1.75.1', row['available'])

    def test_an_early_bundle_older_than_the_last_import_is_reported_and_not_imported(self):
        row, _reader, _builder = probe_touch_beta(assets='3.4.2_old')
        self.assertEqual((False, None, True), (row['changed'], row['error'], row['older']))
        self.assertIn('older than the last import', row['warnings'][0])
        with self.assertRaisesRegex(ValueError, 'older than the last import'):
            updater.selection('touchbeta', [row])

    def test_the_bundle_of_the_last_import_comes_from_the_saved_state_first(self):
        state = {'touchbeta': {'source': {'build': '1.75.0', 'assets': '3.4.5_new', 'languages': ['en', 'fr'],
                                          'data_url': 'https://early.invalid'}}}
        row, _reader, _builder = probe_touch_beta(assets='3.4.5_new', state=state)
        self.assertFalse(row['changed'])
        row, _reader, _builder = probe_touch_beta(assets='3.4.4_between', state=state)
        self.assertTrue(row['older'])

    def test_an_unreachable_early_channel_is_an_error_row_and_the_other_versions_are_still_read(self):
        real_probe = updater.probe

        def probed(version, catalog=None):
            if version == 'touchbeta':
                with mock.patch.object(updater, 'read_json', return_value={}), \
                        mock.patch.object(updater.touch_channels, 'read_config',
                                          side_effect=OSError('behind login')):
                    return real_probe(version)
            return {'key': version, 'current': '1', 'available': '1', 'official': '1', 'source': {},
                    'changed': False, 'warnings': [], 'error': None}

        with mock.patch.object(updater, 'fetch_json', side_effect=OSError('offline')), \
                mock.patch.object(updater, 'probe', side_effect=probed), \
                mock.patch.object(updater, 'read_metadata', return_value=METADATA), \
                contextlib.redirect_stdout(io.StringIO()):
            rows = {row['key']: row for row in updater.discover()}
        self.assertEqual(list(updater.VERSIONS), list(rows))
        self.assertIn('behind login', rows['touchbeta']['error'])
        self.assertEqual([None] * 7, [row['error'] for key, row in rows.items() if key != 'touchbeta'])
        with self.assertRaisesRegex(ValueError, 'source unavailable'):
            updater.selection('touchbeta', list(rows.values()))

    def test_a_config_that_names_no_bundle_is_an_error_not_a_move(self):
        with self.assertRaisesRegex(ValueError, 'no assets bundle'):
            probe_touch_beta(config={'serverLanguages': ['fr']})

    def test_the_early_build_may_carry_a_prerelease_suffix_and_the_login_build_may_not(self):
        def served(text):
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = text.encode()
            return mock.patch.object(updater.urllib.request, 'urlopen', return_value=response)

        with served("window.buildVersion = '1.75.0-4';"):
            self.assertEqual('1.75.0', updater.touch_build_version('early'))
        with served("window.buildVersion = '1.74.13';"):
            self.assertEqual('1.74.13', updater.touch_build_version())
        with served("window.buildVersion = '1.74.13-4';"), self.assertRaisesRegex(ValueError, 'Touch build'):
            updater.touch_build_version()

    def test_an_import_of_touch_beta_sets_its_own_stamp_and_not_touchs(self):
        content = 'WATCHED_TOUCH_ASSETS = "3.3.11_x"\nWATCHED_TOUCH_BETA_ASSETS = "3.4.3_abc"\n'
        row = {'key': 'touchbeta', 'source': {'assets': '3.4.4_def'}}
        self.assertEqual('WATCHED_TOUCH_ASSETS = "3.3.11_x"\nWATCHED_TOUCH_BETA_ASSETS = "3.4.4_def"\n',
                         updater.set_watched_sources(content, row))

    def test_the_import_of_touch_beta_reads_the_early_channel(self):
        seen = []
        module = SimpleNamespace(__file__='legacy.py', main=lambda: seen.append(list(updater.sys.argv)))
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder) / 'job.json'
            updater.write_json(job, {'key': 'touchbeta', 'images': False, 'available': '1.75.0', 'timeout': 60})
            with mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                    mock.patch.object(updater.sys, 'argv', []):
                updater.worker(job)
        self.assertEqual([['legacy.py', '--channel', 'early', '--skip-images']], seen)


class RetroBetaFollowsTheBetaReleaseTests(SimpleTestCase):

    def test_the_build_and_static_data_its_data_was_built_from_are_no_change(self):
        row, manifest, resolved = probe_retro_beta()
        self.assertEqual((False, None, '1.50.0'), (row['changed'], row['error'], row['available']))
        self.assertEqual({'build': RETRO_WATCHED, 'lang_root': RETRO_ROOT, 'lang': RETRO_LANG}, row['source'])
        manifest.assert_called_once_with('retrobeta', version='6.0_' + RETRO_WATCHED)
        resolved.assert_called_once_with('retrobeta', manifest=b'manifest')

    def test_a_newer_beta_build_marks_retro_beta_moved_and_selects_it(self):
        row, _manifest, _resolved = probe_retro_beta(build='6.0_1.50.1.5780.140-abcdef0')
        self.assertEqual((True, None, '1.50.1'), (row['changed'], row['error'], row['available']))
        self.assertEqual(['retrobeta'], updater.selection('retrobeta', [row]))

    def test_a_new_static_data_folder_under_the_same_build_is_a_move(self):
        row, _manifest, _resolved = probe_retro_beta(root=RETRO_ROOT.replace('638', '640'))
        self.assertTrue(row['changed'])

    def test_a_lang_category_bumped_under_the_same_build_and_folder_is_a_move(self):
        row, _manifest, _resolved = probe_retro_beta(lang={**RETRO_LANG, 'items': '100500'})
        self.assertEqual((True, False), (row['changed'], row.get('older', False)))
        self.assertEqual(['retrobeta'], updater.selection('retrobeta', [row]))

    def test_the_lang_of_the_last_import_comes_from_the_saved_state_first(self):
        state = {'retrobeta': {'source': {'build': RETRO_WATCHED, 'lang_root': RETRO_ROOT,
                                          'lang': {**RETRO_LANG, 'items': '100500'}}}}
        row, _manifest, _resolved = probe_retro_beta(state=state)
        self.assertTrue(row['changed'])

    def test_a_beta_build_older_than_the_last_import_is_reported_and_not_imported(self):
        row, _manifest, _resolved = probe_retro_beta(build='6.0_1.50.0.5760.100-aaaaaaa')
        self.assertEqual((False, None, True), (row['changed'], row['error'], row['older']))
        self.assertIn('older than the last import', row['warnings'][0])
        with self.assertRaisesRegex(ValueError, 'older than the last import'):
            updater.selection('retrobeta', [row])

    def test_an_older_static_data_folder_under_the_same_build_is_not_imported(self):
        row, _manifest, _resolved = probe_retro_beta(root=RETRO_ROOT.replace('638', '612'))
        self.assertEqual((False, True), (row['changed'], row['older']))

    def test_the_last_import_comes_from_the_saved_state_first(self):
        state = {'retrobeta': {'source': {'build': '1.50.1.5780.140-abcdef0', 'lang_root': RETRO_ROOT}}}
        row, _manifest, _resolved = probe_retro_beta(state=state)
        self.assertTrue(row['older'])

    def test_a_cytrus_without_a_beta_release_or_an_unreadable_manifest_is_an_error(self):
        import cytrus_cdn
        with self.assertRaisesRegex(ValueError, 'no Retro beta release'):
            probe_retro_beta(catalog={'games': {'retro': {'platforms': {'windows': {'main': 'x'}}}}})
        with mock.patch.object(updater, 'read_metadata', return_value=METADATA), \
                mock.patch.object(updater, 'read_json', return_value={}), \
                mock.patch.object(cytrus_cdn, 'download_manifest', side_effect=OSError('unreachable')), \
                self.assertRaisesRegex(OSError, 'unreachable'):
            updater.probe('retrobeta', {'games': {'retro': {'platforms': {'windows': {'beta': 'x'}}}}})

    def test_an_import_of_retro_beta_sets_its_own_stamps_and_not_retros(self):
        content = ('WATCHED_RETRO_BUILD = "1.49.10"\nWATCHED_RETRO_LANG_ROOT = "https://x/612/lang"\n'
                   'WATCHED_RETROBETA_BUILD = "1.50.0"\nWATCHED_RETROBETA_LANG_ROOT = "https://x/638/lang"\n')
        row = {'key': 'retrobeta', 'source': {'build': '1.50.1', 'lang_root': 'https://x/640/lang'}}
        self.assertEqual('WATCHED_RETRO_BUILD = "1.49.10"\nWATCHED_RETRO_LANG_ROOT = "https://x/612/lang"\n'
                         'WATCHED_RETROBETA_BUILD = "1.50.1"\nWATCHED_RETROBETA_LANG_ROOT = "https://x/640/lang"\n',
                         updater.set_watched_sources(content, row))

    def test_an_import_of_retro_beta_sets_its_lang_stamp_and_not_retros(self):
        def stamp(name, value):
            return "%s = {\n    'items': '%s',\n}\n" % (name, value)

        content = stamp('WATCHED_RETRO_LANG', 1) + stamp('WATCHED_RETROBETA_LANG', 2)
        row = {'key': 'retrobeta', 'source': {'lang': {'items': '3'}}}
        with mock.patch.object(updater, 'read_metadata', return_value={'WATCHED_RETROBETA_LANG': {'items': '2'}}):
            self.assertEqual(stamp('WATCHED_RETRO_LANG', 1) + stamp('WATCHED_RETROBETA_LANG', 3),
                             updater.set_watched_sources(content, row))

    def test_a_restore_puts_the_lang_stamp_back(self):
        self.assertIn('WATCHED_RETROBETA_LANG', updater.WATCHED['retrobeta'])

    def test_the_import_of_retro_beta_reads_the_beta_release_and_its_probed_lang_root(self):
        seen = []

        def main():
            seen.append((list(updater.sys.argv), os.environ.get('RETROBETA_LANG_ROOT'),
                         os.environ.get('RETRO_LANG_ROOT')))

        module = SimpleNamespace(__file__='legacy.py', main=main)
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder) / 'job.json'
            updater.write_json(job, {'key': 'retrobeta', 'images': False, 'available': '1.50.0', 'timeout': 60,
                                     'source': {'lang_root': RETRO_ROOT}})
            with mock.patch.dict(os.environ, {}), \
                    mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                    mock.patch.object(updater.sys, 'argv', []):
                updater.worker(job)
        self.assertEqual([(['legacy.py', '--release', 'beta', '--skip-images'], RETRO_ROOT, None)], seen)


class TheMainVersionsAreReadAsBeforeTests(SimpleTestCase):

    def test_touch_still_reads_its_login_channel_and_nothing_of_the_early_one(self):
        config = {'assetsUrl': 'https://dofustouch.cdn.ankama.com/assets/3.3.6_hash', 'serverLanguages': ['fr'],
                  'dataUrl': 'https://login.invalid'}
        metadata = {'FASHIONISTA_TOUCH_VERSION': '1.74.5', 'WATCHED_TOUCH_ASSETS': '3.3.6_hash'}
        with mock.patch.object(updater, 'fetch_json', return_value=config) as fetched, \
                mock.patch.object(updater, 'touch_build_version', return_value='1.74.5') as builder, \
                mock.patch.object(updater.touch_channels, 'read_config',
                                  side_effect=AssertionError('early read')), \
                mock.patch.object(updater, 'read_metadata', return_value=metadata), \
                mock.patch.object(updater, 'read_json', return_value={}):
            row = updater.probe('touch')
        fetched.assert_called_once_with(updater.TOUCH)
        builder.assert_called_once_with()
        self.assertEqual('3.3.6_hash', row['source']['assets'])

    def test_the_numbers_and_tables_of_the_six_older_versions_are_unchanged(self):
        self.assertEqual(('dofus3', 'beta', 'dofus2', 'touch', 'retro', 'wakfu'), updater.VERSIONS[:6])
        self.assertEqual(('touchbeta', 'retrobeta'), updater.EXPLICIT_ONLY[1:])
        rows = [{'key': key, 'error': None, 'changed': True} for key in updater.VERSIONS]
        self.assertEqual(['dofus3', 'beta', 'dofus2', 'touch', 'retro'], updater.selection('changed', rows))
        self.assertEqual(['dofus3', 'beta', 'dofus2', 'touch', 'retro'], updater.selection('all', rows))

    def test_the_retro_import_still_hands_its_lang_root_through_the_old_variable(self):
        seen = []
        module = SimpleNamespace(__file__='legacy.py',
                                 main=lambda: seen.append((list(updater.sys.argv), os.environ.get('RETRO_LANG_ROOT'))))
        with tempfile.TemporaryDirectory() as folder:
            job = Path(folder) / 'job.json'
            updater.write_json(job, {'key': 'retro', 'images': False, 'available': '1.49.5', 'timeout': 60,
                                     'source': {'lang_root': 'https://x/612/lang'}})
            with mock.patch.dict(os.environ, {}), \
                    mock.patch.object(updater.importlib, 'import_module', return_value=module), \
                    mock.patch.object(updater.sys, 'argv', []):
                updater.worker(job)
        self.assertEqual([(['legacy.py', '--skip-images'], 'https://x/612/lang')], seen)

    def test_every_staged_stamp_exists_in_the_real_version_file(self):
        script = itemscraper_module('check_game_versions')
        self.assertRegex(fashionista_version.WATCHED_TOUCH_BETA_ASSETS, r'^\d+\.\d+\.\d+_.+')
        self.assertRegex(fashionista_version.WATCHED_RETROBETA_BUILD, r'^\d+\.\d+\.\d+\.\d+\.\d+-\w+$')
        self.assertGreater(script.static_data_id(fashionista_version.WATCHED_RETROBETA_LANG_ROOT), 0)
        self.assertEqual(set(fashionista_version.WATCHED_RETRO_LANG), set(fashionista_version.WATCHED_RETROBETA_LANG))
        self.assertTrue(all(value.isdigit() for value in fashionista_version.WATCHED_RETROBETA_LANG.values()))

    def test_the_family_of_a_staged_beta_is_the_registrys(self):
        self.assertEqual(('touch', 'retro', 'retro', 'touch'),
                         tuple(updater.family_of(key) for key in ('touchbeta', 'retrobeta', 'retro', 'touch')))


class TheCheckScriptReadsTheBetaChannelsTests(SimpleTestCase):

    def check(self, early=TOUCH_WATCHED, retro=(RETRO_WATCHED, RETRO_ROOT, RETRO_LANG)):
        script = itemscraper_module('check_game_versions')
        original = (script.touch_early_assets, script.retro_beta_live)
        try:
            if isinstance(early, Exception):
                script.touch_early_assets = mock.Mock(side_effect=early)
            else:
                script.touch_early_assets = lambda: early
            if isinstance(retro, Exception):
                script.retro_beta_live = mock.Mock(side_effect=retro)
            else:
                script.retro_beta_live = lambda: retro
            ours = SimpleNamespace(WATCHED_TOUCH_BETA_ASSETS=TOUCH_WATCHED, FASHIONISTA_TOUCHBETA_VERSION='1.75.0',
                                   WATCHED_RETROBETA_BUILD=RETRO_WATCHED, WATCHED_RETROBETA_LANG_ROOT=RETRO_ROOT,
                                   WATCHED_RETROBETA_LANG=RETRO_LANG)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                moved = script.check_touch_beta(ours) + script.check_retro_beta(ours)
            return moved, output.getvalue()
        finally:
            script.touch_early_assets, script.retro_beta_live = original

    def test_the_stamps_of_the_last_import_are_ok(self):
        moved, text = self.check()
        self.assertEqual([], moved)
        self.assertEqual(2, text.count(' ok '))
        self.assertIn('static-data 638 -> 638', text)

    def test_a_newer_early_bundle_and_a_newer_beta_build_are_moved(self):
        moved, text = self.check(early='3.4.4_def', retro=('1.50.1.5780.140-abcdef0', RETRO_ROOT, RETRO_LANG))
        self.assertEqual([('touchbeta', '3.4.4_def'), ('retrobeta', '1.50.1.5780.140-abcdef0')], moved)
        self.assertEqual(2, text.count('MOVED'))

    def test_a_new_static_data_folder_is_moved(self):
        moved, text = self.check(retro=(RETRO_WATCHED, RETRO_ROOT.replace('638', '640'), RETRO_LANG))
        self.assertEqual([('retrobeta', RETRO_WATCHED)], moved)
        self.assertIn('static-data 638 -> 640', text)

    def test_a_lang_category_bumped_under_the_same_build_and_folder_is_moved(self):
        moved, text = self.check(retro=(RETRO_WATCHED, RETRO_ROOT, {**RETRO_LANG, 'itemstats': '100999'}))
        self.assertEqual([('retrobeta', RETRO_WATCHED)], moved)
        self.assertIn('lang categories moved: itemstats', text)

    def test_older_sources_are_reported_and_not_counted_as_moved(self):
        moved, text = self.check(early='3.4.2_old', retro=('1.49.9.5000.1-aaaaaaa', RETRO_ROOT, RETRO_LANG))
        self.assertEqual([], moved)
        self.assertEqual(2, text.count('OLDER, not imported'))

    def test_an_unreachable_channel_is_reported_and_never_raises_or_counts_as_moved(self):
        moved, text = self.check(early=OSError('behind login'), retro=OSError('no beta'))
        self.assertEqual([], moved)
        self.assertEqual(2, text.count('UNREACHABLE'))
        self.assertIn('behind login', text)

    def test_the_early_bundle_comes_from_the_early_config_and_the_beta_from_the_beta_release(self):
        script = itemscraper_module('check_game_versions')
        with mock.patch.object(script.touch_channels, 'read_config',
                               return_value=early_config('3.4.9_zzz')) as reader:
            self.assertEqual('3.4.9_zzz', script.touch_early_assets())
        reader.assert_called_once_with('early')
        with mock.patch.object(script.cytrus_cdn, 'get_version', return_value='6.0_' + RETRO_WATCHED) as version, \
                mock.patch.object(script.cytrus_cdn, 'download_manifest', return_value=b'm') as manifest, \
                mock.patch.object(script, 'retro_lang_root', return_value=RETRO_ROOT) as root, \
                 mock.patch.object(script, 'retro_lang_versions', return_value=RETRO_LANG) as lang:
            self.assertEqual((RETRO_WATCHED, RETRO_ROOT, RETRO_LANG), script.retro_beta_live())
        lang.assert_called_once_with(RETRO_ROOT)
        version.assert_called_once_with('retrobeta')
        manifest.assert_called_once_with('retrobeta', version='6.0_' + RETRO_WATCHED)
        root.assert_called_once_with(b'm', 'retrobeta')

    def test_the_stamps_read_as_numbers_and_the_main_lang_root_call_is_unchanged(self):
        script = itemscraper_module('check_game_versions')
        self.assertEqual((3, 4, 3), script.stamp_order('3.4.3_hash'))
        self.assertEqual((1, 50, 0, 5770, 137), script.stamp_order(RETRO_WATCHED))
        self.assertEqual((), script.stamp_order(''))
        self.assertEqual(638, script.static_data_id(RETRO_ROOT))
        self.assertEqual(0, script.static_data_id('https://dofusretro.cdn.ankama.com/lang'))
        import download_retro_langs
        with mock.patch.object(download_retro_langs, 'lang_root', return_value='r') as resolved:
            self.assertEqual('r', script.retro_lang_root(b'm'))
            resolved.assert_called_once_with(manifest=b'm')
