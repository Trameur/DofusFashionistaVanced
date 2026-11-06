# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""A card of the Wakfu item list shows the game's lines, the same ones as the item page."""
import os
import re

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.wakfu_flag_for_tests import wakfu_flag

LIST = '/fr/wakfu/encyclopedia/'
ITEM_ID = re.compile(r'/equipment/(\d+)-')
HP_TOTALS = (
    "SELECT o.item, SUM(o.value) FROM stats_of_item o JOIN stats s ON s.id = o.stat"
    " JOIN items i ON i.id = o.item WHERE s.key = 'hp' AND i.removed = 0 GROUP BY o.item")


class AWakfuCardShowsTheLinesOfItsItemPageTests(TestCase):
    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)

    def listed(self, **query):
        with wakfu_flag(True):
            response = self.client.get(LIST, query)
        self.assertEqual(200, response.status_code)
        return response

    def test_a_card_keeps_the_percent_sign_and_the_element_count(self):
        html = self.listed(q='La Zimasse').content.decode('utf-8')
        self.assertIn('5 % Coup critique', html)
        self.assertIn('175 Maîtrise sur 3 éléments', html)
        self.assertIn('-400 Maîtrise Dos', html)
        self.assertNotIn('175 Maîtrise Élémentaire', html)

    def test_a_card_groups_thousands_as_the_item_page_does(self):
        total = max(row[1] for row in self.conn.execute(HP_TOTALS))
        self.assertGreater(total, 999)
        response = self.listed(order_key='hp', order_dir='desc')
        first = response.context['items_page'].object_list[0]
        self.assertIn('%d %03d PV' % (total // 1000, total % 1000),
                      [one['text'] for one in first['stat_lines']])

    def test_every_card_of_a_page_lists_the_worn_lines_of_its_item_page(self):
        cards = self.listed().context['items_page'].object_list
        self.assertTrue(cards)
        for card in cards:
            item_id = int(ITEM_ID.search(card['url']).group(1))
            with self.subTest(item=item_id):
                self.assertEqual(
                    [line.text for line in data.item_detail(item_id, 'fr').lines],
                    [one['text'] for one in card['stat_lines']])
