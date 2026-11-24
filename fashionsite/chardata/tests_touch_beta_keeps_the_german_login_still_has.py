# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The early Touch channel does not serve German, so its German is login's wherever the English did not move, and every table login has is on the beta too."""
import os
import sqlite3
from unittest import mock

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module

PULP = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
                    'fashionistapulp', 'fashionistapulp')
LOGIN_DB = os.path.join(PULP, 'items_touch.db')
EARLY_DB = os.path.join(PULP, 'items_touchbeta.db')


class TheSeedMixesLoginGermanWithEarlyEnglishTests(SimpleTestCase):

    def setUp(self):
        self.seed = itemscraper_module('seed_unserved_language')

    def test_an_unchanged_english_name_takes_the_login_german_and_a_changed_one_stays_english(self):
        early_en = {'1': {'id': 1, 'nameId': 'Sword', 'descriptionId': 'Sharp'},
                    '2': {'id': 2, 'nameId': 'Renamed', 'descriptionId': 'Old'},
                    '3': {'id': 3, 'nameId': 'Brand new', 'descriptionId': 'New'}}
        login_en = {'1': {'nameId': 'Sword', 'descriptionId': 'Sharp'},
                    '2': {'nameId': 'Before', 'descriptionId': 'Old'}}
        login_de = {'1': {'nameId': 'Schwert', 'descriptionId': 'Scharf'},
                    '2': {'nameId': 'Davor', 'descriptionId': 'Alt'}}
        seeded = self.seed.seed_table(early_en, login_en, login_de, ('nameId', 'descriptionId'), ('id',))
        self.assertEqual({'id': 1, 'nameId': 'Schwert', 'descriptionId': 'Scharf'}, seeded['1'])
        self.assertEqual({'id': 2, 'nameId': 'Renamed', 'descriptionId': 'Alt'}, seeded['2'])
        self.assertEqual({'id': 3, 'nameId': 'Brand new', 'descriptionId': 'New'}, seeded['3'])

    def test_a_language_the_channel_serves_is_left_alone(self):
        with mock.patch.object(self.seed.touch_channels, 'served_languages',
                               return_value={'en', 'es', 'fr', 'pt', 'de'}):
            self.assertEqual({}, self.seed.seed('early'))

    def test_an_unreadable_config_seeds_nothing(self):
        with mock.patch.object(self.seed.touch_channels, 'served_languages', return_value=set()):
            self.assertEqual({}, self.seed.seed('early'))


class TheStagedDatabaseSpeaksLoginGermanTests(SimpleTestCase):

    def setUp(self):
        if not (os.path.isfile(LOGIN_DB) and os.path.isfile(EARLY_DB)):
            self.skipTest('the Touch databases are not in this checkout')
        self.login = sqlite3.connect(LOGIN_DB)
        self.early = sqlite3.connect(EARLY_DB)
        self.addCleanup(self.login.close)
        self.addCleanup(self.early.close)

    def _german_items(self, connection):
        return dict(connection.execute(
            "SELECT i.ankama_id, n.name FROM item_names n JOIN items i ON i.id = n.item "
            "WHERE n.language = 'de' AND i.ankama_type = 'equipment' AND i.id < 200000000"))

    def _german_sets(self, connection):
        return dict(connection.execute(
            "SELECT s.ankama_id, n.name FROM set_names n JOIN sets s ON s.id = n.item_set "
            "WHERE n.language = 'de'"))

    def test_a_piece_both_channels_carry_reads_the_same_in_german(self):
        login, early = self._german_items(self.login), self._german_items(self.early)
        shared = set(login) & set(early)
        self.assertGreater(len(shared), 3000)
        english = dict(self.early.execute("SELECT ankama_id, name FROM items WHERE ankama_type = 'equipment'"))
        renamed = [key for key in shared if login[key] != early[key]]
        self.assertTrue(all(early[key] == english[key] for key in renamed), renamed[:10])
        self.assertLess(len(renamed), 40)

    def test_a_set_both_channels_carry_reads_the_same_in_german(self):
        login, early = self._german_sets(self.login), self._german_sets(self.early)
        shared = set(login) & set(early)
        self.assertGreater(len(shared), 250)
        self.assertLess(sum(1 for key in shared if login[key] != early[key]), 15)

    def test_the_german_of_the_beta_is_not_all_english(self):
        early = self._german_items(self.early)
        english = dict(self.early.execute("SELECT ankama_id, name FROM items WHERE ankama_type = 'equipment'"))
        different = sum(1 for key, name in early.items() if name != english.get(key))
        self.assertGreater(different, 2500)


class TheStagedDatabaseHasEveryTableLoginHasTests(SimpleTestCase):

    def _tables(self, path):
        connection = sqlite3.connect(path)
        try:
            return {name for (name,) in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        finally:
            connection.close()

    def test_no_table_of_the_login_database_is_missing_from_the_beta(self):
        if not (os.path.isfile(LOGIN_DB) and os.path.isfile(EARLY_DB)):
            self.skipTest('the Touch databases are not in this checkout')
        self.assertEqual([], sorted(self._tables(LOGIN_DB) - self._tables(EARLY_DB)))

    def test_the_beta_carries_the_pet_variants_and_the_drops_of_login(self):
        if not (os.path.isfile(LOGIN_DB) and os.path.isfile(EARLY_DB)):
            self.skipTest('the Touch databases are not in this checkout')
        login, early = sqlite3.connect(LOGIN_DB), sqlite3.connect(EARLY_DB)
        self.addCleanup(login.close)
        self.addCleanup(early.close)
        for query in ("SELECT COUNT(*) FROM items WHERE id >= 200000000",
                      "SELECT COUNT(*) FROM legacy_item_ids",
                      "SELECT COUNT(*) FROM item_drops",
                      "SELECT COUNT(*) FROM resource_drops",
                      "SELECT COUNT(DISTINCT monster_ankama_id) FROM monster_names",
                      "SELECT COUNT(*) FROM item_recipes"):
            with self.subTest(query=query):
                before, after = login.execute(query).fetchone()[0], early.execute(query).fetchone()[0]
                self.assertGreater(after, 0)
                self.assertGreater(after, before * 0.95)
