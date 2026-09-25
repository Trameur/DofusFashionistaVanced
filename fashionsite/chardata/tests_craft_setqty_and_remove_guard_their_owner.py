# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""craft, uncraft, setqty and remove never touch another user's WorkshopItem."""

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem, WorkshopStock, WorkshopUndo


class TheWorkshopItemActionsGuardTheirOwnerTests(TestCase):

    def setUp(self):
        self.owner = User.objects.create_user(
            'card-owner', 'card-owner@test.local', 'pw-4242xy')
        self.attacker = User.objects.create_user(
            'card-attacker', 'card-attacker@test.local', 'pw-4242xy')
        self.wi = WorkshopItem.objects.create(
            user=self.owner, item_id=1, game_version='dofus3', quantity=3)
        self.client.force_login(self.attacker)

    def test_craft_on_another_users_card_is_404(self):
        resp = self.client.post('/workshop/craft/%d/' % self.wi.id)
        self.assertEqual(404, resp.status_code)
        self.wi.refresh_from_db()
        self.assertEqual(3, self.wi.quantity)

    def test_uncraft_on_another_users_card_is_404(self):
        # Even a card the owner just crafted stays out of reach: the undo
        # token is scoped by the caller's own user id.
        WorkshopStock.objects.create(
            user=self.owner, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=999)
        token = WorkshopUndo.objects.create(
            user=self.owner, game_version='dofus3',
            workshop_item_id=self.wi.id, item_id=self.wi.item_id,
            stock_deltas=[{'ankama_id': 1, 'subtype': 'resources', 'per_unit': 1}])
        resp = self.client.post('/workshop/uncraft/%d/' % self.wi.id)
        self.assertEqual(404, resp.status_code)
        self.assertTrue(WorkshopUndo.objects.filter(pk=token.pk).exists())
        self.assertEqual(999, WorkshopStock.objects.get(user=self.owner).owned)

    def test_setqty_on_another_users_card_is_404(self):
        resp = self.client.post(
            '/workshop/setqty/%d/' % self.wi.id, {'quantity': 5})
        self.assertEqual(404, resp.status_code)
        self.wi.refresh_from_db()
        self.assertEqual(3, self.wi.quantity)

    def test_remove_on_another_users_card_is_404(self):
        resp = self.client.post('/workshop/remove/%d/' % self.wi.id)
        self.assertEqual(404, resp.status_code)
        self.assertTrue(WorkshopItem.objects.filter(id=self.wi.id).exists())

    def test_remove_on_a_missing_id_is_404(self):
        resp = self.client.post('/workshop/remove/99999999/')
        self.assertEqual(404, resp.status_code)

    def test_the_owner_can_still_remove_their_own_card(self):
        self.client.force_login(self.owner)
        resp = self.client.post('/workshop/remove/%d/' % self.wi.id)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['removed'])
        self.assertFalse(WorkshopItem.objects.filter(id=self.wi.id).exists())
