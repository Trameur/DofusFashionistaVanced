# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Retro steps read main by default, and --release beta reads the beta client into retrobeta folders."""
import contextlib
import io
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import zlib
from unittest import TestCase, mock
from urllib.error import URLError

ROOT = Path(__file__).resolve().parents[2]
ITEMSCRAPER = ROOT / 'itemscraper'
sys.path.insert(0, str(ITEMSCRAPER))
sys.path.insert(0, str(ROOT))
import cytrus_cdn  # noqa: E402
import download_retro_images as images  # noqa: E402
import download_retro_langs as langs  # noqa: E402
import download_retro_monster_artworks as artworks  # noqa: E402
import download_retro_spell_images as spells  # noqa: E402
import get_monsters_retro as drops  # noqa: E402
import retro_release  # noqa: E402
import scrape_retro_pet_bonuses as pets  # noqa: E402
import update_data_retro as pipeline  # noqa: E402

CDN = 'https://cytrus.cdn.ankama.com'
CATALOG = json.dumps({'games': {'retro': {'platforms': {'windows': {'main': 'M1', 'beta': 'B1'}}}}}).encode()
STATIC = ROOT / 'fashionsite' / 'chardata' / 'static' / 'chardata'


class Body(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def as2(value):
    low, high = struct.unpack('<II', struct.pack('<d', value))
    return struct.unpack('<d', struct.pack('<II', high, low))[0]


class TheReleaseNamesItsFoldersTests(TestCase):
    def test_main_keeps_the_folders_it_always_had(self):
        self.assertEqual(ITEMSCRAPER / 'retro_raw', retro_release.raw_dir())
        self.assertEqual(ITEMSCRAPER / 'retro', retro_release.work_dir())
        self.assertEqual(ROOT / 'fashionistapulp' / 'fashionistapulp' / 'item_db_dumped_retro.dump',
                         retro_release.dump_path())
        self.assertEqual(STATIC / 'spells' / 'retro', retro_release.static_dir('spells'))

    def test_the_beta_writes_under_the_retrobeta_key(self):
        self.assertEqual(ITEMSCRAPER / 'retrobeta_raw', retro_release.raw_dir('beta'))
        self.assertEqual(ITEMSCRAPER / 'retrobeta', retro_release.work_dir('beta'))
        self.assertEqual(ITEMSCRAPER / 'retrobeta' / 'item_db_dumped_retrobeta.dump',
                         retro_release.dump_path('beta'))
        self.assertEqual(STATIC / 'monsters' / 'retrobeta', retro_release.static_dir('monsters', 'beta'))

    def test_the_cdn_knows_both_retro_releases(self):
        self.assertEqual(('retro', 'main'), cytrus_cdn.RELEASES['retro'])
        self.assertEqual(('retro', 'beta'), cytrus_cdn.RELEASES['retrobeta'])


class EachReleaseReadsItsOwnManifestTests(TestCase):
    def manifest_urls(self, key):
        seen = []

        def urlopen(url, timeout=None):
            seen.append(url)
            return Body(CATALOG if url.endswith('cytrus.json') else b'manifest')

        with mock.patch.object(cytrus_cdn.urllib.request, 'urlopen', side_effect=urlopen):
            cytrus_cdn.download_manifest(key)
        return seen[1:]

    def test_the_cdn_manifest_of_each_release(self):
        self.assertEqual([CDN + '/retro/releases/main/windows/M1.manifest'], self.manifest_urls('retro'))
        self.assertEqual([CDN + '/retro/releases/beta/windows/B1.manifest'], self.manifest_urls('retrobeta'))

    def artwork_urls(self, *release):
        seen = []

        def fetch(url, byte_range=None):
            seen.append(url)
            return CATALOG if url.endswith('cytrus.json') else b'manifest'

        with mock.patch.object(artworks, 'fetch_bytes', side_effect=fetch), \
                contextlib.redirect_stdout(io.StringIO()):
            artworks.download_manifest(*release)
        return seen

    def test_the_clip_steps_read_the_manifest_of_their_release(self):
        self.assertEqual([CDN + '/cytrus.json', CDN + '/retro/releases/main/windows/M1.manifest'],
                         self.artwork_urls())
        self.assertEqual([CDN + '/cytrus.json', CDN + '/retro/releases/beta/windows/B1.manifest'],
                         self.artwork_urls('beta'))

    def test_both_releases_share_the_retro_bundles(self):
        seen = []
        entry = {'chunks': [], 'hash': 'h', 'size': 4}
        with mock.patch.object(artworks, 'fetch_bytes', side_effect=lambda url, r=None: seen.append(url) or b'data'), \
                mock.patch('builtins.open', mock.mock_open()):
            artworks.download_file(entry, {'h': ('abcdef', 0)}, 'out.swf')
        self.assertEqual([CDN + '/retro/bundles/ab/abcdef'], seen)


class TheBetaLangRootComesFromTheBetaConfigTests(TestCase):
    def setUp(self):
        self.addCleanup(langs._resolved_roots.clear)
        langs._resolved_roots.clear()
        patcher = mock.patch.dict(os.environ)
        patcher.start()
        self.addCleanup(patcher.stop)
        os.environ.pop('RETRO_LANG_ROOT', None)
        os.environ.pop('RETROBETA_LANG_ROOT', None)

    def test_each_release_hands_its_root_through_its_own_variable(self):
        self.assertEqual('RETRO_LANG_ROOT', langs.lang_root_env())
        self.assertEqual('RETROBETA_LANG_ROOT', langs.lang_root_env('retrobeta'))

    def test_the_beta_root_is_read_from_the_beta_manifest(self):
        config = (b'<config><clientdata><environment><databank>'
                  b'<dataserver url="https://dofusretro.cdn.ankama.com/static-data/638/" priority="1"/>'
                  b'</databank></environment></clientdata></config>')
        with mock.patch.object(langs.cytrus_cdn, 'download_manifest', return_value=b'm') as download, \
                mock.patch.object(langs.cytrus_cdn, 'find_file', return_value={}), \
                mock.patch.object(langs.cytrus_cdn, 'fetch_file', return_value=config) as fetch:
            root = langs.lang_root('retrobeta')
        self.assertEqual('https://dofusretro.cdn.ankama.com/static-data/638/lang', root)
        download.assert_called_once_with('retrobeta')
        self.assertEqual('retro', fetch.call_args.kwargs['game'])

    def download_call(self, argv):
        with mock.patch.object(langs, 'lang_root', return_value='ROOT') as root, \
                mock.patch.object(langs, 'fetch_manifest', return_value={'items': '7'}), \
                mock.patch.object(langs, 'download_swf', return_value=b'') as download, \
                contextlib.redirect_stdout(io.StringIO()):
            langs.main(['--categories', 'items'] + argv)
        return root.call_args.args, download.call_args.args

    def test_the_lang_download_keeps_its_default_folder_and_root(self):
        root, download = self.download_call([])
        self.assertEqual(('retro',), root)
        self.assertEqual(('items', 'fr', '7', Path('itemscraper/retro_raw'), 'ROOT'), download)

    def test_the_beta_lang_download_writes_into_the_beta_raw_folder(self):
        root, download = self.download_call(['--release', 'beta'])
        self.assertEqual(('retrobeta',), root)
        self.assertEqual(Path(retro_release.raw_dir('beta')), download[3])

    def test_the_beta_drops_read_the_beta_root(self):
        with mock.patch.object(langs, 'lang_root', return_value='ROOT') as root:
            drops._ankama_lang_root('beta')
            drops._ankama_lang_root()
        self.assertEqual([mock.call('retrobeta'), mock.call()], root.call_args_list)


class EachStepWritesTheFoldersOfItsReleaseTests(TestCase):
    def test_monster_artworks(self):
        self.assertEqual([str(STATIC / 'monsters' / 'retro' / '96'),
                          str(ROOT / 'fashionsite' / 'staticfiles' / 'chardata' / 'monsters' / 'retro' / '96')],
                         artworks.target_dirs())
        self.assertTrue(all(Path(d).parts[-2] == 'retrobeta' for d in artworks.target_dirs('beta')))

    def test_item_icons(self):
        items = {'10': {'t': 1, 'g': 5, 'n': 'Amulette'}, '11': {'t': 18, 'g': 6, 'n': 'Familier'}}
        names = {'10': 'Amulet', '11': 'Pet'}
        main = sorted(dest for _iid, dest, _clip in images.icon_clips(items, names))
        beta = sorted(dest for _iid, dest, _clip in images.icon_clips(items, names, 'beta'))
        self.assertEqual([STATIC / 'items' / 'retro' / '60x60' / 'amulet-60-60.png',
                          STATIC / 'pets' / 'retro' / '60x60' / 'pet-60-60.png'], main)
        self.assertEqual([STATIC / 'items' / 'retrobeta' / '60x60' / 'amulet-60-60.png',
                          STATIC / 'pets' / 'retrobeta' / '60x60' / 'pet-60-60.png'], beta)

    def test_spell_icons(self):
        self.assertEqual((spells.DEST, spells.LANG_SPELLS, spells.STENCIL_CACHE, spells.SPELL_REFERENCE),
                         spells.release_paths('main'))
        dest, lang, stencils, _reference = spells.release_paths('beta')
        self.assertEqual(STATIC / 'spells' / 'retrobeta', dest)
        self.assertEqual(ITEMSCRAPER / 'retrobeta_raw' / 'spells_fr.json', lang)
        self.assertEqual(ITEMSCRAPER / 'retrobeta_raw' / 'spell_stencils', stencils)

    def test_pet_bonuses(self):
        self.assertEqual((pets.RAW_DIR, pets.OUT_PATH), pets.release_paths())
        raw, out = pets.release_paths('beta')
        self.assertEqual(str(ITEMSCRAPER / 'retrobeta_raw'), raw)
        self.assertEqual(str(ITEMSCRAPER / 'retrobeta' / 'retro_pet_bonuses.json'), out)


class OnlyTheClipsThatChangedAreRenderedTests(TestCase):
    def test_a_monster_is_rendered_again_only_when_its_clip_moved(self):
        art = artworks.ARTWORK_PREFIX
        sprite = artworks.SPRITE_PREFIX
        main_files = {art + '1.swf': {'hash': 'a'}, art + '2.swf': {'hash': 'b'}, sprite + '3.swf': {'hash': 'c'},
                      art + '4.swf': {'hash': 'd'}}
        files = {art + '1.swf': {'hash': 'a'}, art + '2.swf': {'hash': 'B'}, sprite + '3.swf': {'hash': 'C'},
                 art + '4.swf': {'hash': 'd'}, art + '5.swf': {'hash': 'e'}}
        wanted = {100: 1, 200: 2, 300: 3, 400: 4, 500: 5}
        main_gfx = {100: 1, 200: 2, 300: 3, 400: 1}
        self.assertEqual({200: 2, 300: 3, 400: 4, 500: 5},
                         artworks.changed_since_main(wanted, main_gfx, files, main_files))

    def test_a_spell_icon_is_composed_again_only_when_its_recipe_or_stencil_moved(self):
        stencil = spells.UP_PREFIX
        lang = {'1': {'i': {'up': 7}}, '2': {'i': {'up': 8}}, '3': {'i': {'up': 9}}}
        main_lang = {'1': {'i': {'up': 7}}, '2': {'i': {'up': 8}}, '3': {'i': {'up': 1}}}
        files = {stencil + '7.swf': {'hash': 'x'}, stencil + '8.swf': {'hash': 'Y'}}
        main_files = {stencil + '7.swf': {'hash': 'x'}, stencil + '8.swf': {'hash': 'y'}}
        self.assertEqual({'Deux': 2, 'Trois': 3},
                         spells.recipes_that_changed({'Un': 1, 'Deux': 2, 'Trois': 3},
                                                     lang, main_lang, files, main_files))


class TheBetaDropsComeFromTheBetaLangTests(TestCase):
    def test_a_lang_double_is_read_with_its_words_swapped(self):
        self.assertEqual(0.5, drops.as2_number(as2(0.5)))
        self.assertEqual(7, drops.as2_number(7))
        self.assertEqual('x', drops.as2_number('x'))

    def test_the_last_grade_gives_the_rate(self):
        self.assertEqual(3.0, drops.drop_rate({'t': [1, 2.5, 3]}))
        self.assertEqual(0.0, drops.drop_rate({'t': []}))

    def test_the_rate_is_put_on_the_scale_of_main_with_its_sr(self):
        self.assertAlmostEqual(10.0, drops.drop_rate({'t': [100.0] * 5, 'sr': 10}))
        self.assertAlmostEqual(100 / 13, drops.drop_rate({'t': [100.0] * 5, 'sr': 13}))

    def test_main_rows_are_reused_where_the_lang_did_not_change(self):
        main_index = {'10': [{'monster_ankama_id': 1, 'names': {'fr': 'Bouftou'}, 'rates': [9.0]}],
                      '11': [{'monster_ankama_id': 2, 'names': {'fr': 'Larve'}, 'rates': [4.0]}],
                      '12': [{'monster_ankama_id': 3, 'names': {'fr': 'Tofu'}, 'rates': [2.0]}],
                      '13': [{'monster_ankama_id': 4, 'names': {'fr': 'Arakne'}, 'rates': [1.0]}]}
        main_lang = {(10, 1): {'t': [5]}, (11, 2): {'t': [5], 'sr': 2}, (12, 3): {'t': [5]},
                     (13, 4): {'t': [5], 'pp': 400}, (20, 6): {'t': [1]}}
        lang = {(10, 1): {'t': [5]}, (11, 2): {'t': [6], 'sr': 2}, (13, 4): {'t': [5], 'pp': 500},
                (20, 6): {'t': [1]}, (21, 7): {'t': [8], 'sr': 4}, (22, 8): {'t': [0]}}
        index, counts = drops.merge_release_drops(main_index, main_lang, lang, lambda mid: {'fr': 'M%d' % mid})
        self.assertEqual({'read': 2, 'reused': 2, 'reused_unlisted': 0, 'removed': 1, 'zero_rate': 1,
                          'left_out_as_main': 1, 'reused_other_fields': 1}, counts)
        self.assertEqual(main_index['10'], index['10'])
        self.assertEqual([{'monster_ankama_id': 2, 'names': {'fr': 'Larve'}, 'rates': [3.0]}], index['11'])
        self.assertNotIn('12', index)
        self.assertEqual(main_index['13'], index['13'])
        self.assertEqual([{'monster_ankama_id': 7, 'names': {'fr': 'M7'}, 'rates': [2.0]}], index['21'])
        self.assertNotIn('20', index)
        self.assertNotIn('22', index)

    def test_every_main_row_is_reused_when_the_beta_lang_has_no_drops(self):
        main_index = {'10': [{'monster_ankama_id': 1, 'names': {}, 'rates': [9.0]}]}
        index, counts = drops.merge_release_drops(main_index, None, None, dict)
        self.assertEqual(main_index, index)
        self.assertEqual(1, counts['reused'])

    def test_every_main_row_is_reused_when_a_lang_cannot_be_read(self):
        main_index = {'10': [{'monster_ankama_id': 1, 'names': {'fr': 'Bouftou'}, 'rates': [9.0]}]}
        failures = (URLError('down'), TimeoutError('slow'), ConnectionResetError('reset'),
                    zlib.error('cut'), struct.error('short'), IndexError('garbage'))
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'transformed_drops_retro.json'
            path.write_text(json.dumps(main_index), encoding='utf-8')
            for failure in failures:
                for broken in (retro_release.BETA, retro_release.MAIN):
                    def lang_drops(root, lang='fr', broken=broken, failure=failure):
                        if root == broken:
                            raise failure
                        return '1', {(10, 1): {'t': [7]}, (11, 2): {'t': [3]}}
                    out = io.StringIO()
                    root_of = mock.patch.object(drops, '_ankama_lang_root', lambda release=retro_release.MAIN: release)
                    with root_of, mock.patch.object(drops, 'lang_drops', lang_drops), contextlib.redirect_stdout(out):
                        index, counts = drops.build_release_drops(retro_release.BETA, path)
                    with self.subTest(failure=type(failure).__name__, broken=broken):
                        self.assertEqual(main_index, index)
                        self.assertEqual(1, counts['reused'])
                        self.assertEqual(0, counts['read'])
                        self.assertIn('the %s monsterdrops did not answer' % broken, out.getvalue())


class ThePipelineRunsTheStepsOfItsReleaseTests(TestCase):
    def steps(self, *argv):
        steps = []

        def run_step(label, cmd, cwd=None):
            steps.append((label, [str(part) for part in cmd], str(cwd or pipeline.ROOT)))
            return True, []

        with mock.patch.object(pipeline, 'run_step', side_effect=run_step), \
                mock.patch.object(pipeline, 'export_lang_root', return_value='ROOT'), \
                mock.patch.object(sys, 'argv', ['update_data_retro.py'] + list(argv)), \
                contextlib.redirect_stdout(io.StringIO()):
            pipeline.main()
        return steps

    def test_the_default_run_names_no_release_and_keeps_its_main_paths(self):
        steps = dict((label, cmd) for label, cmd, _cwd in self.steps())
        self.assertFalse([label for label, cmd in steps.items() if '--release' in cmd])
        self.assertFalse([label for label, cmd in steps.items() if any('retrobeta' in part for part in cmd)])
        self.assertEqual(pipeline.RETRO_RAW_DIR, steps['lang/download-fr'][-1])
        self.assertEqual(['--input-dir', pipeline.RETRO_WORK_DIR, '--dump-output', pipeline.RETRO_DUMP],
                         steps['items/dump'][2:])
        self.assertEqual(['get_monsters_retro.py', '--output', 'transformed_drops_retro.json'],
                         steps['drops/transform'][1:])
        self.assertEqual(['download_retro_monster_artworks.py'], steps['monsters/artworks'][1:])
        self.assertEqual(['download_retro_spell_images.py'], steps['spell-images'][1:])
        self.assertIn('items/load-db', steps)

    def test_the_beta_run_writes_only_under_the_retrobeta_folders(self):
        steps = self.steps('--release', 'beta')
        labels = [label for label, _cmd, _cwd in steps]
        for skipped in ('items/load-db', 'drops/store', 'pets/scrape', 'monsters/grades', 'verify/rebuild',
                        'items/weapon-conversions', 'spells/reference'):
            self.assertNotIn(skipped, labels)
        beta_dirs = (str(retro_release.raw_dir('beta')), str(retro_release.work_dir('beta')))
        for label, cmd, _cwd in steps:
            paths = [part for part in cmd[2:] if os.sep in part or '/' in part]
            with self.subTest(step=label):
                self.assertTrue(all(part.startswith(beta_dirs) for part in paths), paths)
                self.assertNotIn(pipeline.RETRO_RAW_DIR, cmd)
                self.assertNotIn(pipeline.RETRO_DUMP, cmd)
        by_label = dict((label, cmd) for label, cmd, _cwd in steps)
        for label in ('lang/download-fr', 'drops/transform', 'monsters/artworks', 'item-images', 'spell-images'):
            with self.subTest(step=label):
                self.assertIn('beta', by_label[label][by_label[label].index('--release') + 1:][:1])
        self.assertEqual(str(retro_release.dump_path('beta')),
                         by_label['items/dump'][by_label['items/dump'].index('--dump-output') + 1])
