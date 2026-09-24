# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
from types import SimpleNamespace
from unittest import mock

from django.test import SimpleTestCase


class StructureItemOrderCacheTests(SimpleTestCase):
    def test_sorted_item_lists_are_cached_without_sharing_mutable_results(self):
        from fashionistapulp.structure import Structure

        structure = object.__new__(Structure)
        structure.types = {200: {'Hat': [SimpleNamespace(name='Beta'),
                                          SimpleNamespace(name='Alpha')]}}
        structure.dt_types = {200: {'Hat': []}}
        structure._unique_items_by_type_and_level_cache = {}
        builtin_sorted = sorted

        with mock.patch('builtins.sorted', wraps=builtin_sorted) as sorter:
            first = structure.get_unique_items_by_type_and_level('Hat', 200)
            first.clear()
            second = structure.get_unique_items_by_type_and_level('Hat', 200)

        self.assertEqual(['Alpha', 'Beta'], [item.name for item in second])
        self.assertEqual(1, sorter.call_count)
