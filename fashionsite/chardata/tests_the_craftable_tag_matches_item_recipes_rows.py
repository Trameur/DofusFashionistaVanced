# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Craftable tag appears on exactly the ingredients with their own
item_recipes rows, matched through items.ankama_id."""

import sqlite3

from django.test import SimpleTestCase

from chardata.item_sources import get_source_ankama_ids
from chardata.recipe_util import workshop_breakdown
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')


def _craftable_ankama_ids_from_the_db(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        rows = conn.execute(
            'SELECT DISTINCT i.ankama_id FROM item_recipes r '
            'JOIN items i ON i.id = r.item').fetchall()
    finally:
        conn.close()
    return {row[0] for row in rows}


class TheCraftableSetMatchesItemRecipesTests(SimpleTestCase):

    def test_the_craftable_set_matches_the_db_count_per_version(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                expected = _craftable_ankama_ids_from_the_db(game_version)
                actual = get_source_ankama_ids(game_version)['craftable']
                print('craftable ankama ids in %s: %d' % (game_version, len(expected)))
                self.assertEqual(expected, actual)


def _a_chained_craftable_ingredient(game_version):
    """(parent_item_id, per_unit_quantity, intermediate_ankama_id) or None.

    The intermediate is an equipment ingredient that carries its own recipe,
    used by some other item's recipe.
    """
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        has_own_recipe = {row[0] for row in conn.execute(
            "SELECT DISTINCT i.ankama_id FROM items i "
            "JOIN item_recipes r ON r.item = i.id WHERE i.ankama_type = 'equipment'")}
        used_as_ingredient = {row[0] for row in conn.execute(
            "SELECT DISTINCT ingredient_ankama_id FROM item_recipes "
            "WHERE ingredient_subtype = 'equipment'")}
        chained = sorted(has_own_recipe & used_as_ingredient)
        if not chained:
            return None
        intermediate = chained[0]
        parent_item, quantity = conn.execute(
            "SELECT item, quantity FROM item_recipes "
            "WHERE ingredient_ankama_id = ? AND ingredient_subtype = 'equipment' LIMIT 1",
            (intermediate,)).fetchone()
    finally:
        conn.close()
    return parent_item, quantity, intermediate


class TheCardRowCarriesTheCraftableFlagTests(SimpleTestCase):

    def test_the_intermediate_ingredient_row_is_flagged_craftable(self):
        chain = _a_chained_craftable_ingredient('dofus3')
        self.assertIsNotNone(chain, 'no equipment-in-equipment chain to test against')
        parent_item, _quantity, intermediate = chain

        breakdown = workshop_breakdown([(parent_item, 1)], 'en', 'dofus3')
        rows = breakdown['items'][parent_item]
        row = next(r for r in rows if r['ankama_id'] == intermediate)

        self.assertTrue(row['craftable'])
        self.assertIsNotNone(row['craftable_item_id'])

    def test_a_resource_only_ingredient_is_not_flagged_craftable(self):
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            row = conn.execute(
                "SELECT item, ingredient_ankama_id, quantity FROM item_recipes "
                "WHERE ingredient_subtype = 'resources' LIMIT 1").fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row, 'no resource ingredient to test against')
        parent_item, resource_ankama_id, _quantity = row

        breakdown = workshop_breakdown([(parent_item, 1)], 'en', 'dofus3')
        rows = breakdown['items'][parent_item]
        matching = next(r for r in rows if r['ankama_id'] == resource_ankama_id
                        and r['subtype'] == 'resources')

        self.assertFalse(matching['craftable'])
        self.assertIsNone(matching['craftable_item_id'])
