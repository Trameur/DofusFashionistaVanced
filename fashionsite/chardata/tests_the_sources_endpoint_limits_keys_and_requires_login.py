# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""workshop/sources/: login required, at most MAX_SOURCE_KEYS_PER_REQUEST keys."""

import sqlite3

from django.contrib.auth.models import User
from django.test import TestCase

from chardata.workshop_view import MAX_SOURCE_KEYS_PER_REQUEST
from fashionistapulp.fashionista_config import get_items_db_path


def _a_dropped_resource_key():
    conn = sqlite3.connect(get_items_db_path('dofus3'))
    try:
        row = conn.execute(
            'SELECT resource_ankama_id FROM resource_drops LIMIT 1').fetchone()
    finally:
        conn.close()
    return '%d:resources' % row[0]


class TheSourcesEndpointRequiresLoginTests(TestCase):

    def test_anonymous_is_redirected(self):
        resp = self.client.get('/workshop/sources/?keys=1:resources')
        self.assertEqual(302, resp.status_code)


class TheSourcesEndpointAnswersALoggedInRequestTests(TestCase):

    def setUp(self):
        self.user = User.objects.create_user(
            'sourcer', 'sourcer@test.local', 'pw-4242xy')
        self.client.force_login(self.user)

    def test_a_known_key_returns_its_monsters_sorted_best_first(self):
        key = _a_dropped_resource_key()
        resp = self.client.get('/workshop/sources/?keys=%s' % key)
        self.assertEqual(200, resp.status_code)
        data = resp.json()
        self.assertTrue(data['success'])
        self.assertIn(key, data['sources'])
        entry = data['sources'][key]
        self.assertIn('monsters', entry)
        self.assertIn('crafted', entry)
        rates = [m['rate'] for m in entry['monsters']]
        self.assertEqual(sorted(rates, reverse=True), rates)

    def test_more_than_the_cap_is_rejected(self):
        keys = ','.join('%d:resources' % i
                        for i in range(MAX_SOURCE_KEYS_PER_REQUEST + 1))
        resp = self.client.get('/workshop/sources/?keys=%s' % keys)
        self.assertEqual(400, resp.status_code)

    def test_exactly_the_cap_is_accepted(self):
        keys = ','.join('%d:resources' % i
                        for i in range(MAX_SOURCE_KEYS_PER_REQUEST))
        resp = self.client.get('/workshop/sources/?keys=%s' % keys)
        self.assertEqual(200, resp.status_code)

    def test_no_keys_is_rejected(self):
        resp = self.client.get('/workshop/sources/')
        self.assertEqual(400, resp.status_code)

    def test_malformed_keys_are_dropped_not_crashed_on(self):
        resp = self.client.get('/workshop/sources/?keys=notanumber,42,42:resources')
        self.assertEqual(200, resp.status_code)
        self.assertEqual(['42:resources'], list(resp.json()['sources'].keys()))
