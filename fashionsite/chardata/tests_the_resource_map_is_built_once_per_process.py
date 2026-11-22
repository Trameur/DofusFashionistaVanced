# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The map from a resource to the items it forbids reads the items DB once per process and version."""
import pickle
import sqlite3
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase

from chardata import resource_ban
from fashionistapulp.structure import get_structure

CRIMSON_PEBBLE = '12737:resources'


class TheResourceMapIsBuiltOnceTests(SimpleTestCase):

    def setUp(self):
        patcher = mock.patch.dict(resource_ban._resource_map_cache, clear=True)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.char = SimpleNamespace(
            id=1, game_version='dofus3',
            options=pickle.dumps({resource_ban.OPTION_KEY: [CRIMSON_PEBBLE]}))

    def test_a_second_call_opens_no_database(self):
        with mock.patch.object(resource_ban.sqlite3, 'connect', wraps=sqlite3.connect) as connect:
            first = resource_ban._items_by_resource('dofus3')
            self.assertEqual(1, connect.call_count)
            second = resource_ban._items_by_resource('dofus3')
            self.assertEqual(1, connect.call_count)
        self.assertIs(first, second)

    def test_every_reader_of_the_ban_shares_the_one_build(self):
        structure = get_structure('dofus3')
        with mock.patch.object(resource_ban.sqlite3, 'connect', wraps=sqlite3.connect) as connect:
            resource_ban.banned_resource_keys(self.char)
            resource_ban.items_the_ban_forbids(self.char, structure)
            resource_ban.items_the_ban_forbids(self.char, structure, {1})
            self.assertEqual(1, connect.call_count)

    def test_each_version_is_built_once_on_its_own(self):
        with mock.patch.object(resource_ban.sqlite3, 'connect', wraps=sqlite3.connect) as connect:
            for version in ('dofus3', 'retro', 'dofus3', 'retro'):
                resource_ban._items_by_resource(version)
            self.assertEqual(2, connect.call_count)
