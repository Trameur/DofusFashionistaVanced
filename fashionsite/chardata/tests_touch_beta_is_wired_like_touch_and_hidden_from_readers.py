# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Touch Beta carries its own data, reads every Touch table through the Touch rules, builds a Touch and a Bellaphone set, and no reader page, route or sitemap names it."""
import glob
import importlib
import json
import os

from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from chardata.spell_buffs import get_damage_spells_for_version, touch_spell_module
from chardata.targets import TARGET_VERSIONS
from chardata.tests_every_per_version_table_names_every_dofus_version import KEYED_TABLES, SPLIT_TABLES
from chardata.version_compat import CLASSES_NOT_IN_VERSION
from fashionistapulp import fashionista_config
from fashionistapulp.combat.rules import record_version
from fashionistapulp.dofus_constants import CHARACTER_CLASSES
from fashionistapulp.game_versions import (GAME_VERSIONS, main_game, prefixed_reader_versions,
                                           reader_dofus_versions, switcher_games, version_keys)
from fashionistapulp.structure import get_structure, set_current_game_version
from fashionsite import urls

KEY = 'touchbeta'
MAIN = 'touch'
HERE = os.path.dirname(os.path.abspath(__file__))
PULP = os.path.dirname(os.path.abspath(fashionista_config.__file__))
SITEMAP_SECTIONS = ('pages', 'items', 'sets', 'resources', 'monsters')
SHARED_WITH_THE_MAIN_GAME = ('combat_rules', 'combat_readings')


def per_key_tables():
    """Every folder of per-version JSON files that holds a Touch file."""
    return sorted(os.path.dirname(path) for pattern in (os.path.join(HERE, '*', MAIN + '.json'),
                                                         os.path.join(PULP, '*', MAIN + '.json'))
                  for path in glob.glob(pattern))


def classes_of(version):
    with open(os.path.join(HERE, 'spell_reference', version + '.json'), encoding='utf-8') as handle:
        return set(json.load(handle))


def table(module_name, attribute):
    return getattr(importlib.import_module(module_name), attribute)


class TouchBetaCarriesItsOwnDataTests(SimpleTestCase):

    def test_its_item_database_has_the_touch_catalogue(self):
        beta = {item.ankama_id for item in get_structure(KEY).get_available_items_list()}
        touch = {item.ankama_id for item in get_structure(MAIN).get_available_items_list()}
        self.assertGreater(len(beta), 0.95 * len(touch))

    def test_every_per_version_json_table_of_touch_has_a_touch_beta_file(self):
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

    def test_its_spells_are_its_own_module_and_keep_every_touch_damage_spell(self):
        beta = get_damage_spells_for_version(KEY)
        touch = get_damage_spells_for_version(MAIN)
        self.assertIs(touch_spell_module(KEY).TOUCH_DAMAGE_SPELLS, beta)
        self.assertIsNot(touch_spell_module(MAIN), touch_spell_module(KEY))
        self.assertEqual(set(), set(touch) - set(beta))
        self.assertEqual(set(), classes_of(MAIN) - classes_of(KEY))
        self.assertIn('Bellaphone', classes_of(KEY))

    def test_the_classes_it_lacks_are_the_ones_its_spell_data_lacks(self):
        for version in (MAIN, KEY):
            with self.subTest(version=version):
                self.assertEqual(set(CHARACTER_CLASSES) - classes_of(version),
                                 set(CLASSES_NOT_IN_VERSION[version]))


class TouchBetaReadsTheTouchTablesTests(SimpleTestCase):

    def test_its_rules_follow_the_touch_main_game(self):
        self.assertEqual(MAIN, main_game(KEY))
        self.assertEqual(GAME_VERSIONS[MAIN].family, GAME_VERSIONS[KEY].family)

    def test_every_keyed_table_gives_it_the_touch_entry(self):
        for module_name, attribute in KEYED_TABLES:
            if attribute == 'CLASSES_NOT_IN_VERSION':
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


class TouchBetaBuildsATouchSetTests(TestCase):

    def test_a_touch_class_and_the_bellaphone_get_a_set(self):
        from chardata.coaching_view import create_build
        from chardata.fashion_action import fashion
        from chardata.solution import get_solution
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(KEY)
        for char_class in ('Iop', 'Bellaphone'):
            with self.subTest(char_class=char_class):
                request = RequestFactory().get('/')
                request.user = User.objects.create_user('touchbeta-' + char_class)
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


class TouchBetaIsHiddenFromReadersTests(TestCase):

    def test_the_reader_lists_and_the_switcher_name_it_only_once_it_is_not_experimental(self):
        hidden = GAME_VERSIONS[KEY].experimental
        self.assertEqual(hidden, KEY not in version_keys())
        self.assertEqual(hidden, KEY not in reader_dofus_versions())
        self.assertEqual(hidden, KEY not in prefixed_reader_versions())
        named = {main: KEY in [main] + list(members) for main, members in switcher_games()}
        self.assertEqual(not hidden, named[MAIN])
        self.assertFalse(any(found for main, found in named.items() if main != MAIN))

    def test_it_has_a_route_only_once_it_is_not_experimental(self):
        hidden = GAME_VERSIONS[KEY].experimental
        routes = [str(pattern.pattern) for pattern in urls._prefixed_version_routes()]
        self.assertEqual(not hidden, GAME_VERSIONS[KEY].prefix + '/' in routes)
        if hidden:
            for pattern in urls._prefixed_version_routes():
                self.assertNotEqual(KEY, pattern.namespace)

    def test_the_home_page_names_it_in_a_link_or_alternate_only_once_it_is_not_experimental(self):
        response = self.client.get('/')
        self.assertEqual(200, response.status_code)
        page = response.content.decode('utf-8')
        self.assertIn('rel="alternate"', page)
        self.assertIn('/%s/' % MAIN, page)
        self.assertEqual(not GAME_VERSIONS[KEY].experimental, '/%s/' % KEY in page)
        if GAME_VERSIONS[KEY].experimental:
            self.assertNotIn(KEY, page)

    def test_the_sitemap_names_it_only_once_it_is_not_experimental(self):
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
                if GAME_VERSIONS[KEY].experimental:
                    self.assertNotIn(KEY, body)
        if not GAME_VERSIONS[KEY].experimental:
            self.assertIn('/%s/' % KEY, built['pages'])
