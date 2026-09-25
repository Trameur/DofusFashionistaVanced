# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""POST workshop/addset/<set_id>/ adds each craftable set item once."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.structure import get_structure

VERSIONS = ('dofus3', 'touch')


def _prefix(game_version):
    return '' if game_version == 'dofus3' else '/%s' % game_version


def _a_set_with_a_craftable_and_a_noncraftable_item(game_version):
    """(set_id, craftable_ids, noncraftable_ids), or (None, [], []) if none fits."""
    structure = get_structure(game_version)
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        recipe_ids = {row[0] for row in
                      conn.execute('SELECT DISTINCT item FROM item_recipes')}
    finally:
        conn.close()

    for set_id, item_set in structure.sets_dict.items():
        item_ids = []
        seen = set()
        for raw_id in getattr(item_set, 'items', None) or []:
            item = structure.get_item_by_id(raw_id)
            if item is None or item.ankama_id in seen:
                continue
            seen.add(item.ankama_id)
            item_ids.append(item.id)
        craftable = [i for i in item_ids if i in recipe_ids]
        noncraftable = [i for i in item_ids if i not in recipe_ids]
        if craftable and noncraftable:
            return set_id, craftable, noncraftable
    return None, [], []


def _a_set_with_no_craftable_items(game_version):
    """set_id of a non-empty set with zero craftable items, or None if none fits."""
    structure = get_structure(game_version)
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        recipe_ids = {row[0] for row in
                      conn.execute('SELECT DISTINCT item FROM item_recipes')}
    finally:
        conn.close()

    for set_id, item_set in structure.sets_dict.items():
        item_ids = [structure.get_item_by_id(raw_id).id
                    for raw_id in (getattr(item_set, 'items', None) or [])
                    if structure.get_item_by_id(raw_id) is not None]
        if item_ids and not any(i in recipe_ids for i in item_ids):
            return set_id
    return None


class AddSetAddsOnlyCraftableItemsOnceTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'set-crafter', 'set-crafter@test.local', 'pw-4242xy')
        self.client.force_login(self.user)

    def test_addset_adds_only_the_craftable_items(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                set_id, craftable, noncraftable = (
                    _a_set_with_a_craftable_and_a_noncraftable_item(game_version))
                self.assertIsNotNone(
                    set_id, 'no mixed set to test against in %s' % game_version)

                resp = self.client.post(
                    '%s/workshop/addset/%d/' % (_prefix(game_version), set_id))
                self.assertEqual(200, resp.status_code)
                body = resp.json()
                self.assertTrue(body['success'])
                self.assertEqual(len(craftable), body['added'])

                for item_id in craftable:
                    self.assertTrue(WorkshopItem.objects.filter(
                        user=self.user, item_id=item_id,
                        game_version=game_version, quantity=1).exists())
                for item_id in noncraftable:
                    self.assertFalse(WorkshopItem.objects.filter(
                        user=self.user, item_id=item_id,
                        game_version=game_version).exists())

    def test_a_second_call_is_idempotent(self):
        set_id, craftable, _noncraftable = (
            _a_set_with_a_craftable_and_a_noncraftable_item('dofus3'))
        self.assertIsNotNone(set_id, 'no mixed set to test against in dofus3')

        self.client.post('/workshop/addset/%d/' % set_id)
        # A player bumps one quantity by hand before clicking the button again
        bumped = WorkshopItem.objects.filter(
            user=self.user, item_id=craftable[0], game_version='dofus3').first()
        bumped.quantity = 4
        bumped.save(update_fields=['quantity'])

        resp = self.client.post('/workshop/addset/%d/' % set_id)
        self.assertEqual(200, resp.status_code)
        self.assertEqual(0, resp.json()['added'])

        bumped.refresh_from_db()
        self.assertEqual(4, bumped.quantity, 'addset must never touch an existing row')

    def test_a_set_with_no_craftable_items_adds_nothing(self):
        set_id = _a_set_with_no_craftable_items('dofus3')
        self.assertIsNotNone(set_id, 'no all-noncraftable set to test against in dofus3')

        resp = self.client.post('/workshop/addset/%d/' % set_id)
        self.assertEqual(200, resp.status_code)
        body = resp.json()
        self.assertTrue(body['success'])
        self.assertEqual(0, body['added'])
        self.assertEqual(0, body['craftable'])

    def test_an_unknown_set_id_is_404(self):
        resp = self.client.post('/workshop/addset/99999999/')
        self.assertEqual(404, resp.status_code)

    def test_anonymous_cannot_addset(self):
        self.client.logout()
        set_id, _c, _n = _a_set_with_a_craftable_and_a_noncraftable_item('dofus3')
        self.assertIsNotNone(set_id)
        resp = self.client.post('/workshop/addset/%d/' % set_id)
        self.assertEqual(302, resp.status_code)
