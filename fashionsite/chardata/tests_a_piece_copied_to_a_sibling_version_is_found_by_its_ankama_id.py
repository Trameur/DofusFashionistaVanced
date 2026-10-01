# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A copied piece is found in the other version by its Ankama id, never by our own id."""
from django.test import SimpleTestCase

from chardata.version_copy import (PieceMap, translated_exclusions,
                                   translated_inclusions, translated_overrides,
                                   translated_slots)

TYPES = {1: 'Hat', 4: 'Cloak', 6: 'Ring', 9: 'Dofus', 10: 'Pet'}
SLOTS = ('hat', 'cloak', 'ring1', 'ring2', 'dofus1', 'pet')


class _Item:

    def __init__(self, item_id, name, type_id, ankama_id, removed=False):
        self.id = item_id
        self.name = name
        self.type = type_id
        self.ankama_id = ankama_id
        self.removed = removed
        self.dofus_touch = False


class _Stat:

    def __init__(self, stat_id, key):
        self.id = stat_id
        self.key = key


class _Catalogue:
    """What PieceMap reads of a Structure, nothing more."""

    def __init__(self, items, stats=()):
        self.items_dict = {item.id: item for item in items}
        self.dt_items_dict = {}
        self.legacy_item_ids = {}
        self._stats = {stat.id: stat for stat in stats}

    def get_item_by_id(self, item_id):
        return self.items_dict.get(item_id)

    def get_type_name_by_id(self, type_id):
        return TYPES[type_id]

    def get_item_by_name(self, name, dofus_touch=False):
        return next((item for item in self.items_dict.values()
                     if item.name == name), None)

    def get_item_by_ankama_id(self, ankama_id, dofus_touch=False):
        return next((item for item in self.items_dict.values()
                     if item.ankama_id == ankama_id), None)

    def get_stat_by_id(self, stat_id):
        return self._stats.get(stat_id)

    def get_stat_by_key(self, key):
        return next((stat for stat in self._stats.values() if stat.key == key),
                    None)

    def get_item_name_in_language(self, item, language):
        return item.name


def _source():
    return _Catalogue([
        _Item(11, 'Gobball Hat', 1, 500),
        _Item(12, 'Gobball Cape', 4, 501),
        _Item(13, 'Old Ring', 6, 502),
        _Item(14, 'Gelano (#1)', 6, 503),
        _Item(15, 'Gelano (#2)', 6, 503),
        _Item(16, 'Retired Dofus', 9, 504),
        _Item(17, 'Nameless Pet', 10, None),
    ], [_Stat(1, 'vit'), _Stat(2, 'wis')])


def _target():
    return _Catalogue([
        _Item(9015, 'Gelano (#2)', 6, 503),
        _Item(9014, 'Gelano (#1)', 6, 503),
        _Item(9011, 'Gobball Hat', 1, 500),
        _Item(11, 'Gobball Cape', 1, 777),
        _Item(9012, 'Gobball Cape', 4, 501),
        _Item(9016, 'Retired Dofus', 9, 504, removed=True),
        _Item(9017, 'Nameless Pet', 10, None),
    ], [_Stat(20, 'wis'), _Stat(10, 'vit')])


class APieceIsFoundByItsAnkamaIdTests(SimpleTestCase):

    def setUp(self):
        self.pieces = PieceMap(_source(), _target())

    def test_no_source_id_names_the_same_piece_in_the_target(self):
        source, target = _source(), _target()
        same = [item_id for item_id in source.items_dict
                if item_id in target.items_dict
                and source.items_dict[item_id].ankama_id
                == target.items_dict[item_id].ankama_id]
        self.assertEqual([], same)
        self.assertIn(11, target.items_dict)

    def test_a_piece_is_found_under_the_targets_own_id(self):
        self.assertEqual(9011, self.pieces.item_id(11))
        self.assertEqual(9012, self.pieces.item_id(12))

    def test_the_branches_of_one_piece_keep_their_branch(self):
        self.assertEqual(9014, self.pieces.item_id(14))
        self.assertEqual(9015, self.pieces.item_id(15))

    def test_a_piece_without_an_ankama_id_is_found_by_its_name_and_type(self):
        self.assertEqual(9017, self.pieces.item_id(17))

    def test_a_piece_the_target_lacks_or_retired_has_no_counterpart(self):
        self.assertIsNone(self.pieces.item_id(13))
        self.assertIsNone(self.pieces.item_id(16))
        self.assertIsNone(self.pieces.item_id(404))

    def test_the_set_keeps_what_the_target_has_and_reports_the_rest(self):
        slots, missing = translated_slots(self.pieces, {
            'hat': 11, 'cloak': 12, 'ring1': 13, 'ring2': 14, 'dofus1': 16,
            'pet': None, 'emblem1': 17}, SLOTS)
        self.assertEqual({'hat': 9011, 'cloak': 9012, 'ring1': None,
                          'ring2': 9014, 'dofus1': None, 'pet': None}, slots)
        self.assertEqual(sorted([('ring1', 13), ('dofus1', 16), ('emblem1', 17)]),
                         sorted(missing))

    def test_locks_bans_and_rolls_move_to_the_targets_ids(self):
        locks, missing = translated_inclusions(
            self.pieces, {'hat': 11, 'ring1': 13, 'cloak': ''}, SLOTS)
        self.assertEqual({'hat': 9011}, locks)
        self.assertEqual([('ring1', 13)], missing)
        self.assertEqual([9012, 9015],
                         translated_exclusions(self.pieces, [12, 13, 15, 12]))
        self.assertEqual({9011: {10: 120, 20: 30}},
                         translated_overrides(self.pieces, {
                             11: {1: 120, 2: 30, 3: 5}, 13: {1: 50}}))
