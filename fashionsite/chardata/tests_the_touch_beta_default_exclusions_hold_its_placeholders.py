# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The Touch Beta default exclusions hold its test and work-in-progress items, and only a lock list holds them back."""
import os
import re
import sqlite3

from django.test import SimpleTestCase

from chardata.lock_forbid import DEFAULT_EXCLUSION_ANKAMA_IDS, DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION
from fashionistapulp.fashionista_config import get_items_db_path

_PLACEHOLDER_IDS = (8422, 12596, 18555, 18557, 18559, 21593)
_PLACEHOLDER_NAME = re.compile(r'^\[!\]|\[FM\]|\[wip\]|\bWIP\b|\btest\b', re.I)


def _default_ids(version):
    return set(DEFAULT_EXCLUSION_ANKAMA_IDS) | set(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION.get(version, []))


class TouchBetaDefaultExclusionTests(SimpleTestCase):

    def _rows(self, query):
        path = get_items_db_path('touchbeta')
        if not os.path.exists(path):
            self.skipTest('touchbeta item database not in this checkout')
        connection = sqlite3.connect(path)
        try:
            return connection.execute(query).fetchall()
        finally:
            connection.close()

    def test_touch_beta_inherits_the_touch_list_for_its_own_ids(self):
        touch = set(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION['touch'])
        self.assertEqual(touch, set(DEFAULT_EXCLUSION_ANKAMA_IDS_BY_VERSION['touchbeta']))

    def test_every_placeholder_the_early_channel_ships_is_excluded_by_default(self):
        defaults = _default_ids('touchbeta')
        stored = {row[0] for row in self._rows('SELECT ankama_id FROM items')}
        for ankama_id in _PLACEHOLDER_IDS:
            with self.subTest(ankama_id=ankama_id):
                self.assertIn(ankama_id, stored)
                self.assertIn(ankama_id, defaults)

    def test_no_test_named_item_of_touch_beta_is_left_to_the_solver(self):
        defaults = _default_ids('touchbeta')
        rows = self._rows('SELECT ankama_id, name FROM items WHERE COALESCE(removed, 0) = 0')
        loose = sorted((ankama_id, name) for ankama_id, name in rows
                       if _PLACEHOLDER_NAME.search(name or '') and ankama_id not in defaults)
        self.assertEqual([], loose)
