# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""expand_subrecipes runs the same small number of queries for one key or many."""

import sqlite3
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_sources import get_source_ankama_ids
from chardata.recipe_util import expand_subrecipes
from fashionistapulp.fashionista_config import get_items_db_path


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


class TheSubrecipeExpansionRunsAConstantNumberOfQueriesTests(SimpleTestCase):

    def _query_count(self, keys):
        # The craftable-ankama-id set is cached per version once warm; prime it
        # here so the measurement reflects its steady-state, per-request cost.
        get_source_ankama_ids('dofus3')

        counter = {'n': 0}
        real_connect = sqlite3.connect

        def counting_connect(*args, **kwargs):
            return _CountingConnection(real_connect(*args, **kwargs), counter)

        with mock.patch('chardata.recipe_util.sqlite3.connect',
                        side_effect=counting_connect):
            expand_subrecipes(keys, 'dofus3', 'en')
        return counter['n']

    def test_one_key_and_thirty_keys_cost_the_same_query_count(self):
        conn = sqlite3.connect(get_items_db_path('dofus3'))
        try:
            ankama_ids = [row[0] for row in conn.execute(
                "SELECT DISTINCT i.ankama_id FROM items i "
                "JOIN item_recipes r ON r.item = i.id "
                "WHERE i.ankama_type = 'equipment' LIMIT 30")]
        finally:
            conn.close()
        self.assertGreaterEqual(len(ankama_ids), 30, 'not enough recipes to sample 30')
        keys = [(ankama_id, 'equipment') for ankama_id in ankama_ids]

        one_key_queries = self._query_count(keys[:1])
        thirty_key_queries = self._query_count(keys)

        self.assertEqual(one_key_queries, thirty_key_queries)
        self.assertLessEqual(thirty_key_queries, 6)
