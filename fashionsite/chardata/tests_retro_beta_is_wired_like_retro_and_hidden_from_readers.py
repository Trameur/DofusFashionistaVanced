# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Retro Beta carries its own data, reads every Retro table through the Retro rules, forbids three more rows by default, builds a Retro set, and no reader page, route or sitemap names it."""
import glob
import importlib
import json
import os
import sqlite3

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.image_store import RETRO_PLACEHOLDER, get_image_url
from chardata.lock_forbid import DEFAULT_EXCLUSION_ANKAMA_IDS, DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION, get_default_exclusions
from chardata.spell_buffs import get_damage_spells_for_version, retro_spell_module
from chardata.targets import TARGET_VERSIONS
from chardata.tests_every_per_version_table_names_every_dofus_version import KEYED_TABLES, SPLIT_TABLES
from chardata.version_compat import CLASSES_NOT_IN_VERSION
from fashionistapulp import fashionista_config
from fashionistapulp.combat.rules import record_version
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import (GAME_VERSIONS, main_game, prefixed_reader_versions,
                                           reader_dofus_versions, switcher_games, version_keys)
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionsite import urls

KEY = 'retrobeta'
MAIN = 'retro'
HERE = os.path.dirname(os.path.abspath(__file__))
PULP = os.path.dirname(os.path.abspath(fashionista_config.__file__))
SITEMAP_SECTIONS = ('pages', 'items', 'sets', 'resources', 'monsters')
SHARED_WITH_THE_MAIN_GAME = ('combat_rules', 'combat_readings')
OWN_RULES = ('CLASSES_NOT_IN_VERSION', 'DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION')


def per_key_tables():
    """Every folder of per-version JSON files that holds a Retro file."""
    return sorted(os.path.dirname(path) for pattern in (os.path.join(HERE, '*', MAIN + '.json'),
                                                         os.path.join(PULP, '*', MAIN + '.json'))
                  for path in glob.glob(pattern))


def classes_of(version):
    with open(os.path.join(HERE, 'spell_reference', version + '.json'), encoding='utf-8') as handle:
        return set(json.load(handle))


def table(module_name, attribute):
    return getattr(importlib.import_module(module_name), attribute)


def beta_only_exclusions():
    return DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION[KEY][len(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION[MAIN]):]


class RetroBetaCarriesItsOwnDataTests(SimpleTestCase):

    def test_its_item_database_has_the_retro_catalogue_and_more(self):
        beta = {item.ankama_id for item in get_structure(KEY).get_available_items_list()}
        retro = {item.ankama_id for item in get_structure(MAIN).get_available_items_list()}
        self.assertGreater(len(beta), 0.95 * len(retro))
        self.assertTrue(beta - retro)

    def test_every_per_version_json_table_of_retro_has_a_retro_beta_file(self):
        folders = per_key_tables()
        self.assertGreaterEqual(len(folders), 5)
        for folder in folders:
            name = os.path.basename(folder)
            with self.subTest(table=name):
                if name in SHARED_WITH_THE_MAIN_GAME:
                    self.assertFalse(os.path.exists(os.path.join(folder, KEY + '.json')))
                    continue
                with open(os.path.join(folder, KEY + '.json'), encoding='utf-8') as handle:
                    self.assertTrue(json.load(handle))

    def test_it_reads_the_combat_record_of_its_main_game_and_takes_no_target(self):
        self.assertEqual(MAIN, record_version(KEY))
        self.assertIn(MAIN, TARGET_VERSIONS)
        self.assertNotIn(KEY, TARGET_VERSIONS)

    def test_its_spells_are_its_own_module_and_keep_every_retro_damage_spell(self):
        beta = get_damage_spells_for_version(KEY)
        retro = get_damage_spells_for_version(MAIN)
        self.assertIs(retro_spell_module(KEY).RETRO_DAMAGE_SPELLS, beta)
        self.assertIsNot(retro_spell_module(MAIN), retro_spell_module(KEY))
        self.assertEqual(set(), set(retro) - set(beta))
        self.assertEqual(classes_of(MAIN), classes_of(KEY))

    def test_the_classes_it_lacks_are_the_ones_its_spell_data_lacks(self):
        for version in (MAIN, KEY):
            with self.subTest(version=version):
                self.assertEqual(set(CHARACTER_CLASSES) - classes_of(version),
                                 set(CLASSES_NOT_IN_VERSION[version]))


class RetroBetaReadsTheRetroTablesTests(SimpleTestCase):

    def test_its_rules_follow_the_retro_main_game(self):
        self.assertEqual(MAIN, main_game(KEY))
        self.assertEqual(GAME_VERSIONS[MAIN].family, GAME_VERSIONS[KEY].family)

    def test_every_keyed_table_gives_it_the_retro_entry(self):
        for module_name, attribute in KEYED_TABLES:
            if attribute in OWN_RULES:
                continue
            found = table(module_name, attribute)
            with self.subTest(table='%s.%s' % (module_name, attribute)):
                if isinstance(found, dict):
                    self.assertIs(found[MAIN], found[KEY])
                else:
                    self.assertEqual(MAIN in found, KEY in found)

    def test_it_has_no_build_site_of_its_own(self):
        for module_name, hosts, without in SPLIT_TABLES:
            with self.subTest(table=hosts):
                self.assertNotIn(KEY, table(module_name, hosts))
                self.assertIn(KEY, table(module_name, without))


class RetroBetaForbidsThreeMoreRowsByDefaultTests(SimpleTestCase):

    def rows(self):
        connection = sqlite3.connect(get_items_db_path(KEY))
        self.addCleanup(connection.close)
        return connection

    def test_its_list_is_the_retro_list_and_three_rows_no_list_covers(self):
        self.assertEqual(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION[MAIN],
                         DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION[KEY][:len(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION[MAIN])])
        extra = beta_only_exclusions()
        self.assertEqual(3, len(extra))
        for ankama_id in extra:
            with self.subTest(ankama_id=ankama_id):
                self.assertNotIn(ankama_id, DEFAULT_EXCLUSION_ANKAMA_IDS)
                self.assertNotIn(ankama_id, DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION[MAIN])

    def test_the_gm_row_is_named_gm(self):
        names = [row[0] for row in self.rows().execute(
            'SELECT name FROM items WHERE ankama_id IN (%s)' % ','.join('?' * 3), beta_only_exclusions())]
        self.assertEqual(1, sum(1 for name in names if 'GM' in name.split()))

    def test_the_tester_mount_has_ten_times_the_prospecting_of_any_other(self):
        rows = self.rows().execute(
            "SELECT i.ankama_id, s.value FROM stats_of_item s JOIN items i ON i.id = s.item "
            "JOIN stats t ON t.id = s.stat JOIN item_types y ON y.id = i.type "
            "WHERE t.name = 'Prospecting' AND y.name = 'Pet'").fetchall()
        extra = set(beta_only_exclusions())
        tester = [value for ankama_id, value in rows if ankama_id in extra]
        others = [value for ankama_id, value in rows if ankama_id not in extra]
        self.assertEqual(1, len(tester))
        self.assertGreaterEqual(tester[0], 10 * max(others))

    def test_the_wip_row_is_new_and_has_no_icon(self):
        structure = get_structure(KEY)
        drawn = [ankama_id for ankama_id in beta_only_exclusions()
                 if get_image_url(structure.get_item_by_ankama_id(ankama_id).type,
                                  structure.get_item_by_ankama_id(ankama_id).name, KEY) == RETRO_PLACEHOLDER]
        unseen = [ankama_id for ankama_id in drawn if get_structure(MAIN).get_item_by_ankama_id(ankama_id) is None]
        self.assertEqual(1, len(unseen))

    def test_the_three_rows_stay_in_the_catalogue_and_are_forbidden_by_default(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(KEY)
        structure = get_structure(KEY)
        available = {item.ankama_id for item in structure.get_available_items_list()}
        removed = dict(self.rows().execute('SELECT ankama_id, removed FROM items').fetchall())
        default = set(get_default_exclusions(None))
        for ankama_id in beta_only_exclusions():
            with self.subTest(ankama_id=ankama_id):
                self.assertIn(ankama_id, available)
                self.assertFalse(removed[ankama_id])
                self.assertIn(structure.get_item_by_ankama_id(ankama_id).id, default)


class RetroBetaStoresNoMovementSentinelTests(SimpleTestCase):

    def grade_rows(self, key):
        connection = sqlite3.connect(get_items_db_path(key))
        self.addCleanup(connection.close)
        return connection.execute('SELECT * FROM monster_grades ORDER BY monster_ankama_id, grade').fetchall()

    def test_a_creature_that_never_moves_is_stored_as_no_value(self):
        rows = self.grade_rows(KEY)
        self.assertTrue(rows)
        self.assertEqual([], [row for row in rows if any(row[index] is not None and row[index] < 0 for index in (4, 5))])

    def test_the_grades_the_beta_lang_does_not_change_are_those_of_main(self):
        main = {row[:2]: row for row in self.grade_rows('retro')}
        beta = {row[:2]: row for row in self.grade_rows(KEY)}
        self.assertTrue(set(beta) <= set(main))
        self.assertEqual([], [key for key in beta if beta[key][4:6] != main[key][4:6]])


class RetroBetaBuildsARetroSetTests(TestCase):

    def test_a_retro_class_gets_a_set(self):
        from chardata.coaching_view import create_build
        from chardata.fashion_action import fashion
        from chardata.solution import get_solution
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(KEY)
        for char_class in ('Iop', 'Cra'):
            with self.subTest(char_class=char_class):
                request = RequestFactory().get('/')
                request.user = User.objects.create_user('retrobeta-' + char_class)
                request.game_version = KEY
                request.LANGUAGE_CODE = 'en'
                request.session = {}
                char = create_build(request, char_class, 50, {'str'}, KEY)
                fashion(request, char.id)
                char.refresh_from_db()
                self.assertEqual(KEY, char.game_version)
                solution = get_solution(char)
                self.assertIsNotNone(solution)
                equipped = [item for item in solution.item_list if item.item_added]
                self.assertGreaterEqual(len(equipped), 3)
                self.assertTrue(all(item.level <= 50 for item in equipped))


class RetroBetaIsHiddenFromReadersTests(TestCase):

    def test_no_reader_list_or_switcher_names_it(self):
        self.assertNotIn(KEY, version_keys())
        self.assertNotIn(KEY, reader_dofus_versions())
        self.assertNotIn(KEY, prefixed_reader_versions())
        for main, members in switcher_games():
            with self.subTest(game=main):
                self.assertNotIn(KEY, [main] + list(members))

    def test_it_has_no_route(self):
        for pattern in urls._prefixed_version_routes():
            with self.subTest(route=str(pattern.pattern)):
                self.assertNotEqual(GAME_VERSIONS[KEY].prefix + '/', str(pattern.pattern))
                self.assertNotEqual(KEY, pattern.namespace)

    def test_the_home_page_names_it_in_no_link_or_alternate(self):
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)
        page = response.content.decode('utf-8')
        self.assertIn('rel="alternate"', page)
        self.assertIn('/%s/' % MAIN, page)
        self.assertNotIn(KEY, page)

    def test_the_sitemap_names_it_nowhere(self):
        saved = dict(urls._SITEMAP_CACHES)
        saved_items = dict(urls._SITEMAP_ITEM_CACHE)
        urls._SITEMAP_CACHES.clear()
        self.addCleanup(urls._SITEMAP_CACHES.update, saved)
        self.addCleanup(urls._SITEMAP_CACHES.clear)
        self.addCleanup(urls._SITEMAP_ITEM_CACHE.update, saved_items)
        built = {name: dict(urls.SITEMAP_SECTIONS)[name](urls.SITEMAP_BASE) for name in SITEMAP_SECTIONS}
        for name, body in built.items():
            with self.subTest(section=name):
                self.assertIn('/%s/' % MAIN, body)
                self.assertNotIn(KEY, body)
