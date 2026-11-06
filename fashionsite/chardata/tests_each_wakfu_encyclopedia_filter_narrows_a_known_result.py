# Copyright (C) 2026 The Dofus Fashionista
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 3 of the License, or (at your option) any later version.

"""Each filter of the Wakfu item list reduces the whole list to the count SQL gives."""
import json
import os
import re
from urllib.parse import urlencode

from django.core.cache import cache
from django.test import TestCase

from chardata import wakfu_encyclopedia_data as data
from chardata.wakfu_flag_for_tests import wakfu_flag

LIST = '/wakfu/encyclopedia/'
LIVE_STAT_TOTALS = (
    'SELECT o.item, SUM(o.value) AS total FROM stats_of_item o'
    ' JOIN stats s ON s.id = o.stat JOIN items i ON i.id = o.item'
    ' WHERE i.removed = 0 AND s.key = ? GROUP BY o.item')
ITEM_ID = re.compile(r'/item/equipment/(\d+)-')


class EachWakfuEncyclopediaFilterNarrowsAKnownResultTests(TestCase):
    def setUp(self):
        cache.clear()
        if not os.path.exists(data.database_path()):
            self.skipTest('no Wakfu database built; run update_data_wakfu.py')
        self.conn = data.connect()
        self.addCleanup(self.conn.close)
        self.total = self.scalar('SELECT COUNT(*) FROM items WHERE removed = 0')

    def scalar(self, sql, *args):
        return self.conn.execute(sql, args).fetchone()[0]

    def listed(self, **query):
        with wakfu_flag(True):
            response = self.client.get(LIST + '?' + urlencode(query, doseq=True))
        self.assertEqual(200, response.status_code, query)
        return response

    def count(self, **query):
        return self.listed(**query).context['items_count']

    def page_ids(self, response):
        return [int(ITEM_ID.search(card['url']).group(1))
                for card in response.context['items_page'].object_list]

    def test_the_unfiltered_list_counts_every_live_item(self):
        self.assertEqual(self.total, self.count())

    def test_a_name_search_narrows_to_the_names_that_contain_it(self):
        expected = self.scalar(
            "SELECT COUNT(*) FROM items i JOIN item_names n ON n.item = i.id"
            " WHERE i.removed = 0 AND n.language = 'en' AND LOWER(n.name) LIKE '%amulet%'")
        self.assertTrue(0 < expected < self.total)
        self.assertEqual(expected, self.count(q='Amulet'))

    def test_a_type_narrows_to_the_items_of_that_type(self):
        item_type, expected = self.conn.execute(
            'SELECT type, COUNT(*) FROM items WHERE removed = 0 GROUP BY type'
            ' ORDER BY COUNT(*) DESC, type LIMIT 1').fetchone()
        self.assertLess(expected, self.total)
        self.assertEqual(expected, self.count(type=item_type))

    def test_a_rarity_narrows_to_the_items_of_that_rarity(self):
        rarity, expected = self.conn.execute(
            'SELECT r.rarity, COUNT(*) FROM item_rarity r JOIN items i ON i.id = r.item'
            ' WHERE i.removed = 0 GROUP BY r.rarity ORDER BY COUNT(*) DESC, r.rarity'
            ' LIMIT 1').fetchone()
        self.assertLess(expected, self.total)
        self.assertEqual(expected, self.count(rarity=rarity))

    def test_a_minimum_level_keeps_the_items_at_or_above_it(self):
        level = self.scalar('SELECT CAST(AVG(level) AS INTEGER) FROM items WHERE removed = 0')
        expected = self.scalar(
            'SELECT COUNT(*) FROM items WHERE removed = 0 AND level >= ?', level)
        self.assertTrue(0 < expected < self.total)
        self.assertEqual(expected, self.count(min_level=level))

    def test_a_maximum_level_keeps_the_items_at_or_below_it(self):
        level = self.scalar('SELECT CAST(AVG(level) AS INTEGER) FROM items WHERE removed = 0')
        expected = self.scalar(
            'SELECT COUNT(*) FROM items WHERE removed = 0 AND level <= ?', level)
        self.assertTrue(0 < expected < self.total)
        self.assertEqual(expected, self.count(max_level=level))

    def test_a_stat_row_on_hp_keeps_the_items_whose_hp_reaches_it(self):
        totals = [row[1] for row in self.conn.execute(LIVE_STAT_TOTALS, ('hp',))]
        minimum = sorted(totals)[len(totals) // 2]
        expected = sum(1 for one in totals if one >= minimum)
        self.assertTrue(0 < expected < self.total)
        self.assertEqual(expected, self.count(stat_key='hp', stat_min=minimum))

    def test_a_stat_row_on_another_stat_keeps_the_items_that_reach_it(self):
        key = self.conn.execute(
            'SELECT s.key FROM stats_of_item o JOIN stats s ON s.id = o.stat'
            ' JOIN items i ON i.id = o.item WHERE i.removed = 0 AND s.key <> ?'
            ' GROUP BY s.key ORDER BY COUNT(DISTINCT o.item) DESC, s.key LIMIT 1',
            ('hp',)).fetchone()[0]
        totals = [row[1] for row in self.conn.execute(LIVE_STAT_TOTALS, (key,))]
        minimum = sorted(totals)[len(totals) // 2]
        expected = sum(1 for one in totals if one >= minimum)
        self.assertTrue(0 < expected < self.total)
        self.assertEqual(expected, self.count(stat_key=key, stat_min=minimum))

    def test_an_order_row_on_hp_sorts_the_page_by_hp(self):
        totals = dict(self.conn.execute(LIVE_STAT_TOTALS, ('hp',)).fetchall())
        descending = self.listed(order_rows_json=json.dumps([{'key': 'hp', 'dir': 'desc'}]))
        shown = [totals.get(one, 0) for one in self.page_ids(descending)]
        self.assertEqual(shown, sorted(shown, reverse=True))
        self.assertEqual(max(totals.values()), shown[0])
        ascending = self.listed(order_key='hp', order_dir='asc')
        shown = [totals.get(one, 0) for one in self.page_ids(ascending)]
        self.assertEqual(shown, sorted(shown))

    def test_an_order_row_on_level_sorts_the_page_by_level(self):
        levels = dict(self.conn.execute('SELECT id, level FROM items').fetchall())
        ascending = self.listed(order_key='level', order_dir='asc')
        shown = [levels[one] for one in self.page_ids(ascending)]
        self.assertEqual(shown, sorted(shown))
        self.assertEqual(self.scalar('SELECT MIN(level) FROM items WHERE removed = 0'), shown[0])

    def test_an_order_row_on_name_sorts_the_page_by_name(self):
        response = self.listed(order_key='name', order_dir='asc')
        shown = [card['name'].lower() for card in response.context['items_page'].object_list]
        self.assertEqual(shown, sorted(shown))

    def test_a_value_that_does_not_parse_leaves_the_list_unfiltered(self):
        for query in ({'type': 'abc'}, {'type': 999999}, {'rarity': 'zzz'},
                      {'rarity': 999999}, {'min_level': 'x'}, {'max_level': '1.5e'},
                      {'stat_key': 'no_such_stat', 'stat_min': 5},
                      {'stat_key': 'hp', 'stat_min': 'many'},
                      {'order_key': 'no_such_stat', 'order_dir': 'up'},
                      {'order_rows_json': '{not json'}, {'page': 'abc'}):
            with self.subTest(query=query):
                self.assertEqual(self.total, self.count(**query))
