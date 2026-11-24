# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Touch pipeline reads the login channel by default and the early channel on request, writing the early data apart."""
import contextlib
import importlib.util
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest import mock

import requests
from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
LOGIN_HOST = 'https://dt-proxy-production-login.ankama-games.com'
EARLY_HOST = 'https://dt-proxy-production-early.ankama-games.com'

SMALL_TABLE = {'1': {'id': 1, 'nameId': 'Bouclier d’épreuve', 'iconId': 7}}


class _Reply:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


class _Proxy:
    """Answers config.json and /data/map for the hosts it knows, and remembers every URL asked."""

    def __init__(self, tables, served=('fr', 'en', 'es', 'pt')):
        self.tables = tables
        self.served = list(served)
        self.asked = []

    def get(self, url, headers=None, timeout=None):
        self.asked.append(url)
        host = url.split('/config.json')[0]
        return _Reply({'dataUrl': host, 'assetsUrl': host + '/assets/x', 'serverLanguages': self.served})

    def post(self, url, json=None, headers=None, timeout=None):
        self.asked.append(url)
        return _Reply(self.tables[json['class']])


def _quiet():
    return contextlib.redirect_stdout(io.StringIO())


def _load(name):
    spec = importlib.util.spec_from_file_location(name + '_for_tests', os.path.join(REPO_ROOT, name + '.py'))
    module = importlib.util.module_from_spec(spec)
    with _quiet():
        spec.loader.exec_module(module)
    return module


class TheTwoTouchChannelsTests(SimpleTestCase):

    def setUp(self):
        self.channels = itemscraper_module('touch_channels')

    def test_login_is_the_default_channel(self):
        self.assertEqual('login', self.channels.DEFAULT_CHANNEL)
        self.assertEqual(LOGIN_HOST + '/config.json', self.channels.config_url())
        self.assertEqual('touch', self.channels.game_version())

    def test_early_has_its_own_config_key_and_folders(self):
        self.assertEqual(EARLY_HOST + '/config.json', self.channels.config_url('early'))
        self.assertEqual('touchbeta', self.channels.game_version('early'))
        self.assertEqual('touchbeta_raw', os.path.basename(self.channels.raw_dir('early')))
        self.assertEqual('touchbeta', os.path.basename(self.channels.work_dir('early')))
        self.assertEqual('item_db_dumped_touchbeta.dump', os.path.basename(self.channels.dump_path('early')))

    def test_login_keeps_the_folders_the_pipeline_always_used(self):
        self.assertEqual('touch_raw', os.path.basename(self.channels.raw_dir('login')))
        self.assertEqual('touch', os.path.basename(self.channels.work_dir('login')))
        self.assertEqual('item_db_dumped_touch.dump', os.path.basename(self.channels.dump_path('login')))

    def test_an_unknown_channel_is_refused(self):
        with self.assertRaises(ValueError):
            self.channels.config_url('beta')

    def test_the_languages_served_are_read_from_the_config_of_the_channel(self):
        proxy = _Proxy({}, served=('fr', 'en'))
        with mock.patch.object(self.channels.requests, 'get', proxy.get):
            self.assertEqual({'fr', 'en'}, self.channels.served_languages('early'))
        self.assertEqual([EARLY_HOST + '/config.json?lang=fr'], proxy.asked)


class TheRawTablesFollowTheChannelTests(SimpleTestCase):

    def setUp(self):
        self.download = itemscraper_module('download_touch_data')
        self.channels = itemscraper_module('touch_channels')

    def _run(self, *args, served=('fr', 'en', 'es', 'pt')):
        proxy = _Proxy({'Items': SMALL_TABLE, 'Monsters': {}}, served)
        with tempfile.TemporaryDirectory() as dest, \
                mock.patch.object(self.download.requests, 'get', proxy.get), \
                mock.patch.object(self.download.requests, 'post', proxy.post), \
                _quiet():
            code = self.download.main(['--classes', 'Items', '--dest', dest, *args])
            written = {name: Path(dest, name).read_bytes() for name in os.listdir(dest)}
        return code, written, proxy

    def test_login_writes_the_table_exactly_as_before_and_asks_only_login(self):
        code, written, proxy = self._run()
        self.assertEqual(0, code)
        self.assertEqual({'Items_fr.json': json.dumps(SMALL_TABLE, ensure_ascii=False).encode('utf-8')},
                         written)
        self.assertEqual([LOGIN_HOST + '/config.json?lang=fr', LOGIN_HOST + '/data/map'], proxy.asked)

    def test_early_asks_only_the_early_host(self):
        code, written, proxy = self._run('--channel', 'early')
        self.assertEqual(0, code)
        self.assertEqual(['Items_fr.json'], list(written))
        self.assertEqual([EARLY_HOST + '/config.json?lang=fr', EARLY_HOST + '/data/map'], proxy.asked)

    def test_early_with_no_destination_writes_under_its_own_raw_folder(self):
        proxy = _Proxy({'Items': SMALL_TABLE})
        with tempfile.TemporaryDirectory() as root:
            early_raw = os.path.join(root, 'touchbeta_raw')
            with mock.patch.object(self.download.requests, 'get', proxy.get), \
                    mock.patch.object(self.download.requests, 'post', proxy.post), \
                    mock.patch.object(self.channels, 'raw_dir', return_value=early_raw) as raw_dir, \
                    _quiet():
                self.download.main(['--classes', 'Items', '--channel', 'early'])
            self.assertEqual(['Items_fr.json'], os.listdir(early_raw))
        raw_dir.assert_called_with('early')

    def test_a_language_the_early_config_no_longer_lists_is_not_asked_for(self):
        _, written, proxy = self._run('--channel', 'early', '--all-langs', served=('fr', 'en'))
        self.assertEqual({'Items_fr.json', 'Items_en.json'}, set(written))
        self.assertEqual(2, sum(url.endswith('/data/map') for url in proxy.asked))


class TheMountsFollowTheChannelTests(SimpleTestCase):

    def setUp(self):
        self.mounts = itemscraper_module('download_touch_mounts')
        self.channels = itemscraper_module('touch_channels')

    def _run(self, catalogue, login_rows, *args):
        proxy_urls = []

        def resolve(channel='login'):
            proxy_urls.append(channel)
            return 'proxy-' + channel

        def fetch(data_url):
            if isinstance(catalogue, Exception):
                raise catalogue
            return catalogue, {}

        page = '<div class="ak-title">\n 100  Vitality</div>'
        reply = requests.Response()
        reply.status_code = 200
        reply._content = page.encode('utf-8')
        reply.encoding = 'utf-8'
        session = mock.Mock()
        session.get.return_value = reply
        printed = io.StringIO()
        with tempfile.TemporaryDirectory() as root:
            login_dir = os.path.join(root, 'touch_raw')
            os.makedirs(login_dir)
            if login_rows is not None:
                Path(login_dir, 'mounts.json').write_text(json.dumps(login_rows), encoding='utf-8')
            dest = os.path.join(root, 'touchbeta_raw')
            with mock.patch.object(self.mounts, 'resolve_data_url', resolve), \
                    mock.patch.object(self.mounts, 'fetch_mount_catalogue', fetch), \
                    mock.patch.object(self.mounts, 'make_session', return_value=session), \
                    mock.patch.object(self.mounts, 'time'), \
                    mock.patch.object(self.channels, 'raw_dir',
                                      side_effect=lambda channel='login': login_dir if channel == 'login' else dest), \
                    contextlib.redirect_stdout(printed), contextlib.redirect_stderr(printed):
                code = self.mounts.main(['--delay', '0', *args])
            out = os.path.join(dest, 'mounts.json')
            written = json.loads(Path(out).read_text(encoding='utf-8')) if os.path.exists(out) else None
            login_after = (json.loads(Path(login_dir, 'mounts.json').read_text(encoding='utf-8'))
                           if login_rows is not None else None)
        return code, written, login_after, proxy_urls, printed.getvalue()

    def test_early_reads_the_mounts_table_of_the_early_channel(self):
        code, written, _, asked, _ = self._run({'3': {'en': 'Ebony Dragoturkey'}}, [], '--channel', 'early')
        self.assertEqual(0, code)
        self.assertEqual(['early'], asked)
        self.assertEqual([3], [mount['ankama_id'] for mount in written])

    def test_early_without_a_mounts_table_reuses_the_login_rows_and_says_so(self):
        login_rows = [{'ankama_id': 3, 'name_en': 'Ebony Dragoturkey', 'stats': []}]
        code, written, login_after, _, printed = self._run(
            requests.exceptions.HTTPError('404'), login_rows, '--channel', 'early')
        self.assertEqual(0, code)
        self.assertEqual(login_rows, written)
        self.assertEqual(login_rows, login_after)
        self.assertIn('Reused the 1 Touch mounts of the login channel', printed)

    def test_early_with_no_mounts_anywhere_fails(self):
        code, written, _, _, _ = self._run(requests.exceptions.HTTPError('404'), None, '--channel', 'early')
        self.assertEqual(1, code)
        self.assertIsNone(written)

    def test_login_still_fails_loudly_when_its_mounts_table_cannot_be_read(self):
        with self.assertRaises(requests.exceptions.HTTPError):
            self._run(requests.exceptions.HTTPError('404'), [])


class TheIconsOfTheEarlyChannelAreOnlyTheOnesThatDifferTests(SimpleTestCase):

    def setUp(self):
        self.images = itemscraper_module('download_touch_images')
        self.channels = itemscraper_module('touch_channels')
        self.resources = itemscraper_module('download_resource_icons')

    def _items(self, rows):
        return {str(i): {'id': i, 'nameId': name, 'iconId': icon, 'typeId': 16}
                for i, (name, icon) in rows.items()}

    def test_an_item_image_is_fetched_only_for_a_name_and_icon_login_does_not_have(self):
        login = self._items({1: ('Same Hat', 10), 2: ('Moved Hat', 20)})
        early = self._items({1: ('Same Hat', 10), 2: ('Moved Hat', 21), 3: ('New Hat', 30)})
        fetched = []

        class Session:
            def get(self, url, headers=None, timeout=None):
                fetched.append(url)
                reply = requests.Response()
                reply.status_code = 404
                return reply

        with tempfile.TemporaryDirectory() as root:
            raws = {'login': os.path.join(root, 'touch_raw'), 'early': os.path.join(root, 'touchbeta_raw')}
            for channel, items in (('login', login), ('early', early)):
                os.makedirs(raws[channel])
                Path(raws[channel], 'Items_fr.json').write_text(json.dumps(items), encoding='utf-8')
            with mock.patch.object(self.channels, 'raw_dir', side_effect=lambda channel='login': raws[channel]), \
                    mock.patch.object(self.images.requests, 'Session', Session), \
                    mock.patch.object(self.images, 'STATIC', Path(root, 'static')), \
                    _quiet():
                self.images.main(['--channel', 'early', '--assets-url', 'https://cdn.test/assets/next'])
        self.assertEqual(['https://cdn.test/assets/next/gfx/items/21.png',
                          'https://cdn.test/assets/next/gfx/items/30.png'], sorted(fetched))

    def test_a_resource_icon_is_listed_only_when_the_row_differs_from_login(self):
        login = self._items({1: ('Same Ore', 10), 2: ('Moved Ore', 20)})
        early = self._items({1: ('Same Ore', 10), 2: ('Moved Ore', 21), 3: ('New Ore', 30)})
        tables = {'login': login, 'early': early}
        with mock.patch.object(self.resources, 'touch_items',
                               side_effect=lambda channel='login': tables[channel]):
            changed = self.resources.icons_that_differ_from_login('early')
        self.assertEqual({2: 'gfx/items/21.png', 3: 'gfx/items/30.png'}, changed)

    def test_a_resource_row_equal_to_login_keeps_the_login_icon(self):
        login = self._items({1: ('Same Ore', 10), 2: ('Moved Ore', 20)})
        early = self._items({1: ('Same Ore', 10), 2: ('Moved Ore', 21), 3: ('New Ore', 30)})
        tables = {'login': login, 'early': early}
        with mock.patch.object(self.resources, 'touch_items',
                               side_effect=lambda channel='login': tables[channel]):
            self.assertEqual({1}, self.resources.rows_same_as_login('early'))

    def test_a_monster_image_is_listed_only_when_login_does_not_know_the_monster(self):
        monsters = itemscraper_module('download_monster_images')
        with tempfile.TemporaryDirectory() as root:
            login_raw = os.path.join(root, 'touch_raw')
            os.makedirs(login_raw)
            Path(login_raw, 'Monsters_fr.json').write_text(json.dumps({'1': {}, '2': {}}), encoding='utf-8')
            with mock.patch.object(self.channels, 'raw_dir', return_value=login_raw):
                self.assertEqual([3], monsters.monsters_not_in_login([1, 2, 3]))

    def test_login_icons_go_to_the_same_folders_and_records_as_before(self):
        self.assertTrue(self.resources.SOURCE_RECORDS['touch'].endswith(os.path.join('touch', 'resource_icon_sources.json')))
        self.assertTrue(self.resources.SOURCE_RECORDS['touchbeta'].endswith(
            os.path.join('touchbeta', 'resource_icon_sources.json')))


class TheSpellsFollowTheChannelTests(SimpleTestCase):

    def setUp(self):
        self.spells = itemscraper_module('get_spells_touch')

    def test_the_early_channel_writes_its_own_module_and_not_the_login_one(self):
        written = []
        with mock.patch.object(self.spells, 'resolve_config', return_value=('proxy', 'assets')), \
                mock.patch.object(self.spells, 'fetch_table', return_value={}), \
                mock.patch.object(self.spells, 'build', return_value={}), \
                mock.patch.object(self.spells, 'build_damage_taken', return_value={}), \
                mock.patch.object(self.spells, 'build_spell_names', return_value={}), \
                mock.patch.object(self.spells, 'emit_module',
                                  side_effect=lambda by_class, names, path, taken: written.append(path)), \
                _quiet():
            self.spells.main(['--channel', 'early', '--skip-images'])
            self.spells.main(['--skip-images'])
        self.assertEqual(['dofus_constants_touchbeta_spells.py', 'dofus_constants_touch_spells.py'],
                         [os.path.basename(path) for path in written])

    def test_a_spell_icon_identical_to_login_is_not_fetched_again(self):
        by_class = {'Iop': [{'id': 1, 'name': 'Same'}, {'id': 2, 'name': 'Moved'}, {'id': 3, 'name': 'New'}]}
        now = {'1': {'nameId': 'Same', 'iconId': 10}, '2': {'nameId': 'Moved', 'iconId': 21},
               '3': {'nameId': 'New', 'iconId': 30}}
        login = {'1': {'nameId': 'Same', 'iconId': 10}, '2': {'nameId': 'Moved', 'iconId': 20}}
        self.assertEqual({'Same'}, self.spells.unchanged_spell_names(by_class, now, login))

    def test_a_spell_icon_login_does_not_hold_is_fetched_even_when_the_spell_is_unchanged(self):
        by_class = {'Iop': [{'id': 1, 'name': 'Held'}, {'id': 2, 'name': 'Missing'}]}
        same = {'1': {'nameId': 'Held', 'iconId': 10}, '2': {'nameId': 'Missing', 'iconId': 11}}
        with tempfile.TemporaryDirectory() as folder:
            open(os.path.join(folder, 'Held.png'), 'wb').close()
            self.assertEqual({'Held'}, self.spells.unchanged_spell_names(by_class, same, same, folder))


class TheLoginPipelineIsUnchangedTests(SimpleTestCase):

    def _commands(self, argv, registered):
        module = _load('update_data_touch')
        commands = []

        def run_step(label, cmd, cwd=None):
            commands.append((label, list(cmd)))
            return True, []

        with mock.patch.object(module, 'run_step', run_step), \
                mock.patch.object(module, 'registered_versions', return_value=registered), \
                mock.patch.object(sys, 'argv', ['update_data_touch.py', *argv]), \
                _quiet():
            module.main()
        return module, commands

    def test_the_default_run_never_names_a_channel_or_a_beta_folder(self):
        module, commands = self._commands([], {'touch'})
        flat = [part for _, cmd in commands for part in cmd]
        self.assertNotIn('--channel', flat)
        self.assertFalse([part for part in flat if 'touchbeta' in part])
        self.assertIn(module.TOUCH_RAW_DIR, flat)
        self.assertIn(module.TOUCH_WORK_DIR, flat)
        self.assertIn(module.TOUCH_DUMP, flat)

    def test_the_default_run_keeps_every_step_in_its_order(self):
        _, commands = self._commands([], {'touch'})
        labels = [label for label, _ in commands]
        self.assertEqual('data/download', labels[0])
        self.assertEqual('data/mounts', labels[1])
        self.assertEqual('verify/rebuild', labels[-1])
        self.assertEqual(len(labels), len(set(labels)))
        self.assertIn(['load_item_db.py', '--game-version', 'touch'], [cmd[1:] for _, cmd in commands])

    def test_early_before_its_registry_key_stops_after_the_transformed_files(self):
        module, commands = self._commands(['--channel', 'early'], {'touch'})
        self.assertEqual(['data/download', 'data/seed-languages', 'data/mounts', 'items/transform'],
                         [label for label, _ in commands])
        flat = [part for _, cmd in commands for part in cmd]
        self.assertNotIn(module.TOUCH_RAW_DIR, flat)
        self.assertNotIn(module.TOUCH_WORK_DIR, flat)
        self.assertNotIn(module.TOUCH_DUMP, flat)
        raws = [part for part in flat if part.endswith('touchbeta_raw')]
        self.assertTrue(raws)
        self.assertEqual(['--channel', 'early'], commands[0][1][-2:])

    def test_early_once_registered_reads_the_channel_only_where_the_step_can(self):
        _, commands = self._commands(['--channel', 'early'], {'touch', 'touchbeta'})
        by_label = dict(commands)
        for label in ('data/download', 'data/mounts', 'items/recipes', 'items/special-spells',
                      'pets/store-bonuses', 'monsters/grades', 'monsters/subareas',
                      'spells/build', 'item-images', 'resource-icons', 'monster-images'):
            self.assertEqual(['--channel', 'early'], by_label[label][-2:], label)
        for label in ('stats/starting', 'items/weapon-conversions', 'spells/tooltips',
                      'spells/modifiers', 'drops/store', 'craftjobs/store', 'item-skins',
                      'items/corrections', 'spells/reference', 'verify/rebuild'):
            self.assertIn('touchbeta', by_label[label], label)
            self.assertNotIn('touch', by_label[label], label)
        self.assertEqual(['load_item_db.py', '--game-version', 'touchbeta'], by_label['items/load-db'][1:])

    def test_early_reads_its_own_drops_and_names_what_it_still_skips(self):
        module = _load('update_data_touch')
        commands = []
        printed = io.StringIO()

        def run_step(label, cmd, cwd=None):
            commands.append(label)
            return True, []

        with mock.patch.object(module, 'run_step', run_step), \
                mock.patch.object(module, 'registered_versions', return_value={'touch', 'touchbeta'}), \
                mock.patch.object(sys, 'argv', ['update_data_touch.py', '--channel', 'early']), \
                contextlib.redirect_stdout(printed):
            module.main()
        for label in ('drops/transform', 'drops/store', 'monsters/grades', 'monsters/subareas',
                      'monster-images', 'craftjobs/store', 'items/recipes', 'pets/store-bonuses'):
            self.assertIn(label, commands)
        for label in ('pets/scrape-bonuses', 'dynamic-translations'):
            self.assertNotIn(label, commands)
            self.assertIn('[%s]' % label + chr(10) + '  skipped: ', printed.getvalue())

    def test_login_still_runs_its_monster_steps(self):
        _, commands = self._commands([], {'touch', 'touchbeta'})
        by_label = dict(commands)
        self.assertEqual(['store_touch_monster_subareas.py', '--download'], by_label['monsters/subareas'][1:])
        self.assertEqual(['download_monster_images.py', '--game-version', 'touch'], by_label['monster-images'][1:])
