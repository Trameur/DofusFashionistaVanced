# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""The Wakfu item list holds the records of the database, page after page."""
import os

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.wakfu_flag_for_tests import wakfu_flag

LIST = '/wakfu/encyclopedia/'
PER_PAGE = 39


class WakfuEncyclopediaPagesMatchTheRecordsTests(TestCase):
    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.total = self.conn.execute(
            'SELECT COUNT(*) FROM items WHERE removed = 0').fetchone()[0]
        self.pages = -(-self.total // PER_PAGE)

    def get(self, query=''):
        with wakfu_flag(True):
            response = self.client.get(LIST + query)
        self.assertEqual(200, response.status_code)
        return response

    def test_the_paginator_count_is_the_number_of_live_items(self):
        page = self.get().context['items_page']
        self.assertEqual(self.total, page.paginator.count)
        self.assertEqual(self.pages, page.paginator.num_pages)
        self.assertEqual(PER_PAGE, len(page.object_list))

    def test_the_last_page_holds_what_the_count_says(self):
        page = self.get('?page=%d' % self.pages).context['items_page']
        self.assertEqual(self.pages, page.number)
        self.assertEqual(self.total - PER_PAGE * (self.pages - 1), len(page.object_list))

    def test_a_page_past_the_end_is_the_last_page(self):
        page = self.get('?page=%d' % (self.pages + 50)).context['items_page']
        self.assertEqual(self.pages, page.number)

    def test_a_few_pages_repeat_no_item(self):
        seen = []
        for number in range(1, self.pages + 1, max(1, self.pages // 6)):
            page = self.get('?page=%d' % number).context['items_page']
            seen.extend(card['url'] for card in page.object_list)
        self.assertEqual(len(seen), len(set(seen)))

    def test_the_canonical_ignores_a_key_that_is_not_a_filter(self):
        plain = self.get('?page=2').context['canonical_url']
        self.assertTrue(plain.endswith(LIST + '?page=2'), plain)
        self.assertEqual(plain, self.get('?page=2&utm_source=x').context['canonical_url'])
        self.assertTrue(self.get('?page=2&q=ring').context['canonical_url'].endswith(LIST))
        self.assertTrue(self.get('?page=2&rarity=1').context['canonical_url'].endswith(LIST))

    def test_the_search_placeholder_is_a_live_item_name_and_does_not_change(self):
        names = {name for (name,) in self.conn.execute(
            "SELECT n.name FROM item_names n JOIN items i ON i.id = n.item"
            " WHERE i.removed = 0 AND n.language = 'en'")}
        first = self.get().context['search_example']
        self.assertIn(first, names)
        self.assertEqual(first, self.get('?q=ring').context['search_example'])
