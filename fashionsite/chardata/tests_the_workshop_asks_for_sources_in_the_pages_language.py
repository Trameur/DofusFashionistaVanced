# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The workshop fetches its drop sources under the page's own language prefix."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.models import WorkshopItem
from fashionistapulp.fashionista_config import get_items_db_path


def _a_dropped_resource_key():
    conn = sqlite3.connect(get_items_db_path('dofus3'))
    try:
        row = conn.execute(
            'SELECT resource_ankama_id FROM resource_drops LIMIT 1').fetchone()
    finally:
        conn.close()
    return '%d:resources' % row[0]


def _a_crafted_item_id(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        return conn.execute('SELECT item FROM item_recipes LIMIT 1').fetchone()[0]
    finally:
        conn.close()


class TheSourcesUrlKeepsTheLanguagePrefixTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'polyglot', 'polyglot@test.local', 'pw-4242xy')
        self.client.force_login(self.user)
        for game_version in ('dofus3', 'touch'):
            WorkshopItem.objects.create(
                user=self.user, item_id=_a_crafted_item_id(game_version),
                game_version=game_version, quantity=1)

    def test_a_german_page_asks_the_german_endpoint(self):
        page = self.client.get('/de/workshop/').content.decode('utf-8')
        self.assertIn('/de/workshop/sources/', page)

    def test_a_prefixed_version_keeps_both_prefixes(self):
        page = self.client.get('/de/touch/workshop/').content.decode('utf-8')
        self.assertIn('/de/touch/workshop/sources/', page)

    def test_an_unprefixed_page_asks_the_unprefixed_endpoint(self):
        page = self.client.get('/workshop/').content.decode('utf-8')
        self.assertIn('"/workshop/sources/"', page)

    def test_the_prefixed_endpoint_answers_in_that_language(self):
        key = _a_dropped_resource_key()
        levels = {}
        for prefix in ('/de', '/fr'):
            data = self.client.get('%s/workshop/sources/?keys=%s' % (prefix, key)).json()
            levels[prefix] = [m['level'] for m in data['sources'][key]['monsters'] if m['level']]
        self.assertTrue(levels['/de'] and levels['/fr'])
        self.assertNotEqual(levels['/de'], levels['/fr'])
