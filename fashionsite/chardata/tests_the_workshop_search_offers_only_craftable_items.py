# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop's add search offers only items that have a recipe."""

import io
import os
import sqlite3

from django.test import TestCase

from fashionistapulp.fashionista_config import get_items_db_path

_JS = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   'static', 'chardata', 'workshop.js')


def _craftable_ids(game_version='dofus3'):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        return {row[0] for row in conn.execute('SELECT DISTINCT item FROM item_recipes')}
    finally:
        conn.close()


class TheWorkshopSearchOffersOnlyCraftableItemsTests(TestCase):

    PET = 'Air Bwak'
    RING = 'Rhineetle Ring'

    def _ids(self, **params):
        resp = self.client.get('/forgemagie/items/', params)
        self.assertEqual(resp.status_code, 200)
        return [entry['id'] for entry in resp.json()['items']]

    def test_an_item_without_a_recipe_is_left_out(self):
        craftable = _craftable_ids()
        uncraftable = [item_id for item_id in self._ids(q=self.PET, all_types='1')
                       if item_id not in craftable]
        self.assertTrue(uncraftable, 'the pet search found no item without a recipe')
        filtered = self._ids(q=self.PET, all_types='1', with_recipe='1')
        self.assertFalse(set(uncraftable) & set(filtered))

    def test_a_craftable_item_is_still_offered(self):
        craftable = _craftable_ids()
        found = self._ids(q=self.RING, all_types='1', with_recipe='1')
        self.assertTrue(found, 'the ring search found nothing with a recipe')
        self.assertTrue(set(found) <= craftable)

    def test_without_the_flag_the_search_is_unchanged(self):
        self.assertEqual(self._ids(q=self.PET, all_types='1'),
                         self._ids(q=self.PET, all_types='1', with_recipe='0'))

    def test_the_workshop_page_asks_for_craftable_items_only(self):
        with io.open(_JS, encoding='utf-8') as source:
            self.assertIn('with_recipe=1', source.read())
