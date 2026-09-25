# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""POST workshop/uncraft/<id>/ undoes the last craft on a card, stock included."""

import sqlite3
from collections import defaultdict
from datetime import timedelta
from unittest import mock

from django.contrib.auth.models import User
from django.core.cache import caches
from django.test import TestCase

from chardata.models import WorkshopItem, WorkshopStock, WorkshopUndo
from chardata.workshop_view import UNDO_WINDOW_SECONDS
from fashionistapulp.fashionista_config import get_items_db_path


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


class UndoRestoresTheCraftExactlyTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'undoer-1', 'undoer-1@test.local', 'pw-4242xy')
        self.client.force_login(self.user)
        self.item_id = _an_item_with_a_recipe('dofus3')
        self.assertIsNotNone(self.item_id, 'no recipe to test against in dofus3')
        self.needs = _per_unit_needs('dofus3', self.item_id)
        self.assertTrue(self.needs)

    def _stock_ready_card(self, multiplier, extra_per_row=0):
        wi = WorkshopItem.objects.create(
            user=self.user, item_id=self.item_id, game_version='dofus3',
            quantity=multiplier)
        for (ankama_id, subtype), per_unit in self.needs.items():
            WorkshopStock.objects.create(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype,
                owned=per_unit * multiplier + extra_per_row)
        return wi

    def test_undo_restores_the_multiplier_and_every_stock_row(self):
        wi = self._stock_ready_card(3, extra_per_row=5)
        before = {
            (r.ingredient_ankama_id, r.ingredient_subtype): r.owned
            for r in WorkshopStock.objects.filter(user=self.user, game_version='dofus3')
        }

        resp = self.client.post('/workshop/craft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['success'])

        after_wi = WorkshopItem.objects.get(user=self.user, item_id=self.item_id,
                                            game_version='dofus3')
        self.assertEqual(3, after_wi.quantity)
        after = {
            (r.ingredient_ankama_id, r.ingredient_subtype): r.owned
            for r in WorkshopStock.objects.filter(user=self.user, game_version='dofus3')
        }
        self.assertEqual(before, after)

    def test_undo_recreates_a_card_deleted_by_the_craft(self):
        wi = self._stock_ready_card(1)
        original_id = wi.id

        resp = self.client.post('/workshop/craft/%d/' % original_id)
        self.assertEqual(200, resp.status_code)
        self.assertFalse(WorkshopItem.objects.filter(id=original_id).exists())

        resp = self.client.post('/workshop/uncraft/%d/' % original_id)
        self.assertEqual(200, resp.status_code)

        restored = WorkshopItem.objects.get(
            user=self.user, item_id=self.item_id, game_version='dofus3')
        self.assertEqual(1, restored.quantity)
        for (ankama_id, subtype), per_unit in self.needs.items():
            row = WorkshopStock.objects.get(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
            self.assertEqual(per_unit, row.owned)

    def test_undo_never_leaves_a_zero_owned_stock_row(self):
        wi = self._stock_ready_card(1)
        self.client.post('/workshop/craft/%d/' % wi.id)
        self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertFalse(WorkshopStock.objects.filter(
            user=self.user, game_version='dofus3', owned=0).exists())

    def test_uncraft_without_a_prior_craft_is_refused(self):
        wi = self._stock_ready_card(1)
        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(404, resp.status_code)

    def test_undo_does_not_depend_on_the_per_process_default_cache(self):
        # Gunicorn runs several worker processes, each with its own default
        # cache; the undo record must not live there or an undo served by a
        # different worker than the craft would always 404.
        wi = self._stock_ready_card(1)
        self.client.post('/workshop/craft/%d/' % wi.id)
        caches['default'].clear()
        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)

    def test_undo_is_consumed_and_cannot_be_replayed(self):
        wi = self._stock_ready_card(2)
        self.client.post('/workshop/craft/%d/' % wi.id)
        first = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(200, first.status_code)
        second = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(404, second.status_code)

    def test_undo_adds_back_its_own_delta_without_erasing_another_cards_use(self):
        # WorkshopStock is shared across every card that needs a resource.
        # Undo must not overwrite what another card did to it meanwhile.
        wi = self._stock_ready_card(2, extra_per_row=20)
        self.client.post('/workshop/craft/%d/' % wi.id)

        any_key = next(iter(self.needs))
        ankama_id, subtype = any_key
        row = WorkshopStock.objects.get(
            user=self.user, game_version='dofus3',
            ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
        owned_after_craft = row.owned
        row.owned = max(0, row.owned - 7)
        row.save(update_fields=['owned'])

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)

        row.refresh_from_db()
        per_unit = self.needs[any_key]
        self.assertEqual(owned_after_craft - 7 + per_unit, row.owned)

    def test_undo_increments_a_card_re_added_since_the_craft(self):
        wi = self._stock_ready_card(1)
        self.client.post('/workshop/craft/%d/' % wi.id)
        self.assertFalse(WorkshopItem.objects.filter(id=wi.id).exists())

        readded = WorkshopItem.objects.create(
            user=self.user, item_id=self.item_id, game_version='dofus3', quantity=5)

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)

        readded.refresh_from_db()
        self.assertEqual(6, readded.quantity)
        self.assertEqual(readded.id, resp.json()['workshop_item_id'])

    def test_undo_after_a_stock_reset_gives_back_only_its_own_delta(self):
        wi = self._stock_ready_card(1, extra_per_row=5)
        self.client.post('/workshop/craft/%d/' % wi.id)

        WorkshopStock.objects.filter(user=self.user, game_version='dofus3').delete()

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)

        for (ankama_id, subtype), per_unit in self.needs.items():
            row = WorkshopStock.objects.get(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
            self.assertEqual(per_unit, row.owned)

    def test_a_stale_token_is_refused_and_removed(self):
        wi = self._stock_ready_card(2)
        self.client.post('/workshop/craft/%d/' % wi.id)
        token = WorkshopUndo.objects.get(user=self.user, workshop_item_id=wi.id)
        WorkshopUndo.objects.filter(pk=token.pk).update(
            created_time=token.created_time - timedelta(seconds=UNDO_WINDOW_SECONDS + 1))

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(404, resp.status_code)
        self.assertFalse(WorkshopUndo.objects.filter(pk=token.pk).exists())
        wi.refresh_from_db()
        self.assertEqual(1, wi.quantity)

    def test_two_racing_uncrafts_apply_the_restore_only_once(self):
        # Reproduces the race a review found: two uncraft requests for the
        # same card both find the undo token before either deletes it.
        wi = self._stock_ready_card(2, extra_per_row=5)
        self.client.post('/workshop/craft/%d/' % wi.id)

        stock_before = {
            (r.ingredient_ankama_id, r.ingredient_subtype): r.owned
            for r in WorkshopStock.objects.filter(user=self.user, game_version='dofus3')
        }
        quantity_before = WorkshopItem.objects.get(
            user=self.user, item_id=self.item_id, game_version='dofus3').quantity

        original_delete = WorkshopUndo.delete
        already_raced = []

        def racing_delete(token, *args, **kwargs):
            if not already_raced:
                already_raced.append(True)
                second = self.client.post('/workshop/uncraft/%d/' % wi.id)
                self.assertEqual(200, second.status_code)
            return original_delete(token, *args, **kwargs)

        with mock.patch.object(WorkshopUndo, 'delete', racing_delete):
            first = self.client.post('/workshop/uncraft/%d/' % wi.id)

        self.assertEqual(404, first.status_code)

        after_wi = WorkshopItem.objects.get(
            user=self.user, item_id=self.item_id, game_version='dofus3')
        self.assertEqual(quantity_before + 1, after_wi.quantity)
        for key, owned_before in stock_before.items():
            ankama_id, subtype = key
            row = WorkshopStock.objects.get(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
            self.assertEqual(owned_before + self.needs[key], row.owned)

    def test_uncraft_after_remove_is_refused_and_does_not_resurrect_the_card(self):
        wi = self._stock_ready_card(5, extra_per_row=5)
        self.client.post('/workshop/craft/%d/' % wi.id)
        stock_after_craft = {
            (r.ingredient_ankama_id, r.ingredient_subtype): r.owned
            for r in WorkshopStock.objects.filter(user=self.user, game_version='dofus3')
        }

        resp = self.client.post('/workshop/remove/%d/' % wi.id)
        self.assertEqual(200, resp.status_code)
        self.assertFalse(WorkshopItem.objects.filter(id=wi.id).exists())
        self.assertFalse(WorkshopUndo.objects.filter(
            user=self.user, workshop_item_id=wi.id).exists())

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(404, resp.status_code)
        self.assertFalse(WorkshopItem.objects.filter(
            user=self.user, item_id=self.item_id, game_version='dofus3').exists())
        stock_after_uncraft = {
            (r.ingredient_ankama_id, r.ingredient_subtype): r.owned
            for r in WorkshopStock.objects.filter(user=self.user, game_version='dofus3')
        }
        self.assertEqual(stock_after_craft, stock_after_uncraft)

    def test_uncraft_after_clear_is_refused_and_does_not_resurrect_the_card(self):
        wi = self._stock_ready_card(5, extra_per_row=5)
        self.client.post('/workshop/craft/%d/' % wi.id)

        resp = self.client.post('/workshop/clear/')
        self.assertEqual(200, resp.status_code)
        self.assertFalse(WorkshopItem.objects.filter(
            user=self.user, game_version='dofus3').exists())
        self.assertFalse(WorkshopUndo.objects.filter(
            user=self.user, workshop_item_id=wi.id).exists())

        resp = self.client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(404, resp.status_code)
        self.assertFalse(WorkshopItem.objects.filter(
            user=self.user, game_version='dofus3').exists())

    def test_racing_craft_and_uncraft_on_the_same_card_leave_it_consistent(self):
        # Not a real MySQL deadlock reproduction (sqlite select_for_update is
        # a no-op); only checks that interleaving the two calls, forced the
        # same way test_two_racing_uncrafts_apply_the_restore_only_once does,
        # never crashes and leaves a self-consistent multiplier and stock.
        wi = self._stock_ready_card(3, extra_per_row=5)
        self.client.post('/workshop/craft/%d/' % wi.id)

        original_delete = WorkshopUndo.delete
        already_raced = []

        def racing_delete(token, *args, **kwargs):
            if not already_raced:
                already_raced.append(True)
                second = self.client.post('/workshop/craft/%d/' % wi.id)
                self.assertIn(second.status_code, (200, 400))
            return original_delete(token, *args, **kwargs)

        with mock.patch.object(WorkshopUndo, 'delete', racing_delete):
            first = self.client.post('/workshop/uncraft/%d/' % wi.id)

        self.assertIn(first.status_code, (200, 404))

        after_wi = WorkshopItem.objects.get(
            user=self.user, item_id=self.item_id, game_version='dofus3')
        self.assertGreaterEqual(after_wi.quantity, 1)
        for (ankama_id, subtype), per_unit in self.needs.items():
            row = WorkshopStock.objects.get(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype)
            self.assertGreaterEqual(row.owned, 0)

    def test_two_racing_uncrafts_on_different_users_never_cross_wires(self):
        other = User.objects.create_user(
            'undoer-2', 'undoer-2@test.local', 'pw-4242xy')
        wi = self._stock_ready_card(1)
        self.client.post('/workshop/craft/%d/' % wi.id)

        other_client = self.client_class()
        other_client.force_login(other)
        resp = other_client.post('/workshop/uncraft/%d/' % wi.id)
        self.assertEqual(404, resp.status_code)

        self.assertTrue(WorkshopUndo.objects.filter(
            user=self.user, workshop_item_id=wi.id).exists())
