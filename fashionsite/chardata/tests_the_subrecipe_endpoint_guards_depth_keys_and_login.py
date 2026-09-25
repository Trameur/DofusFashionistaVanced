# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The subrecipe endpoint requires login, bounds its keys and depth, and
refuses to walk back into its own ancestor chain."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from fashionistapulp.fashionista_config import get_items_db_path


def _a_craftable_key(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            "SELECT DISTINCT i.ankama_id FROM items i "
            "JOIN item_recipes r ON r.item = i.id "
            "WHERE i.ankama_type = 'equipment' LIMIT 1").fetchone()
    finally:
        conn.close()
    return '%d:equipment' % row[0]


class TheSubrecipeEndpointRequiresLoginTests(TestCase):

    def test_an_anonymous_request_is_redirected(self):
        key = _a_craftable_key('dofus3')
        resp = self.client.get('/workshop/subrecipe/?keys=%s&depth=1' % key)
        self.assertEqual(302, resp.status_code)


class TheSubrecipeEndpointGuardsItsInputTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'subrecipe-guard', 'subrecipe-guard@test.local', 'pw-5541rt')
        self.client.force_login(self.user)
        self.key = _a_craftable_key('dofus3')

    def test_too_many_keys_are_refused(self):
        keys = ','.join('%d:equipment' % i for i in range(1, 42))
        resp = self.client.get('/workshop/subrecipe/?keys=%s&depth=1' % keys)
        self.assertEqual(400, resp.status_code)

    def test_a_missing_depth_is_refused(self):
        resp = self.client.get('/workshop/subrecipe/?keys=%s' % self.key)
        self.assertEqual(400, resp.status_code)

    def test_a_depth_of_zero_is_refused(self):
        resp = self.client.get('/workshop/subrecipe/?keys=%s&depth=0' % self.key)
        self.assertEqual(400, resp.status_code)

    def test_a_depth_past_the_cap_is_refused(self):
        resp = self.client.get('/workshop/subrecipe/?keys=%s&depth=9' % self.key)
        self.assertEqual(400, resp.status_code)

    def test_the_maximum_depth_is_accepted(self):
        resp = self.client.get('/workshop/subrecipe/?keys=%s&depth=8' % self.key)
        self.assertEqual(200, resp.status_code)
        self.assertTrue(resp.json()['success'])

    def test_a_key_already_in_its_own_path_is_refused_as_a_cycle(self):
        resp = self.client.get(
            '/workshop/subrecipe/?keys=%s&depth=2&path=%s' % (self.key, self.key))
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertTrue(data['subrecipes'][self.key]['cycle'])
        self.assertEqual([], data['subrecipes'][self.key]['children'])

    def test_an_unrelated_ancestor_does_not_block_expansion(self):
        resp = self.client.get(
            '/workshop/subrecipe/?keys=%s&depth=2&path=999999998:equipment' % self.key)
        self.assertEqual(200, resp.status_code)
        result = resp.json()['subrecipes'][self.key]
        self.assertNotIn('cycle', result)
        self.assertTrue(result['found'])
