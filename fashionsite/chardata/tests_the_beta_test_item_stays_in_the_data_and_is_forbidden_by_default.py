# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Ankama's beta test item stays in the game data and is only forbidden by default."""

import sqlite3

from django.test import TestCase

from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure, set_current_game_version

TEST_ITEM_ANKAMA_ID = 34569
TEST_ITEM_URL = '/beta/encyclopedia/item/equipment/34569-test-masquer-effet/'


class TheBetaTestItemStaysInTheDataTests(TestCase):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')

    def test_the_beta_database_keeps_it_unremoved(self):
        conn = sqlite3.connect(get_items_db_path('beta'))
        try:
            row = conn.execute('SELECT removed FROM items WHERE ankama_id = ?',
                               (TEST_ITEM_ANKAMA_ID,)).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertFalse(row[0])

    def test_its_encyclopedia_page_answers(self):
        self.assertEqual(200, self.client.get(TEST_ITEM_URL).status_code)

    def test_it_is_forbidden_by_default_on_the_beta(self):
        from chardata.lock_forbid import get_default_exclusions
        set_current_game_version('beta')
        structure = get_structure('beta')
        item = structure.get_item_by_ankama_id(TEST_ITEM_ANKAMA_ID)
        self.assertIsNotNone(item)
        self.assertIn(item.id, get_default_exclusions(char=None))

    def test_it_stays_in_the_pool_so_it_can_be_allowed_by_hand(self):
        set_current_game_version('beta')
        structure = get_structure('beta')
        item = structure.get_item_by_ankama_id(TEST_ITEM_ANKAMA_ID)
        self.assertIn(item.id, {it.id for it in structure.get_available_items_list()})

    def test_the_corrections_file_hides_no_item(self):
        import io
        import json
        import os
        from django.conf import settings
        path = os.path.join(os.path.dirname(settings.BASE_DIR), 'itemscraper',
                            'item_corrections.json')
        with io.open(path, encoding='utf-8') as handle:
            corrections = json.load(handle)
        for version, fixes in corrections.items():
            if version.startswith('_'):
                continue
            for ankama_id, fix in fixes.items():
                self.assertNotIn('removed', fix, (version, ankama_id))
