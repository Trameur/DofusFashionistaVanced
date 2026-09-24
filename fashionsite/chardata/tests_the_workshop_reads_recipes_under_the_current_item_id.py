# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A WorkshopItem stored under a retired id still shows its ingredients."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem
from chardata.recipe_util import workshop_breakdown
from chardata.workshop_view import _breakdown_for_user
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure


def _a_legacy_id_with_a_recipe(game_version):
    """(old_id, current_id) where the current id has recipe rows, or (None, None)."""
    structure = get_structure(game_version)
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        cursor = conn.cursor()
        for old_id, new_id in structure.legacy_item_ids.items():
            cursor.execute(
                'SELECT COUNT(*) FROM item_recipes WHERE item = ?', (new_id,))
            if cursor.fetchone()[0] > 0:
                return old_id, new_id
    finally:
        conn.close()
    return None, None


class TheBreakdownFollowsALegacyIdToItsCurrentRecipeTests(TestCase):

    def test_a_legacy_id_gets_the_same_rows_as_its_current_id(self):
        old_id, new_id = _a_legacy_id_with_a_recipe('dofus3')
        self.assertIsNotNone(
            old_id, 'no legacy id with a recipe in dofus3 to test against')

        direct = workshop_breakdown([(new_id, 1)], 'en', 'dofus3')
        legacy = workshop_breakdown([(old_id, 1)], 'en', 'dofus3')

        self.assertIn(new_id, direct['items'])
        self.assertIn(old_id, legacy['items'])
        self.assertTrue(direct['items'][new_id])
        self.assertEqual(
            [(row['ankama_id'], row['subtype'], row['quantity'])
             for row in direct['items'][new_id]],
            [(row['ankama_id'], row['subtype'], row['quantity'])
             for row in legacy['items'][old_id]])

    def test_a_saved_workshop_row_under_a_legacy_id_gets_its_ingredients(self):
        old_id, new_id = _a_legacy_id_with_a_recipe('dofus3')
        self.assertIsNotNone(
            old_id, 'no legacy id with a recipe in dofus3 to test against')

        user = User.objects.create_user(
            'legacy-crafter', 'legacy-crafter@test.local', 'pw-90210x')
        WorkshopItem.objects.create(
            user=user, item_id=old_id, game_version='dofus3', quantity=2)

        breakdown = _breakdown_for_user(user, 'dofus3')

        self.assertIn(old_id, breakdown['items'])
        self.assertTrue(breakdown['items'][old_id])
        self.assertEqual(1, breakdown['items_with_recipe'])
