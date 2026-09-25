# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""get_resource_sources costs the same number of SQL statements at 1 or 60 keys."""

import sqlite3
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_sources import get_source_ankama_ids
from chardata.workshop_sources import MAX_SOURCE_KEYS_PER_REQUEST, get_resource_sources
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


def _resource_keys(game_version, limit):
    conn = sqlite3.connect(get_items_db_path(game_version))
    try:
        rows = conn.execute(
            'SELECT DISTINCT resource_ankama_id FROM resource_drops '
            'ORDER BY resource_ankama_id LIMIT ?', (limit,)).fetchall()
    finally:
        conn.close()
    return [(row[0], 'resources') for row in rows]


class TheSourcesEndpointRunsABoundedQueryCountTests(SimpleTestCase):

    def _query_count(self, keys):
        counter = {'n': 0}
        real_connect = sqlite3.connect

        def counting_connect(*args, **kwargs):
            return _CountingConnection(real_connect(*args, **kwargs), counter)

        with mock.patch('chardata.workshop_sources.sqlite3.connect',
                        side_effect=counting_connect):
            get_resource_sources(keys, 'dofus3', 'en')
        return counter['n']

    def test_one_key_and_sixty_keys_cost_the_same_query_count(self):
        keys = _resource_keys('dofus3', MAX_SOURCE_KEYS_PER_REQUEST)
        self.assertGreaterEqual(
            len(keys), MAX_SOURCE_KEYS_PER_REQUEST,
            'not enough dropped resources to sample %d' % MAX_SOURCE_KEYS_PER_REQUEST)

        # Warms the process-wide id cache uncounted, so neither count below pays it.
        get_source_ankama_ids('dofus3')

        one_key_queries = self._query_count(keys[:1])
        sixty_key_queries = self._query_count(keys)

        self.assertEqual(one_key_queries, sixty_key_queries)
        self.assertLessEqual(sixty_key_queries, 8)
