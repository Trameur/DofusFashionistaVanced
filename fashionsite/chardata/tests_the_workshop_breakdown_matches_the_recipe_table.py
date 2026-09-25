# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""workshop_breakdown agrees with item_recipes, in a constant number of queries."""

import sqlite3
from collections import defaultdict
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_sources import get_source_ankama_ids
from chardata.recipe_util import workshop_breakdown
from fashionistapulp.fashionista_config import get_items_db_path

VERSIONS = ('dofus3', 'beta', 'dofus2', 'retro', 'touch')
MULTIPLIER = 8


def _an_item_with_a_recipe(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        row = conn.execute(
            'SELECT DISTINCT item FROM item_recipes ORDER BY item LIMIT 1').fetchone()
    finally:
        conn.close()
    return row[0] if row else None


def _recipe_rows(game_version, item_id):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        return conn.execute(
            'SELECT ingredient_ankama_id, ingredient_subtype, quantity '
            'FROM item_recipes WHERE item = ? ORDER BY position', (item_id,)).fetchall()
    finally:
        conn.close()


def _two_items_sharing_an_ingredient(game_version):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        shared = conn.execute(
            'SELECT ingredient_ankama_id, ingredient_subtype FROM item_recipes '
            'GROUP BY ingredient_ankama_id, ingredient_subtype '
            'HAVING COUNT(DISTINCT item) > 1 LIMIT 1').fetchone()
        if shared is None:
            return None
        ankama_id, subtype = shared
        item_rows = conn.execute(
            'SELECT DISTINCT item FROM item_recipes '
            'WHERE ingredient_ankama_id = ? AND ingredient_subtype = ? '
            'ORDER BY item LIMIT 2', (ankama_id, subtype)).fetchall()
    finally:
        conn.close()
    return (ankama_id, subtype), [row[0] for row in item_rows]


class TheBreakdownAgreesWithTheRecipeTableTests(SimpleTestCase):

    def test_one_crafted_item_per_version_matches_item_recipes(self):
        for game_version in VERSIONS:
            with self.subTest(game_version=game_version):
                item_id = _an_item_with_a_recipe(game_version)
                self.assertIsNotNone(
                    item_id, 'no recipe to test against in %s' % game_version)

                expected = _recipe_rows(game_version, item_id)
                breakdown = workshop_breakdown(
                    [(item_id, MULTIPLIER)], 'en', game_version)
                rows = breakdown['items'][item_id]

                self.assertEqual(len(expected), len(rows))
                for (ankama_id, subtype, quantity), row in zip(expected, rows):
                    self.assertEqual(ankama_id, row['ankama_id'])
                    self.assertEqual(subtype, row['subtype'])
                    self.assertEqual(quantity, row['quantity'])

                expected_totals = defaultdict(int)
                for ankama_id, subtype, quantity in expected:
                    expected_totals[(ankama_id, subtype)] += quantity
                totals_by_key = {(r['ankama_id'], r['subtype']): r['quantity']
                                 for r in breakdown['resources']}
                for key, total in expected_totals.items():
                    self.assertEqual(total * MULTIPLIER, totals_by_key[key])


class TheBreakdownMergesASharedResourceAcrossCardsTests(SimpleTestCase):

    def test_two_items_sharing_a_resource_sum_its_need_and_used_by(self):
        shared = _two_items_sharing_an_ingredient('dofus3')
        self.assertIsNotNone(shared, 'no shared ingredient to test against in dofus3')
        (ankama_id, subtype), item_ids = shared
        self.assertEqual(2, len(item_ids), 'need two distinct items sharing it')
        item_a, item_b = item_ids

        expected_quantity = 0
        for item_id in item_ids:
            for row_ankama_id, row_subtype, quantity in _recipe_rows('dofus3', item_id):
                if (row_ankama_id, row_subtype) == (ankama_id, subtype):
                    expected_quantity += quantity

        breakdown = workshop_breakdown(
            [(item_a, 1), (item_b, 1)], 'en', 'dofus3')
        resource = next(r for r in breakdown['resources']
                        if (r['ankama_id'], r['subtype']) == (ankama_id, subtype))

        self.assertEqual(expected_quantity, resource['quantity'])
        self.assertEqual(2, resource['used_by'])


class _CountingCursor:

    def __init__(self, cursor, counter):
        self._cursor = cursor
        self._counter = counter

    def execute(self, *args, **kwargs):
        self._counter['n'] += 1
        return self._cursor.execute(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _CountingConnection:

    def __init__(self, conn, counter):
        self._conn = conn
        self._counter = counter

    def cursor(self):
        return _CountingCursor(self._conn.cursor(), self._counter)

    def __getattr__(self, name):
        return getattr(self._conn, name)


class TheBreakdownRunsAConstantNumberOfQueriesTests(SimpleTestCase):

    def _query_count(self, item_ids):
        # The craftable-ankama-id set is cached per version once warm; prime it
        # here so the measurement reflects its steady-state, per-request cost.
        get_source_ankama_ids('dofus3')

        counter = {'n': 0}
        real_connect = sqlite3.connect

        def counting_connect(*args, **kwargs):
            return _CountingConnection(real_connect(*args, **kwargs), counter)

        with mock.patch('chardata.recipe_util.sqlite3.connect',
                        side_effect=counting_connect):
            workshop_breakdown(
                [(item_id, 1) for item_id in item_ids], 'en', 'dofus3')
        return counter['n']

    def test_one_item_and_thirty_items_cost_the_same_query_count(self):
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            item_ids = [row[0] for row in conn.execute(
                'SELECT DISTINCT item FROM item_recipes ORDER BY item LIMIT 30')]
        finally:
            conn.close()
        self.assertGreaterEqual(len(item_ids), 30, 'not enough recipes to sample 30')

        one_item_queries = self._query_count(item_ids[:1])
        thirty_item_queries = self._query_count(item_ids)

        self.assertEqual(one_item_queries, thirty_item_queries)
        self.assertLessEqual(thirty_item_queries, 5)
