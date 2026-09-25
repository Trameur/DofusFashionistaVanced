# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""has_recipe and the workshop add URLs reach the item and set page context."""

import sqlite3

from django.test import TestCase

from chardata.official_site import get_item_link, get_set_link
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

VERSIONS = ('dofus3', 'touch')


def _prefix(game_version):
    return '' if game_version == 'dofus3' else '/%s' % game_version


def _items_with_and_without_a_recipe(game_version):
    structure = get_structure(game_version)
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        recipe_ids = {row[0] for row in
                      conn.execute('SELECT DISTINCT item FROM item_recipes')}
    finally:
        conn.close()

    with_recipe = without_recipe = None
    for item in structure.get_concatenated_items_lists():
        if getattr(item, 'removed', False) or not item.ankama_id:
            continue
        if item.id in recipe_ids and with_recipe is None:
            with_recipe = item
        if item.id not in recipe_ids and without_recipe is None:
            without_recipe = item
        if with_recipe is not None and without_recipe is not None:
            break
    return with_recipe, without_recipe


class ItemPageWorkshopContextTests(TestCase):

    def test_an_item_with_a_recipe_carries_the_add_url(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                with_recipe, _without = _items_with_and_without_a_recipe(game_version)
                self.assertIsNotNone(with_recipe)
                url = get_item_link(with_recipe.ankama_type, with_recipe.ankama_id,
                                    with_recipe.name, game_version)
                resp = self.client.get(url)
                self.assertEqual(200, resp.status_code)
                self.assertTrue(resp.context['has_recipe'])
                self.assertEqual(
                    '%s/workshop/add/' % _prefix(game_version),
                    resp.context['workshop_add_url'])

    def test_an_item_without_a_recipe_says_so(self):
        _with, without_recipe = _items_with_and_without_a_recipe('dofus3')
        self.assertIsNotNone(without_recipe)
        url = get_item_link(without_recipe.ankama_type, without_recipe.ankama_id,
                            without_recipe.name, 'dofus3')
        resp = self.client.get(url)
        self.assertEqual(200, resp.status_code)
        self.assertFalse(resp.context['has_recipe'])


class SetPageWorkshopContextTests(TestCase):

    def test_the_set_page_carries_the_addset_url(self):
        structure = get_structure('dofus3')
        set_id, item_set = next(iter(structure.sets_dict.items()))
        set_name = (item_set.localized_names.get('en') or item_set.name)
        url = get_set_link(set_id, set_name, 'dofus3')
        resp = self.client.get(url, follow=True)
        self.assertEqual(200, resp.status_code)
        self.assertEqual('/workshop/addset/%d/' % set_id,
                         resp.context['workshop_add_set_url'])

    def test_set_cards_flag_which_items_are_craftable(self):
        structure = get_structure('dofus3')
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            recipe_ids = {row[0] for row in
                          conn.execute('SELECT DISTINCT item FROM item_recipes')}
        finally:
            conn.close()

        found = None
        for set_id, item_set in structure.sets_dict.items():
            ids = []
            seen = set()
            for raw_id in getattr(item_set, 'items', None) or []:
                item = structure.get_item_by_id(raw_id)
                if (item is None or not getattr(item, 'ankama_id', None)
                        or item.ankama_id in seen):
                    continue
                seen.add(item.ankama_id)
                ids.append(item.id)
            if any(i in recipe_ids for i in ids) and any(i not in recipe_ids for i in ids):
                found = (set_id, item_set, {i in recipe_ids for i in ids})
                break
        self.assertIsNotNone(found, 'no mixed set to test against')
        set_id, item_set, _ = found
        set_name = (item_set.localized_names.get('en') or item_set.name)
        url = get_set_link(set_id, set_name, 'dofus3')

        resp = self.client.get(url, follow=True)
        cards = resp.context['set_items']
        self.assertTrue(any(card['has_recipe'] for card in cards))
        self.assertTrue(any(not card['has_recipe'] for card in cards))
