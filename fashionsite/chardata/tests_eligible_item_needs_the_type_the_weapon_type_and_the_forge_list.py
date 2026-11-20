# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A dracorune goes on an item whose type the rune file names, whose weapon type a smithmagic skill works on, and that the forge list allows."""

import sqlite3

from django.test import SimpleTestCase

from fashionistapulp import weapon_forge
from fashionistapulp.dracorunes import eligible, eligible_item
from fashionistapulp.exo_options import (FORGEABLE_TYPES, FORGEABLE_WEAPON_TYPES,
                                         forgeable_type)
from fashionistapulp.item import Item
from fashionistapulp.structure import Structure
from fashionistapulp.weapon import WeaponType

VERSION = 'beta'
RUNES = {'item_types': ['Hat', 'Ring', 'Weapon']}
UNFORGEABLE_ID = min(weapon_forge.load(VERSION)['unforgeable'])


class TheEligibleItemTests(SimpleTestCase):

    def test_the_forge_list_holds_the_id_the_tests_use(self):
        self.assertFalse(weapon_forge.can_forge(VERSION, UNFORGEABLE_ID))
        self.assertTrue(weapon_forge.can_forge(VERSION, 1))

    def test_a_type_the_rune_file_does_not_name_is_refused(self):
        self.assertTrue(forgeable_type('Belt', None))
        self.assertFalse(eligible_item('Belt', None, 1, VERSION, RUNES))

    def test_a_type_the_rune_file_names_is_accepted(self):
        self.assertTrue(eligible_item('Hat', None, 1, VERSION, RUNES))
        self.assertTrue(eligible_item('Ring', None, UNFORGEABLE_ID, VERSION, RUNES))

    def test_a_version_without_a_rune_file_has_no_eligible_item(self):
        self.assertFalse(eligible_item('Hat', None, 1, VERSION, None))
        self.assertFalse(eligible('Hat', None))

    def test_a_weapon_needs_a_forgeable_weapon_type(self):
        for key in FORGEABLE_WEAPON_TYPES:
            self.assertTrue(eligible_item('Weapon', key, 1, VERSION, RUNES), key)
        self.assertFalse(eligible_item('Weapon', 'pickaxe', 1, VERSION, RUNES))
        self.assertFalse(eligible_item('Weapon', None, 1, VERSION, RUNES))

    def test_a_weapon_on_the_forge_list_is_refused(self):
        self.assertFalse(eligible_item('Weapon', 'staff', UNFORGEABLE_ID, VERSION, RUNES))

    def test_a_version_without_a_weapon_forge_has_no_eligible_weapon(self):
        self.assertFalse(eligible_item('Weapon', 'staff', 1, 'wakfu', RUNES))

    def test_the_type_rule_is_the_smithmagic_rule(self):
        for name in FORGEABLE_TYPES:
            self.assertTrue(forgeable_type(name, None))
        self.assertFalse(forgeable_type('Pet', None))
        self.assertFalse(forgeable_type('Pet', 'staff'))
        self.assertTrue(forgeable_type('Weapon', 'bow'))
        self.assertFalse(forgeable_type('Weapon', 'pickaxe'))


class _Catalogue:

    _table_exists = Structure._table_exists

    def __init__(self, game_version):
        self.game_version = game_version
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript(
            'CREATE TABLE weapon_weapontype (item INTEGER, weapontype INTEGER);'
            'INSERT INTO weapon_weapontype VALUES (2, 1);'
            'INSERT INTO weapon_weapontype VALUES (4, 2);')
        self.types_dict = {1: 'Hat', 2: 'Weapon'}
        self.weapon_type_dict = {}
        for type_id, key in ((1, 'staff'), (2, 'pickaxe')):
            weapon_type = WeaponType()
            weapon_type.id, weapon_type.key = type_id, key
            self.weapon_type_dict[type_id] = weapon_type
        self.items_dict = {}
        self.dt_items_dict = {}
        for item_id, type_id in ((1, 1), (2, 2), (4, 2)):
            item = Item()
            item.id = item_id
            item.type = type_id
            self.items_dict[item_id] = item


class TheStructureKeepsTheWeaponKeyTests(SimpleTestCase):

    def _read(self, game_version):
        catalogue = _Catalogue(game_version)
        Structure.read_forgeable_items_table(catalogue)
        return catalogue.items_dict

    def test_a_version_without_exo_per_item_keeps_the_key_and_forges_nothing(self):
        items = self._read('dofus3')
        self.assertEqual('staff', items[2].weapon_key)
        self.assertEqual('pickaxe', items[4].weapon_key)
        self.assertIsNone(items[1].weapon_key)
        self.assertFalse([item.id for item in items.values() if item.forgeable])

    def test_retro_keeps_the_key_and_the_smithmagic_pieces(self):
        items = self._read('retro')
        self.assertEqual('staff', items[2].weapon_key)
        self.assertEqual({1, 2}, {i for i, item in items.items() if item.forgeable})
