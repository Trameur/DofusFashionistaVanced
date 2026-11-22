# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Retro importer reads its lang files under the dataserver the live client config ranks first."""
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
from unittest import TestCase, mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'itemscraper'))
import download_retro_langs as langs  # noqa: E402
import get_monsters_retro  # noqa: E402
import store_retro_subarea_languages  # noqa: E402

LIVE_ROOT = 'https://dofusretro.cdn.ankama.com/static-data/612/lang'


def config(*servers):
    rows = ''.join('<dataserver url="%s"%s priority="%s"/>' % (url, ' type="local"' if local else '', priority)
                   for url, priority, local in servers)
    return ('<config><clientdata><environment><databank>%s</databank></environment></clientdata></config>'
            % rows).encode('utf-8')


CLIENT = config(('data/', 3, True), ('https://dofusretro.cdn.ankama.com/static-data/612/', 1, False))


class Response(SimpleNamespace):
    def raise_for_status(self):
        pass


class TheRetroLangRootComesFromTheClientConfigTests(TestCase):
    def setUp(self):
        self.addCleanup(langs._resolved_roots.clear)
        langs._resolved_roots.clear()
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop(langs.LANG_ROOT_ENV, None)

    def test_the_remote_dataserver_of_priority_one_names_the_lang_root(self):
        self.assertEqual(LIVE_ROOT, langs.lang_root_from_config(CLIENT))

    def test_the_lowest_priority_number_wins_whatever_the_order(self):
        both = config(('https://dofusretro.cdn.ankama.com/static-data/700/', 2, False), ('data/', 0, True),
                      ('https://dofusretro.cdn.ankama.com/static-data/612', 1, False))
        self.assertEqual(LIVE_ROOT, langs.lang_root_from_config(both))

    def test_a_config_without_a_remote_dataserver_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'no remote dataserver'):
            langs.lang_root_from_config(config(('data/', 1, True)))

    def test_a_dataserver_outside_ankama_or_without_https_is_refused(self):
        for url in ('https://example.invalid/static-data/612/', 'http://dofusretro.cdn.ankama.com/static-data/612/',
                    'https://dofusretro.cdn.ankama.com.example.invalid/'):
            with self.subTest(url=url), self.assertRaisesRegex(ValueError, 'unexpected Retro dataserver'):
                langs.lang_root_from_config(config((url, 1, False)))

    def test_two_dataservers_sharing_the_first_priority_are_not_guessed_between(self):
        tied = config(('https://dofusretro.cdn.ankama.com/static-data/612/', 1, False),
                      ('https://dofusretro.cdn.ankama.com/static-data/613/', 1, False))
        with self.assertRaisesRegex(ValueError, 'share priority 1'):
            langs.lang_root_from_config(tied)

    def test_the_config_is_read_from_the_retro_manifest_on_the_retro_bundles(self):
        entry = object()
        with mock.patch.object(langs.cytrus_cdn, 'find_file', return_value=entry) as find, \
                mock.patch.object(langs.cytrus_cdn, 'fetch_file', return_value=CLIENT) as fetch:
            self.assertEqual(LIVE_ROOT, langs.lang_root(manifest=b'manifest'))
        find.assert_called_once_with(b'manifest', 'resources/app/retroclient/config.xml')
        fetch.assert_called_once_with(entry, game='retro')

    def test_a_manifest_without_the_client_config_is_refused(self):
        with mock.patch.object(langs.cytrus_cdn, 'find_file', return_value=None), \
                self.assertRaises(LookupError):
            langs.lang_root(manifest=b'manifest')

    def test_the_root_is_resolved_once_per_process(self):
        with mock.patch.object(langs.cytrus_cdn, 'download_manifest', return_value=b'manifest') as download, \
                mock.patch.object(langs.cytrus_cdn, 'find_file', return_value=object()), \
                mock.patch.object(langs.cytrus_cdn, 'fetch_file', return_value=CLIENT):
            self.assertEqual([LIVE_ROOT, LIVE_ROOT], [langs.lang_root(), langs.lang_root()])
        download.assert_called_once_with('retro')

    def test_a_root_the_pipeline_resolved_is_taken_without_a_download(self):
        os.environ[langs.LANG_ROOT_ENV] = LIVE_ROOT + '/'
        with mock.patch.object(langs.cytrus_cdn, 'download_manifest') as download:
            self.assertEqual(LIVE_ROOT, langs.lang_root())
        download.assert_not_called()


class TheRetroLangFilesAreReadUnderThatRootTests(TestCase):
    def test_the_versions_file_lists_each_category_with_its_version(self):
        body = '&f=items,fr,1399|itemstats,fr,1398|itemsets,fr,1393|broken|monsterdrops,fr,25'
        self.assertEqual({'items': '1399', 'itemstats': '1398', 'itemsets': '1393', 'monsterdrops': '25'},
                         langs.parse_manifest(body))

    def test_the_versions_and_the_swf_are_fetched_under_the_given_root(self):
        urls = []

        def get(url, timeout):
            urls.append(url)
            if url.endswith('.txt'):
                return Response(text='&f=items,fr,1399')
            return Response(content=b'FWS' + bytes(5) + b'payload')

        with mock.patch.object(langs.requests, 'get', side_effect=get), \
                mock.patch.object(langs, 'parse_lang_swf', return_value={}), \
                tempfile.TemporaryDirectory() as folder:
            self.assertEqual({'items': '1399'}, langs.fetch_manifest('fr', LIVE_ROOT))
            self.assertEqual(b'payload', langs.download_swf('items', 'fr', '1399', Path(folder), LIVE_ROOT))
        self.assertEqual([LIVE_ROOT + '/versions_fr.txt', LIVE_ROOT + '/swf/items_fr_1399.swf'], urls)

    def test_the_download_step_reads_every_category_under_the_live_root(self):
        urls = []

        def get(url, timeout):
            urls.append(url)
            if url.endswith('.txt'):
                return Response(text='&f=items,fr,1399|itemstats,fr,1398')
            return Response(content=b'FWS' + bytes(5))

        with mock.patch.object(langs, 'lang_root', return_value=LIVE_ROOT), \
                mock.patch.object(langs.requests, 'get', side_effect=get), \
                mock.patch.object(langs, 'parse_lang_swf', return_value={}), \
                tempfile.TemporaryDirectory() as folder, mock.patch('sys.stdout'):
            self.assertEqual(0, langs.main(['--categories', 'items', 'itemstats', '--dest', folder]))
        self.assertEqual([LIVE_ROOT + '/versions_fr.txt', LIVE_ROOT + '/swf/items_fr_1399.swf',
                          LIVE_ROOT + '/swf/itemstats_fr_1398.swf'], urls)

    def test_the_monster_and_subarea_steps_take_the_same_root(self):
        with mock.patch.object(langs, 'lang_root', return_value=LIVE_ROOT):
            self.assertEqual(LIVE_ROOT, get_monsters_retro._ankama_lang_root())
            self.assertEqual(LIVE_ROOT, store_retro_subarea_languages._lang_root())

    def test_no_retro_step_names_the_old_frozen_lang_root(self):
        folder = Path(__file__).resolve().parents[2] / 'itemscraper'
        for name in ('download_retro_langs.py', 'get_monsters_retro.py', 'store_retro_subarea_languages.py'):
            with self.subTest(name=name):
                source = (folder / name).read_text(encoding='utf-8')
                self.assertNotIn("'https://dofusretro.cdn.ankama.com/lang'", source)
                self.assertNotIn('"https://dofusretro.cdn.ankama.com/lang"', source)


class TheRetroWatchNamesTheLangTreeTests(TestCase):
    def test_the_watched_lang_root_is_a_static_data_tree_of_the_retro_cdn(self):
        import fashionista_version as ours
        self.assertTrue(ours.WATCHED_RETRO_LANG_ROOT.startswith('https://dofusretro.cdn.ankama.com/static-data/'))
        self.assertTrue(ours.WATCHED_RETRO_LANG_ROOT.endswith('/lang'))
