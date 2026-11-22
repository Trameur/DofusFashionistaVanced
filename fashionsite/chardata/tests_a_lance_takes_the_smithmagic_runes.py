# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A lance takes an exo, a dracorune and a transcendence rune; a pickaxe and a scythe take none."""

import sqlite3

from django.test import SimpleTestCase

from chardata.transcendence_advice import best_transcendence
from fashionistapulp import weapon_forge
from fashionistapulp.dracorunes import eligible_item
from fashionistapulp.exo_options import forgeable_type
from fashionistapulp.item import Item
from fashionistapulp.structure import Structure
from fashionistapulp.weapon import WeaponType

RUNES = {'item_types': ['Weapon']}
FORGEABLE_ID = min(item_id for item_id in range(1, 100000)
                   if weapon_forge.can_forge('beta', item_id))


class _Catalogue:

    _table_exists = Structure._table_exists

    def __init__(self, game_version):
        self.game_version = game_version
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript(
            'CREATE TABLE weapon_weapontype (item INTEGER, weapontype INTEGER);'
            'INSERT INTO weapon_weapontype VALUES (1, 1);'
            'INSERT INTO weapon_weapontype VALUES (2, 2);'
            'INSERT INTO weapon_weapontype VALUES (3, 3);')
        self.types_dict = {1: 'Weapon'}
        self.weapon_type_dict = {}
        for type_id, key in ((1, 'lance'), (2, 'pickaxe'), (3, 'scythe')):
            weapon_type = WeaponType()
            weapon_type.id, weapon_type.key = type_id, key
            self.weapon_type_dict[type_id] = weapon_type
        self.items_dict = {}
        self.dt_items_dict = {}
        for item_id in (1, 2, 3):
            item = Item()
            item.id = item_id
            item.type = 1
            self.items_dict[item_id] = item


class ALanceTakesTheSmithmagicRunesTests(SimpleTestCase):

    def test_a_lance_is_a_forgeable_weapon_and_a_pickaxe_and_a_scythe_are_not(self):
        self.assertTrue(forgeable_type('Weapon', 'lance'))
        self.assertFalse(forgeable_type('Weapon', 'pickaxe'))
        self.assertFalse(forgeable_type('Weapon', 'scythe'))

    def test_an_exo_per_item_version_gives_a_lance_an_exo_option_and_no_pickaxe_or_scythe(self):
        catalogue = _Catalogue('retro')
        Structure.read_forgeable_items_table(catalogue)
        found = {item_id for item_id, item in catalogue.items_dict.items() if item.forgeable}
        self.assertEqual({1}, found)

    def test_a_lance_is_eligible_for_a_dracorune_on_the_beta(self):
        self.assertTrue(eligible_item('Weapon', 'lance', FORGEABLE_ID, 'beta', RUNES))
        self.assertFalse(eligible_item('Weapon', 'pickaxe', FORGEABLE_ID, 'beta', RUNES))
        self.assertFalse(eligible_item('Weapon', 'scythe', FORGEABLE_ID, 'beta', RUNES))

    def test_a_lance_gets_a_transcendence_tip_on_dofus3_and_the_beta(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                self.assertIsNotNone(best_transcendence(version, {}, {'str': 1}, 'Weapon', 'lance'))
                self.assertIsNone(best_transcendence(version, {}, {'str': 1}, 'Weapon', 'pickaxe'))
                self.assertIsNone(best_transcendence(version, {}, {'str': 1}, 'Weapon', 'scythe'))
