# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""POST workshop/stock/reset/ clears the caller's stock for one version."""

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem, WorkshopStock


class WorkshopStockResetTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'reseter', 'reseter@test.local', 'pw-4242xy')
        self.other = User.objects.create_user(
            'reset-bystander', 'reset-bystander@test.local', 'pw-4242xy')
        self.client.force_login(self.user)

    def test_reset_clears_only_this_versions_stock(self):
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=10)
        WorkshopStock.objects.create(
            user=self.user, game_version='touch', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=20)

        resp = self.client.post('/workshop/stock/reset/')
        self.assertEqual(200, resp.status_code)
        self.assertEqual(1, resp.json()['removed_count'])

        self.assertFalse(WorkshopStock.objects.filter(
            user=self.user, game_version='dofus3').exists())
        self.assertTrue(WorkshopStock.objects.filter(
            user=self.user, game_version='touch').exists())

    def test_reset_never_touches_the_item_cards(self):
        wi = WorkshopItem.objects.create(
            user=self.user, item_id=1, game_version='dofus3', quantity=5)
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=10)

        self.client.post('/workshop/stock/reset/')

        wi.refresh_from_db()
        self.assertEqual(5, wi.quantity)

    def test_reset_never_touches_another_users_stock(self):
        WorkshopStock.objects.create(
            user=self.other, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=10)
        self.client.post('/workshop/stock/reset/')
        self.assertTrue(WorkshopStock.objects.filter(user=self.other).exists())

    def test_anonymous_cannot_reset(self):
        self.client.logout()
        resp = self.client.post('/workshop/stock/reset/')
        self.assertEqual(302, resp.status_code)
