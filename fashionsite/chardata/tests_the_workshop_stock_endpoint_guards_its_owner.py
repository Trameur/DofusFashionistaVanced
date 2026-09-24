# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""WorkshopStock: one owned count per resource, written only by its owner."""

import json

from django.contrib.auth.models import User
from django.db import IntegrityError, transaction
from django.test import TestCase

from chardata.models import WorkshopStock
from chardata.workshop_view import (
    MAX_STOCK_KEYS_PER_REQUEST, MAX_STOCK_OWNED, MAX_STOCK_ROWS_PER_VERSION)


def _post_stock(client, updates):
    return client.post('/workshop/stock/', data=json.dumps({'updates': updates}),
                       content_type='application/json')


class TheStockModelKeepsOneRowPerResourceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('stock-model', 'sm@test.local', 'pw-4242xy')

    def test_the_same_resource_cannot_be_stocked_twice(self):
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=1)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                WorkshopStock.objects.create(
                    user=self.user, game_version='dofus3', ingredient_ankama_id=1,
                    ingredient_subtype='resources', owned=2)

    def test_the_same_resource_in_two_versions_is_two_rows(self):
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=1)
        WorkshopStock.objects.create(
            user=self.user, game_version='touch', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=1)
        self.assertEqual(2, WorkshopStock.objects.filter(user=self.user).count())

    def test_deleting_the_user_deletes_the_stock(self):
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=1,
            ingredient_subtype='resources', owned=1)
        self.user.delete()
        self.assertEqual(0, WorkshopStock.objects.count())


class TheStockEndpointRequiresLoginTests(TestCase):

    def test_anonymous_is_redirected(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': 1, 'subtype': 'resources', 'owned': 5}])
        self.assertEqual(302, resp.status_code)
        self.assertEqual(0, WorkshopStock.objects.count())


class TheStockEndpointWritesOnlyItsCallersRowsTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user('stocker', 'stocker@test.local', 'pw-4242xy')
        self.other = User.objects.create_user('bystander', 'bystander@test.local', 'pw-4242xy')
        self.client.force_login(self.user)

    def test_a_new_owned_count_is_saved(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': 999, 'subtype': 'resources', 'owned': 40}])
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['success'])
        row = WorkshopStock.objects.get(user=self.user)
        self.assertEqual(40, row.owned)
        self.assertEqual({'999:resources': 40}, resp.json()['stock'])

    def test_zero_deletes_the_row(self):
        WorkshopStock.objects.create(
            user=self.user, game_version='dofus3', ingredient_ankama_id=999,
            ingredient_subtype='resources', owned=12)
        _post_stock(self.client, [
            {'ingredient_ankama_id': 999, 'subtype': 'resources', 'owned': 0}])
        self.assertFalse(WorkshopStock.objects.filter(user=self.user).exists())

    def test_writing_zero_for_an_unknown_resource_creates_nothing(self):
        _post_stock(self.client, [
            {'ingredient_ankama_id': 999, 'subtype': 'resources', 'owned': 0}])
        self.assertFalse(WorkshopStock.objects.exists())

    def test_bad_values_are_clamped_not_rejected(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': 999, 'subtype': 'resources', 'owned': -30},
            {'ingredient_ankama_id': 998, 'subtype': 'resources', 'owned': 10 ** 8},
            {'ingredient_ankama_id': 'not-an-id', 'subtype': 'resources', 'owned': 5}])
        self.assertEqual(200, resp.status_code)
        # A negative value clamps to 0, which deletes rather than stores a row
        self.assertFalse(WorkshopStock.objects.filter(
            user=self.user, ingredient_ankama_id=999).exists())
        self.assertEqual(0, resp.json()['stock']['999:resources'])
        self.assertEqual(MAX_STOCK_OWNED, WorkshopStock.objects.get(
            user=self.user, ingredient_ankama_id=998).owned)
        self.assertEqual(1, WorkshopStock.objects.filter(user=self.user).count())

    def test_more_than_the_cap_is_rejected_and_writes_nothing(self):
        updates = [{'ingredient_ankama_id': i, 'subtype': 'resources', 'owned': 1}
                   for i in range(MAX_STOCK_KEYS_PER_REQUEST + 1)]
        resp = _post_stock(self.client, updates)
        self.assertEqual(400, resp.status_code)
        self.assertFalse(WorkshopStock.objects.filter(user=self.user).exists())

    def test_an_empty_or_malformed_body_is_rejected(self):
        self.assertEqual(400, _post_stock(self.client, []).status_code)
        resp = self.client.post('/workshop/stock/', data='not json',
                                content_type='application/json')
        self.assertEqual(400, resp.status_code)

    def test_a_caller_never_writes_another_users_row(self):
        WorkshopStock.objects.create(
            user=self.other, game_version='dofus3', ingredient_ankama_id=999,
            ingredient_subtype='resources', owned=5)
        _post_stock(self.client, [
            {'ingredient_ankama_id': 999, 'subtype': 'resources', 'owned': 77}])
        self.assertEqual(5, WorkshopStock.objects.get(user=self.other).owned)
        self.assertEqual(77, WorkshopStock.objects.get(user=self.user).owned)

    def test_a_caller_never_reads_another_users_stock_on_the_page(self):
        WorkshopStock.objects.create(
            user=self.other, game_version='dofus3', ingredient_ankama_id=999,
            ingredient_subtype='resources', owned=5)
        from chardata.workshop_view import _stock_map
        self.assertEqual({}, _stock_map(self.user, 'dofus3'))

    def test_an_ankama_id_past_the_32_bit_column_is_dropped(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': 2 ** 31, 'subtype': 'resources', 'owned': 5}])
        self.assertEqual(400, resp.status_code)
        self.assertFalse(WorkshopStock.objects.filter(user=self.user).exists())

    def test_an_ankama_id_at_the_32_bit_column_ceiling_is_saved(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': 2 ** 31 - 1, 'subtype': 'resources', 'owned': 5}])
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(5, WorkshopStock.objects.get(user=self.user).owned)

    def test_a_negative_ankama_id_is_dropped(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': -1, 'subtype': 'resources', 'owned': 5}])
        self.assertEqual(400, resp.status_code)
        self.assertFalse(WorkshopStock.objects.filter(user=self.user).exists())


class TheStockRowCapPerVersionTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'capped-crafter', 'capped@test.local', 'pw-4242xy')
        self.client.force_login(self.user)
        WorkshopStock.objects.bulk_create([
            WorkshopStock(user=self.user, game_version='dofus3',
                          ingredient_ankama_id=i, ingredient_subtype='resources', owned=1)
            for i in range(MAX_STOCK_ROWS_PER_VERSION)])

    def test_a_new_resource_past_the_cap_is_rejected_and_writes_nothing(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': MAX_STOCK_ROWS_PER_VERSION,
             'subtype': 'resources', 'owned': 5}])
        self.assertEqual(400, resp.status_code)
        self.assertFalse(WorkshopStock.objects.filter(
            user=self.user, ingredient_ankama_id=MAX_STOCK_ROWS_PER_VERSION).exists())
        self.assertEqual(MAX_STOCK_ROWS_PER_VERSION,
                         WorkshopStock.objects.filter(user=self.user).count())

    def test_updating_an_existing_resource_at_the_cap_still_succeeds(self):
        resp = _post_stock(self.client, [
            {'ingredient_ankama_id': 0, 'subtype': 'resources', 'owned': 77}])
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(77, WorkshopStock.objects.get(
            user=self.user, ingredient_ankama_id=0).owned)
        self.assertEqual(MAX_STOCK_ROWS_PER_VERSION,
                         WorkshopStock.objects.filter(user=self.user).count())
