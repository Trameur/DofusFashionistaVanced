# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""workshop.js reads the csrf token from the hidden form and sends it back
as the X-CSRFToken header, the way inventory.html and forgemagie.html do.
This drives that handshake for real, with CSRF checks turned on, instead of
trusting the test client's default bypass."""

import json
import re
import sqlite3

from django.contrib.auth.models import User
from django.test import Client, TestCase

from chardata.models import WorkshopStock
from fashionistapulp.fashionista_config import get_items_db_path

_CSRF_FORM_RE = re.compile(r'<form id="ws-csrf"[^>]*>(.*?)</form>', re.S)
_CSRF_VALUE_RE = re.compile(r'value="([^"]+)"')


def _a_resource_ingredient():
    conn = sqlite3.connect(get_items_db_path('dofus3'))
    try:
        row = conn.execute(
            "SELECT ingredient_ankama_id, ingredient_subtype FROM item_recipes "
            "LIMIT 1").fetchone()
    finally:
        conn.close()
    return row


class TheHiddenFormTokenActuallySatisfiesCsrfTests(TestCase):

    def setUp(self):
        self.client = Client(enforce_csrf_checks=True)
        self.user = User.objects.create_user(
            'csrf-crafter', 'csrf-crafter@test.local', 'pw-real-token-1')
        self.client.force_login(self.user)

    def test_the_pages_own_token_is_accepted_as_the_header(self):
        ankama_id, subtype = _a_resource_ingredient()
        self.assertIsNotNone(ankama_id, 'no ingredient to stock in dofus3')

        page = self.client.get('/workshop/')
        self.assertEqual(200, page.status_code)
        html = page.content.decode('utf-8')
        form_match = _CSRF_FORM_RE.search(html)
        self.assertIsNotNone(form_match, 'the hidden csrf form is missing from the page')
        value_match = _CSRF_VALUE_RE.search(form_match.group(1))
        self.assertIsNotNone(value_match, 'the csrf input carries no value')
        token = value_match.group(1)

        resp = self.client.post(
            '/workshop/stock/',
            data=json.dumps({'updates': [{
                'ingredient_ankama_id': ankama_id,
                'subtype': subtype,
                'owned': 7,
            }]}),
            content_type='application/json',
            HTTP_X_CSRFTOKEN=token)

        self.assertEqual(200, resp.status_code, resp.content)
        self.assertTrue(resp.json()['success'])
        self.assertEqual(
            7, WorkshopStock.objects.get(
                user=self.user, game_version='dofus3',
                ingredient_ankama_id=ankama_id, ingredient_subtype=subtype).owned)

    def test_the_same_request_without_the_header_is_refused(self):
        ankama_id, subtype = _a_resource_ingredient()
        self.client.get('/workshop/')

        resp = self.client.post(
            '/workshop/stock/',
            data=json.dumps({'updates': [{
                'ingredient_ankama_id': ankama_id,
                'subtype': subtype,
                'owned': 7,
            }]}),
            content_type='application/json')

        self.assertEqual(403, resp.status_code)
