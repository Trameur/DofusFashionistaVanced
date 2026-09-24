# Copyright (C) 2020 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License
# along with this program; if not, write to the Free Software Foundation,
# Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.

"""Ankama's beta client test item (ankama_id 34569) must not get a live
encyclopedia page or a sitemap entry."""

from django.test import TestCase


TEST_ITEM_ANKAMA_ID = 34569
TEST_ITEM_URL = '/beta/encyclopedia/item/equipment/34569-test-masquer-effet/'


class BetaClientTestItemHiddenTests(TestCase):
    def test_the_item_page_answers_404(self):
        response = self.client.get(TEST_ITEM_URL)
        self.assertEqual(response.status_code, 404)

    def test_the_item_page_is_not_indexable(self):
        response = self.client.get(TEST_ITEM_URL)
        self.assertTrue(response.context['noindex'])

    def test_the_sitemap_drops_the_item(self):
        from fashionsite.urls import _sitemap_encyclopedia_items

        xml = _sitemap_encyclopedia_items('https://dofusfashionista.gg', 'en')
        self.assertNotIn('34569-test-masquer-effet', xml)

    def test_the_sitemap_still_lists_a_live_beta_item(self):
        from fashionsite.urls import _sitemap_encyclopedia_items

        xml = _sitemap_encyclopedia_items('https://dofusfashionista.gg', 'en')
        self.assertIn('/beta/encyclopedia/item/', xml)

    def test_the_item_is_marked_removed_in_the_beta_database(self):
        import sqlite3

        from fashionistapulp.fashionista_config import get_items_db_path

        conn = sqlite3.connect(get_items_db_path('beta'))
        try:
            row = conn.execute(
                'SELECT removed FROM items WHERE ankama_id = ?',
                (TEST_ITEM_ANKAMA_ID,)).fetchone()
        finally:
            conn.close()
        self.assertIsNotNone(row)
        self.assertTrue(row[0])
