# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A Retro piece takes an exo when a smithmagic skill works on its type and its fm flag allows it."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile

from django.test import SimpleTestCase

from chardata.tests import itemscraper_module
from fashionistapulp.exo_options import exo_count, forgeable_slot_count
from fashionistapulp.item import Item
from fashionistapulp.structure import (Structure, get_structure,
                                       set_current_game_version)
from fashionistapulp.weapon import WeaponType

_REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_SCRAPERS = os.path.join(_REPO, 'itemscraper')

_SKILLS = {'1': {'n': 'Smithmagic a hat', 'f': 16},
           '2': {'n': 'Smithmagic an amulet', 'f': 1},
           '3': {'n': 'Smithmagic a ring', 'f': 9},
           '4': {'n': 'Reap'},
           '5': 'none'}

_ITEMS = {'u': {
    '100': {'n': 'Hat', 't': 16, 'l': 50},
    '101': {'n': 'Frozen Hat', 't': 16, 'l': 50, 'fm': False},
    '102': {'n': 'Amulet', 't': 1, 'l': 60, 'fm': True},
    '103': {'n': 'Pet', 't': 18, 'l': 1},
    '104': {'n': 'Ring', 't': 9, 'l': 70},
    '105': {'n': 'Cloak', 't': 17, 'l': 80},
}}

_FORGEABLE = {100, 102, 104}

_RETRO_SLOTS = ['hat', 'cloak', 'amulet', 'ring1', 'ring2', 'belt', 'boots', 'weapon']


def _retro():
    return itemscraper_module('get_equipments_retro')


class TheSkillsNameTheTypesTests(SimpleTestCase):

    def test_only_a_skill_with_a_type_names_one(self):
        self.assertEqual({'16', '1', '9'}, _retro().mage_item_types(_SKILLS))

    def test_a_piece_needs_a_mage_type_and_no_fm_refusal(self):
        retro = _retro()
        equipment, _ = retro.build(_ITEMS, {}, mage_types=retro.mage_item_types(_SKILLS))
        self.assertEqual(_FORGEABLE,
                         {e['ankama_id'] for e in equipment if e['forgeable']})
        self.assertEqual(set(int(i) for i in _ITEMS['u']),
                         {e['ankama_id'] for e in equipment})

    def test_without_skills_no_piece_carries_the_flag(self):
        equipment, _ = _retro().build(_ITEMS, {})
        self.assertFalse([e for e in equipment if 'forgeable' in e])

    def test_the_downloaded_skills_name_the_fifteen_mage_types(self):
        path = os.path.join(_SCRAPERS, 'retro_raw', 'skills_fr.json')
        if not os.path.exists(path):
            self.skipTest('no Retro lang files here')
        with open(path, encoding='utf-8') as raw:
            skills = json.load(raw)['SK']
        self.assertEqual(
            {'1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '16', '17',
             '19', '81'},
            _retro().mage_item_types(skills))


class TheDumpListsTheForgeablePiecesTests(SimpleTestCase):

    def _dump(self, mage_types):
        retro = _retro()
        equipment, sets = retro.build(_ITEMS, {}, mage_types=mage_types)
        with tempfile.TemporaryDirectory() as directory:
            for name, rows in (('transformed_equipment.json', equipment),
                               ('transformed_sets.json', sets)):
                with open(os.path.join(directory, name), 'w', encoding='utf-8') as out:
                    json.dump(rows, out)
            dump = os.path.join(directory, 'items.dump')
            done = subprocess.run(
                [sys.executable, 'get_equipments3.py', '--input-dir', directory,
                 '--dump-output', dump],
                cwd=_SCRAPERS, capture_output=True, text=True, timeout=300)
            self.assertEqual(0, done.returncode, done.stderr)
            with open(dump, encoding='utf-8') as text:
                database = sqlite3.connect(':memory:')
                database.executescript(text.read())
        self.addCleanup(database.close)
        return database

    def test_the_table_holds_the_forgeable_pieces(self):
        database = self._dump(_retro().mage_item_types(_SKILLS))
        self.assertEqual(_FORGEABLE, {ankama_id for (ankama_id,) in database.execute(
            'SELECT i.ankama_id FROM forgeable_items f JOIN items i ON i.id = f.item')})

    def test_a_catalogue_without_the_flag_has_no_table(self):
        database = self._dump(None)
        self.assertIsNone(database.execute(
            "SELECT 1 FROM sqlite_master WHERE name = 'forgeable_items'").fetchone())


class _Catalogue:
    """The part of a structure read_forgeable_items_table reads."""

    _table_exists = Structure._table_exists

    def __init__(self, game_version, tables):
        self.game_version = game_version
        self.conn = sqlite3.connect(':memory:')
        self.conn.executescript(tables)
        self.types_dict = {1: 'Hat', 2: 'Weapon', 3: 'Pet'}
        self.weapon_type_dict = {}
        self.items_dict = {}
        self.dt_items_dict = {}
        for item_id, type_id in ((1, 1), (2, 2), (3, 3), (4, 2)):
            item = Item()
            item.id = item_id
            item.type = type_id
            self.items_dict[item_id] = item

    def get_item_by_id(self, item_id):
        return self.items_dict.get(item_id)

    def forgeable(self):
        Structure.read_forgeable_items_table(self)
        self.conn.close()
        return {i for i, item in self.items_dict.items() if item.forgeable}


_WEAPON_TYPES = ('CREATE TABLE weapontype (id INTEGER, key text, name text);'
                 "INSERT INTO weapontype VALUES (1, 'staff', 'Staff');"
                 "INSERT INTO weapontype VALUES (2, 'pickaxe', 'Pickaxe');"
                 'CREATE TABLE weapon_weapontype (item INTEGER, weapontype INTEGER);'
                 'INSERT INTO weapon_weapontype VALUES (2, 1);'
                 'INSERT INTO weapon_weapontype VALUES (4, 2);')


class TheStructureReadsTheTableTests(SimpleTestCase):

    def _catalogue(self, game_version, tables=''):
        catalogue = _Catalogue(game_version, _WEAPON_TYPES + tables)
        for type_id, key in ((1, 'staff'), (2, 'pickaxe')):
            weapon_type = WeaponType()
            weapon_type.id, weapon_type.key = type_id, key
            catalogue.weapon_type_dict[type_id] = weapon_type
        return catalogue

    def test_the_table_wins_over_the_type_rule(self):
        tables = ('CREATE TABLE forgeable_items (item INTEGER);'
                  'INSERT INTO forgeable_items VALUES (3);'
                  'INSERT INTO forgeable_items VALUES (99);')
        self.assertEqual({3}, self._catalogue('retro', tables).forgeable())

    def test_without_the_table_retro_follows_the_type_rule(self):
        self.assertEqual({1, 2}, self._catalogue('retro').forgeable())

    def test_without_the_table_other_versions_forge_nothing(self):
        self.assertEqual(set(), self._catalogue('dofus3').forgeable())


class TheCatalogueGivesEightForgeableSlotsTests(SimpleTestCase):

    def setUp(self):
        set_current_game_version('retro')

    def test_retro_forges_every_slot_but_the_shield_the_pet_and_the_dofus(self):
        structure = get_structure('retro')
        self.assertEqual(len(_RETRO_SLOTS), forgeable_slot_count(structure))
        types = {structure.get_type_name_by_id(item.type)
                 for item in structure.get_concatenated_items_lists() if item.forgeable}
        self.assertEqual({'Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots', 'Weapon'},
                         types)

    def test_no_synthetic_gelano_is_forgeable(self):
        structure = get_structure('retro')
        self.assertFalse([item.name for item in structure.get_concatenated_items_lists()
                          if item.id >= 990000000 and item.forgeable])

    def test_the_other_versions_have_no_forgeable_piece(self):
        for version in ('dofus3', 'beta', 'dofus2', 'touch'):
            with self.subTest(version=version):
                set_current_game_version(version)
                structure = get_structure(version)
                self.assertFalse([item.id for item in
                                  structure.get_concatenated_items_lists()
                                  if item.forgeable])


class AnExoOptionReadsAsACountTests(SimpleTestCase):

    def test_each_stored_value_gives_its_count(self):
        for value, count in ((True, 1), (False, 0), (None, 0), ('gelano', 0),
                             (0, 0), (3, 3), (-2, 0), ('3', 0)):
            with self.subTest(value=value):
                self.assertEqual(count, exo_count(value))
