# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Each Retro monster zone comes from the game's monsters and maps lang files, never from a third-party crawl."""
import contextlib
import html
import io
import json
import os
import re
import sqlite3
import tempfile
import unittest
from unittest import mock

from django.test import SimpleTestCase, TestCase

from chardata.tests import itemscraper_module

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RAW_DIR = os.path.join(REPO, 'itemscraper', 'retro_raw')
LANGUAGES = ('fr', 'en', 'es', 'pt', 'de')


def store():
    return itemscraper_module('store_retro_monster_subareas')


def read_source(*parts):
    with open(os.path.join(REPO, *parts), encoding='utf-8') as handle:
        return handle.read()


def sub(name, area):
    return {'n': name, 'a': area}


def fixture_maps():
    french = {
        'a': {1: {'n': 'Amakna'}, 2: {'n': 'Zone Deux'}},
        'sa': {10: sub('Forêt', 1), 11: sub('Forêt', 1), 20: sub('//Divers', 2),
               30: sub('Plaine', 1), 40: sub('Sans carte', 1)},
        'm': {100: {'sa': 10}, 101: {'sa': 11}, 200: {'sa': 20}, 300: {'sa': 30}},
    }
    english = {
        'a': {1: {'n': 'Amakna'}, 2: {'n': 'Second zone'}},
        'sa': {10: sub('Forest', 1), 11: sub('Forest', 1), 20: sub('//Misc', 2),
               40: sub('No map', 1)},
        'm': {},
    }
    return {'fr': french, 'en': english}


def spawn(areas=(), maps=()):
    return {'a': list(areas), 'm': list(maps)}


def names(rows, monster_id, language):
    return [row[3] for row in sorted(rows) if row[0] == monster_id and row[1] == language]


class TheRowsFollowTheLangFilesTests(SimpleTestCase):

    def build(self, spawns, languages=('fr', 'en')):
        return store().build_rows(spawns, fixture_maps(), languages)

    def test_rows_follow_the_subarea_id_order(self):
        rows, _, _, _ = self.build({1: spawn(areas=[30, 20, 10])})
        self.assertEqual(['Forêt', 'Zone Deux', 'Plaine'], names(rows, 1, 'fr'))

    def test_a_subarea_named_with_two_slashes_shows_its_area_name(self):
        rows, _, _, _ = self.build({1: spawn(areas=[20])})
        self.assertEqual(['Zone Deux'], names(rows, 1, 'fr'))
        self.assertEqual(['Second zone'], names(rows, 1, 'en'))

    def test_a_monster_with_only_spawn_maps_gets_the_subareas_of_those_maps(self):
        rows, _, _, _ = self.build({1: spawn(maps=[300, 200, 9999])})
        self.assertEqual(['Zone Deux', 'Plaine'], names(rows, 1, 'fr'))

    def test_a_subarea_with_no_map_is_left_out_and_counted(self):
        rows, unresolved, mapless, _ = self.build({1: spawn(areas=[40, 10])})
        self.assertEqual(['Forêt'], names(rows, 1, 'fr'))
        self.assertEqual([(1, 40)], mapless)
        self.assertEqual([], unresolved)

    def test_a_subarea_the_maps_file_lacks_is_reported_not_stored(self):
        rows, unresolved, mapless, _ = self.build({1: spawn(areas=[99, 10])})
        self.assertEqual(['Forêt'], names(rows, 1, 'fr'))
        self.assertEqual([(1, 99)], unresolved)
        self.assertEqual([], mapless)

    def test_a_name_the_language_lacks_falls_back_to_french(self):
        rows, _, _, in_french = self.build({1: spawn(areas=[10, 30])})
        self.assertEqual(['Forest', 'Plaine'], names(rows, 1, 'en'))
        self.assertEqual(1, in_french['en'])

    def test_a_name_listed_twice_is_stored_once(self):
        rows, _, _, _ = self.build({1: spawn(areas=[10, 11, 30])})
        self.assertEqual(['Forêt', 'Plaine'], names(rows, 1, 'fr'))
        self.assertEqual([(1, 'fr', 0, 'Forêt'), (1, 'fr', 1, 'Plaine')],
                         sorted(row for row in rows if row[1] == 'fr'))
        self.assertEqual(['Forest'], names(rows, 1, 'en')[:1])
        self.assertEqual(2, len(names(rows, 1, 'en')))

    def test_too_few_french_rows_are_refused(self):
        module = store()
        with self.assertRaisesRegex(ValueError, 'French subarea rows'):
            module.check_rows([(1, 'fr', 0, 'Forêt')] * (module.MIN_FR_ROWS - 1))
        module.check_rows([(1, 'fr', 0, 'Forêt')] * module.MIN_FR_ROWS)

    def test_a_double_encoded_name_is_refused(self):
        module = store()
        double = 'forêt'.encode('utf-8').decode('latin-1')
        replaced = 'for' + chr(0xFFFD) + 't'
        control = 'for' + chr(0x82) + 't'
        for name in (double, replaced, control):
            with self.subTest(name=name):
                self.assertEqual([name], module.broken_names([(1, 'fr', 0, name)]))
        self.assertEqual([], module.broken_names(
            [(1, 'fr', 0, "Forêt d'Astrub"), (1, 'fr', 1, 'Quartier des Bûcherons')]))


class ANameWithTwoSlashesTests(SimpleTestCase):

    def test_a_language_lacking_the_area_shows_the_french_area_name(self):
        french = {'a': {3: {'n': 'Zone Trois'}}, 'sa': {50: sub('//Divers', 3)},
                  'm': {500: {'sa': 50}}}
        english = {'a': {}, 'sa': {50: sub('//Misc', 3)}, 'm': {}}
        rows = store().build_rows({1: spawn(areas=[50])}, {'fr': french, 'en': english},
                                  ('fr', 'en'))[0]
        self.assertEqual(['Zone Trois'], names(rows, 1, 'en'))


class AMissingLanguageFileTests(SimpleTestCase):

    def write(self, folder, name, content):
        with open(os.path.join(folder, name), 'w', encoding='utf-8') as handle:
            json.dump(content, handle)

    def raw_folder(self, folder):
        french = fixture_maps()['fr']
        self.write(folder, 'monsters_fr.json', {
            'VERSION': 7, 'M': {'1': {'spawn': {'a': [10, 30], 'sa': [0]}}}})
        self.write(folder, 'maps_fr.json', {'VERSION': 5, 'MA': {
            key: {str(i): row for i, row in table.items()} for key, table in french.items()}})

    def test_a_missing_language_file_is_reported_and_gives_no_rows(self):
        module = store()
        with tempfile.TemporaryDirectory() as folder:
            self.raw_folder(folder)
            spawns, maps, versions, missing = module.read_lang(folder, ('fr', 'en'))
            self.assertEqual(['en'], missing)
            self.assertEqual(['fr'], list(maps))
            self.assertEqual({'monsters_fr': 7, 'maps_fr': 5}, versions)
            database = os.path.join(folder, 'scratch.db')
            connection = sqlite3.connect(database)
            connection.execute('CREATE TABLE monster_names (monster_ankama_id INTEGER)')
            connection.execute('INSERT INTO monster_names VALUES (1)')
            connection.commit()
            connection.close()
            out = io.StringIO()
            with mock.patch.object(module, 'DB_PATH', database), \
                    mock.patch.object(module, 'MIN_FR_ROWS', 0), \
                    mock.patch('store_item_obtainment._save_db_to_dump'), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(0, module.main(['--raw-dir', folder, '--languages', 'fr', 'en']))
            connection = sqlite3.connect(database)
            try:
                stored = connection.execute(
                    'SELECT language, COUNT(*) FROM monster_subareas GROUP BY language').fetchall()
            finally:
                connection.close()
        self.assertEqual([('fr', 2)], stored)
        self.assertIn('warning: maps_en.json not found, no en rows', out.getvalue())
        self.assertIn('stored 2 subarea rows for 1 retro monsters (1 with an encyclopedia page)',
                      out.getvalue())

    def scratch_database(self, folder):
        database = os.path.join(folder, 'scratch.db')
        connection = sqlite3.connect(database)
        connection.execute('CREATE TABLE monster_names (monster_ankama_id INTEGER)')
        connection.execute('INSERT INTO monster_names VALUES (1)')
        connection.execute('CREATE TABLE monster_subareas (marker TEXT)')
        connection.execute("INSERT INTO monster_subareas VALUES ('sentinel')")
        connection.commit()
        connection.close()
        return database

    def sentinel_rows(self, database):
        connection = sqlite3.connect(database)
        try:
            return connection.execute('SELECT marker FROM monster_subareas').fetchall()
        finally:
            connection.close()

    def test_main_refuses_a_table_with_too_few_french_rows(self):
        module = store()
        with tempfile.TemporaryDirectory() as folder:
            self.raw_folder(folder)
            database = self.scratch_database(folder)
            with mock.patch.object(module, 'DB_PATH', database), \
                    mock.patch('store_item_obtainment._save_db_to_dump') as dump, \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaisesRegex(ValueError, 'French subarea rows'):
                    module.main(['--raw-dir', folder, '--languages', 'fr'])
            self.assertEqual([('sentinel',)], self.sentinel_rows(database))
            dump.assert_not_called()

    def test_main_refuses_a_name_with_a_broken_encoding(self):
        module = store()
        double = 'forêt'.encode('utf-8').decode('latin-1')
        with tempfile.TemporaryDirectory() as folder:
            self.raw_folder(folder)
            self.write(folder, 'maps_fr.json', {'VERSION': 5, 'MA': {
                'a': {'1': {'n': 'Amakna'}},
                'sa': {'10': {'n': double, 'a': 1}, '30': {'n': 'Plaine', 'a': 1}},
                'm': {'100': {'sa': 10}, '300': {'sa': 30}}}})
            database = self.scratch_database(folder)
            out = io.StringIO()
            with mock.patch.object(module, 'DB_PATH', database), \
                    mock.patch.object(module, 'MIN_FR_ROWS', 0), \
                    mock.patch('store_item_obtainment._save_db_to_dump') as dump, \
                    contextlib.redirect_stdout(out):
                self.assertEqual(1, module.main(['--raw-dir', folder, '--languages', 'fr']))
            self.assertIn('broken encoding', out.getvalue())
            self.assertEqual([('sentinel',)], self.sentinel_rows(database))
            dump.assert_not_called()

    def test_an_insert_that_fails_leaves_the_old_table_in_place(self):
        module = store()
        with tempfile.TemporaryDirectory() as folder:
            self.raw_folder(folder)
            database = self.scratch_database(folder)
            with mock.patch.object(module, 'DB_PATH', database), \
                    mock.patch.object(module, 'MIN_FR_ROWS', 0), \
                    mock.patch.object(module, 'build_rows',
                                      return_value=([(1, 'fr', 0, None)], [], [], {'fr': 0})), \
                    mock.patch.object(module, 'broken_names', return_value=[]), \
                    mock.patch('store_item_obtainment._save_db_to_dump') as dump, \
                    contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(sqlite3.IntegrityError):
                    module.main(['--raw-dir', folder, '--languages', 'fr'])
            self.assertEqual([('sentinel',)], self.sentinel_rows(database))
            dump.assert_not_called()

    def test_a_spawn_map_the_maps_file_does_not_place_is_reported(self):
        module = store()
        with tempfile.TemporaryDirectory() as folder:
            self.raw_folder(folder)
            self.write(folder, 'monsters_fr.json', {
                'VERSION': 7, 'M': {'1': {'spawn': {'a': [10, 30], 'm': [100, 9999]}}}})
            database = self.scratch_database(folder)
            out = io.StringIO()
            with mock.patch.object(module, 'DB_PATH', database), \
                    mock.patch.object(module, 'MIN_FR_ROWS', 0), \
                    mock.patch('store_item_obtainment._save_db_to_dump'), \
                    contextlib.redirect_stdout(out):
                self.assertEqual(0, module.main(['--raw-dir', folder, '--languages', 'fr']))
        self.assertIn('warning: map 9999 of monster 1 has no subarea in maps_fr.json', out.getvalue())
        self.assertNotIn('warning: map 100 ', out.getvalue())


class TheStoredTableMatchesTheRawFilesTests(SimpleTestCase):

    def setUp(self):
        for name in ('monsters_fr.json', 'maps_fr.json'):
            if not os.path.exists(os.path.join(RAW_DIR, name)):
                raise unittest.SkipTest('retro_raw is gitignored; download the Retro monsters and maps lang '
                                        'files to compare the table with them')
        self.module = store()
        self.spawns, self.maps, _, _ = self.module.read_lang(RAW_DIR, LANGUAGES)

    def test_the_table_holds_the_rows_the_lang_files_give(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        rows = self.module.build_rows(self.spawns, self.maps, LANGUAGES)[0]
        connection = sqlite3.connect('file:%s?mode=ro' % get_items_db_path('retro'), uri=True)
        try:
            shipped = connection.execute(
                'SELECT monster_ankama_id, language, position, name FROM monster_subareas').fetchall()
        finally:
            connection.close()
        self.assertEqual(sorted(rows), sorted(shipped))

    def test_every_monster_the_lang_places_has_rows(self):
        rows = self.module.build_rows(self.spawns, self.maps, LANGUAGES)[0]
        placed = {row[0] for row in rows if row[1] == 'fr'}
        with_a_map = self.module.subareas_with_a_map(self.maps['fr'])
        map_subarea = self.module.map_subareas(self.maps['fr'])
        for monster_id, spawn_ in self.spawns.items():
            found = set(spawn_['a']) | {map_subarea[i] for i in spawn_['m'] if i in map_subarea}
            expected = bool(found & with_a_map & set(self.maps['fr']['sa']))
            with self.subTest(monster=monster_id):
                self.assertEqual(expected, monster_id in placed)
        self.assertGreater(len(placed), 900)


class TheRetroPipelineReadsTheLangFilesTests(SimpleTestCase):

    def test_the_store_reads_no_third_party_host(self):
        source = read_source('itemscraper', 'store_retro_monster_subareas.py').lower()
        self.assertNotIn('http', source)
        self.assertNotIn('solomonk', source)

    def test_the_retro_pipeline_downloads_the_maps_file_of_each_language(self):
        source = read_source('update_data_retro.py')
        commands = re.findall(r'"--categories"[^\]]*', source)
        self.assertEqual(2, len([c for c in commands if '"items"' in c]))
        for command in (c for c in commands if '"items"' in c):
            with self.subTest(command=command[:60]):
                self.assertIn('"maps"', command)

    def test_the_retro_pipeline_has_no_subarea_language_patch(self):
        for name in ('update_data_retro.py', 'update_all.py'):
            with self.subTest(name=name):
                source = read_source(name)
                self.assertNotIn('store_retro_subarea_languages', source)
                self.assertNotIn('subarea-langs', source)
        self.assertIn('store_retro_monster_subareas.py', read_source('update_data_retro.py'))


class ARetroMonsterPageTests(TestCase):

    def test_a_retro_monster_page_lists_the_zones_of_its_spawn(self):
        from fashionistapulp.fashionista_config import get_items_db_path
        connection = sqlite3.connect('file:%s?mode=ro' % get_items_db_path('retro'), uri=True)
        try:
            for language in ('en', 'fr'):
                zones = [row[0] for row in connection.execute(
                    'SELECT name FROM monster_subareas WHERE monster_ankama_id = 121 '
                    'AND language = ? ORDER BY position', (language,))]
                if zones:
                    break
        finally:
            connection.close()
        self.assertTrue(zones)
        response = self.client.get('/retro/encyclopedia/monster/121-minotoror/')
        self.assertEqual(200, response.status_code)
        body = html.unescape(response.content.decode('utf-8'))
        self.assertIn('id="monster-subareas"', body)
        self.assertIn(zones[0], body)
