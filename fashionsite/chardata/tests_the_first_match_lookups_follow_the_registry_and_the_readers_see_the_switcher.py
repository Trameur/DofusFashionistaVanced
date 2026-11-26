# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Where a first-match lookup walks the versions in registry order and what a reader sees of the game keys in switcher order, with the accepted set of keys unchanged."""
from unittest import mock

from django.test import SimpleTestCase, TestCase

from chardata import encyclopedia_view, fashionista_build
from fashionistapulp.game_versions import switcher_order, version_keys

CURRENT = 'dofus3'


def _the_others():
    return [key for key in version_keys() if key != CURRENT]


class TheRegistryOrderIsNotTheSwitcherOrderTests(SimpleTestCase):

    def test_the_two_orders_differ_so_the_lookups_below_can_tell_them_apart(self):
        self.assertNotEqual(version_keys(), switcher_order())
        self.assertEqual(sorted(version_keys()), sorted(switcher_order()))


class AMissingNameIsAskedOfTheVersionsInRegistryOrderTests(SimpleTestCase):

    def test_an_item_is_asked_of_the_versions_in_registry_order(self):
        asked = []

        def structure(key):
            asked.append(key)
            return mock.Mock(get_concatenated_items_lists=lambda: [])

        with mock.patch.object(encyclopedia_view, 'get_structure', structure):
            encyclopedia_view._resolve_missing_item_name('Equipment', 1, 'slug', 'en', CURRENT)
        self.assertEqual(asked, _the_others())

    def test_a_monster_is_asked_of_the_versions_in_registry_order(self):
        asked = []

        def path(key):
            asked.append(key)
            return ':memory:'

        with mock.patch.object(encyclopedia_view, 'get_items_db_path', path):
            encyclopedia_view._resolve_missing_monster_name(1, 'slug', 'en', CURRENT)
        self.assertEqual(asked, _the_others())

    def test_a_resource_is_asked_of_the_versions_in_registry_order(self):
        asked = []

        def path(key):
            asked.append(key)
            return ':memory:'

        with mock.patch.object(encyclopedia_view, 'get_items_db_path', path):
            encyclopedia_view._resolve_missing_resource_name('resource', 1, 'slug', 'en', CURRENT)
        self.assertEqual(asked, _the_others())


class TheSendABuildPageListsTheGamesInSwitcherOrderTests(TestCase):

    def test_the_page_hands_its_template_the_games_in_switcher_order(self):
        response = self.client.get('/developers/send-a-build/')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['games'], switcher_order())

    def test_the_unknown_game_message_names_the_games_in_switcher_order(self):
        text = fashionista_build.message('unknown_game')
        positions = [text.index(key) for key in switcher_order()]
        self.assertEqual(positions, sorted(positions))

    def test_the_schema_enum_keeps_the_registry_keys(self):
        self.assertEqual(fashionista_build.json_schema()['properties']['game']['enum'], version_keys())

    def test_every_registry_key_is_accepted_and_an_unknown_one_is_not(self):
        for key in version_keys():
            with self.subTest(key=key):
                codes = [e['code'] for e in fashionista_build.check(
                    {'format': fashionista_build.FORMAT, 'version': 1, 'game': key}).errors]
                self.assertNotIn('unknown_game', codes)
        codes = [e['code'] for e in fashionista_build.check(
            {'format': fashionista_build.FORMAT, 'version': 1, 'game': 'dofus99'}).errors]
        self.assertIn('unknown_game', codes)
