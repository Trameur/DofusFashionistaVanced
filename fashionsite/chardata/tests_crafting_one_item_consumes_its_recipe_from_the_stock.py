# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""POST workshop/craft/<id>/ consumes the recipe from stock, one unit at a time."""

import sqlite3
from collections import defaultdict

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem, WorkshopStock
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

VERSIONS = ('dofus3', 'touch', 'retro')


def _prefix(game_version):
    return '' if game_version == 'dofus3' else '/%s' % game_version


def _an_item_with_a_recipe(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT DISTINCT item FROM item_recipes ORDER BY item LIMIT 1').fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _per_unit_needs(game_version, item_id):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        rows = conn.execute(
            'SELECT ingredient_ankama_id, ingredient_subtype, quantity '
            'FROM item_recipes WHERE item = ?', (item_id,)).fetchall()
    finally:
        conn.close()
    needs = defaultdict(int)
    for ankama_id, subtype, quantity in rows:
        needs[(ankama_id, subtype)] += quantity
    return dict(needs)


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


class CraftConsumesTheRecipeFromStockTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'crafter-42', 'crafter-42@test.local', 'pw-4242xy')
        self.client.force_login(self.user)

    def _stock_ready_card(self, game_version, multiplier):
        item_id = _an_item_with_a_recipe(game_version)
        self.assertIsNotNone(item_id, 'no recipe to test against in %s' % game_version)
        needs = _per_unit_needs(game_version, item_id)
        self.assertTrue(needs, 'the sampled item has no ingredient rows')

        wi = WorkshopItem.objects.create(
            user=self.user, item_id=item_id, game_version=game_version,
            quantity=multiplier)
        for (ankama_id, subtype), per_unit in needs.items():
            WorkshopStock.objects.create(
                user=self.user, game_version=game_version,
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype,
                owned=per_unit * multiplier)
        return wi, needs

    def test_craft_lowers_multiplier_and_subtracts_one_unit_per_resource(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                wi, needs = self._stock_ready_card(game_version, 3)

                resp = self.client.post(
                    '%s/workshop/craft/%d/' % (_prefix(game_version), wi.id))
                self.assertEqual(200, resp.status_code)
                body = resp.json()
                self.assertTrue(body['success'])
                self.assertFalse(body['removed'])
                self.assertEqual(2, body['quantity'])

                wi.refresh_from_db()
                self.assertEqual(2, wi.quantity)
                for (ankama_id, subtype), per_unit in needs.items():
                    row = WorkshopStock.objects.get(
                        user=self.user, game_version=game_version,
                        ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
                    self.assertEqual(per_unit * 2, row.owned)

    def test_craft_at_multiplier_one_removes_the_card_and_never_goes_below_zero(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                wi, needs = self._stock_ready_card(game_version, 1)

                resp = self.client.post(
                    '%s/workshop/craft/%d/' % (_prefix(game_version), wi.id))
                self.assertEqual(200, resp.status_code)
                body = resp.json()
                self.assertTrue(body['removed'])
                self.assertEqual(0, body['quantity'])

                self.assertFalse(WorkshopItem.objects.filter(id=wi.id).exists())
                for (ankama_id, subtype) in needs:
                    self.assertFalse(WorkshopStock.objects.filter(
                        user=self.user, game_version=game_version,
                        ingredient_ankama_id=ankama_id,
                        ingredient_subtype=subtype).exists())

    def test_craft_is_refused_when_one_row_is_short(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                wi, needs = self._stock_ready_card(game_version, 2)
                any_key = next(iter(needs))
                ankama_id, subtype = any_key
                row = WorkshopStock.objects.get(
                    user=self.user, game_version=game_version,
                    ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
                row.owned = max(0, row.owned - 1)
                row.save(update_fields=['owned'])

                resp = self.client.post(
                    '%s/workshop/craft/%d/' % (_prefix(game_version), wi.id))
                self.assertEqual(400, resp.status_code)

                wi.refresh_from_db()
                self.assertEqual(2, wi.quantity)

    def test_craft_on_a_legacy_id_uses_its_current_recipe(self):
        old_id, new_id = _a_legacy_id_with_a_recipe('dofus3')
        self.assertIsNotNone(old_id, 'no legacy id with a recipe in dofus3 to test against')
        needs = _per_unit_needs('dofus3', new_id)
        self.assertTrue(needs, 'the sampled current id has no ingredient rows')

        wi = WorkshopItem.objects.create(
            user=self.user, item_id=old_id, game_version='dofus3', quantity=1)
        for (ankama_id, subtype), per_unit in needs.items():
            WorkshopStock.objects.create(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype,
                owned=per_unit)

        resp = self.client.post('/workshop/craft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['success'])
        self.assertFalse(WorkshopItem.objects.filter(id=wi.id).exists())
        for (ankama_id, subtype) in needs:
            self.assertFalse(WorkshopStock.objects.filter(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype).exists())

    def test_an_item_with_no_recipe_refuses_to_craft(self):
        wi = WorkshopItem.objects.create(
            user=self.user, item_id=999999999, game_version='dofus3', quantity=1)
        resp = self.client.post('/workshop/craft/%d/' % wi.id)
        self.assertEqual(400, resp.status_code)

    def test_anonymous_cannot_craft(self):
        self.client.logout()
        wi_id = WorkshopItem.objects.create(
            user=self.user, item_id=1, game_version='dofus3', quantity=1).id
        resp = self.client.post('/workshop/craft/%d/' % wi_id)
        self.assertEqual(302, resp.status_code)
