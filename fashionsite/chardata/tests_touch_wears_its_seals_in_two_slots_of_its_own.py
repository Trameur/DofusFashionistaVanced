# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""Dofus Touch has two seal slots, filled by the items of super type 51."""

import json
import os
import re

from django.test import SimpleTestCase

from chardata.spell_reference import reference_by_spell_id
from fashionistapulp import temporix
from fashionistapulp.dofus_constants import SLOTS, slots_for, type_names_for
from fashionistapulp.game_versions import version_keys
from fashionistapulp.structure import (get_structure, level_to_wear,
                                       set_current_game_version)

_RAW = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), 'itemscraper', 'touch_raw')

# Touch breed ids, get_spells_touch.CLASS_ID_TO_NAME
_BREEDS = {1: 'Feca', 2: 'Osamodas', 3: 'Enutrof', 4: 'Sram', 5: 'Xelor',
           6: 'Ecaflip', 7: 'Eniripsa', 8: 'Iop', 9: 'Cra', 10: 'Sadida',
           11: 'Sacrier', 12: 'Pandawa', 13: 'Rogue', 14: 'Masqueraider',
           15: 'Foggernaut'}


def _raw(table):
    with open(os.path.join(_RAW, '%s_fr.json' % table), encoding='utf-8') as handle:
        return json.load(handle)


def _raw_super_type_51():
    super_types = {int(type_id): record.get('superTypeId')
                   for type_id, record in _raw('ItemTypes').items()
                   if isinstance(record, dict)}
    return {int(ankama_id): record for ankama_id, record in _raw('Items').items()
            if isinstance(record, dict)
            and super_types.get(record.get('typeId')) == 51}


class _Touch(SimpleTestCase):

    def setUp(self):
        set_current_game_version('touch')
        self.structure = get_structure('touch')
        emblem = self.structure.get_type_id_by_name('Emblem')
        self.seals = [item for item in self.structure.get_items_list()
                      if item.type == emblem]

    def tearDown(self):
        set_current_game_version('dofus3')


class TheSealItemsAreTheGamesTests(_Touch):

    def test_the_seal_slot_items_are_the_super_type_51_items(self):
        self.assertEqual(set(_raw_super_type_51()),
                         {item.ankama_id for item in self.seals})

    def test_each_touch_class_has_the_two_seals_its_pg_condition_names(self):
        wanted = {}
        for ankama_id, record in _raw_super_type_51().items():
            for breed in re.findall(r'(?:^|&)PG=(\d+)(?=&|$)',
                                    record.get('criteria') or ''):
                wanted.setdefault(_BREEDS[int(breed)], set()).add(ankama_id)
        worn = {}
        for item in self.seals:
            for char_class in getattr(item, 'classes', ()):
                worn.setdefault(char_class, set()).add(item.ankama_id)
        self.assertEqual(wanted, worn)
        self.assertEqual(15, len(worn))
        self.assertEqual({2}, {len(ids) for ids in worn.values()})

    def test_the_insignia_and_the_spell_book_fit_every_class(self):
        for ankama_id in (23485, 24057):
            with self.subTest(ankama_id=ankama_id):
                item = self.structure.get_item_by_ankama_id(ankama_id)
                self.assertEqual(self.structure.get_type_id_by_name('Emblem'),
                                 item.type)
                self.assertEqual((), getattr(item, 'classes', ()))

    def test_a_seal_carries_no_stat(self):
        self.assertEqual([], [item.name for item in self.seals if item.stats])

    def test_the_doom_spell_book_is_temporix_only(self):
        doom = self.structure.get_item_by_ankama_id(24057)
        self.assertIn(doom.id, temporix.temporix_only_item_ids(self.structure))


class TheSealSlotsAreTouchOnlyTests(SimpleTestCase):

    def tearDown(self):
        set_current_game_version('dofus3')

    def test_touch_has_the_sixteen_slots_and_two_seal_slots(self):
        self.assertEqual(SLOTS + ['emblem1', 'emblem2'], slots_for('touch'))

    def test_every_other_version_keeps_its_sixteen_slots(self):
        for version in version_keys():
            if version == 'touch':
                continue
            with self.subTest(version=version):
                self.assertEqual(SLOTS, slots_for(version))
                self.assertNotIn('Emblem', type_names_for(version))

    def test_no_other_catalogue_has_a_seal_type(self):
        for version in version_keys():
            if version == 'touch':
                continue
            with self.subTest(version=version):
                set_current_game_version(version)
                self.assertNotIn('Emblem',
                                 get_structure(version).get_types_list())


class ASealWaitsForItsSpellRankTests(_Touch):

    def test_the_rank_level_is_the_one_the_spell_reference_gives(self):
        checked = 0
        for item in self.seals:
            for spell_id, rank, min_level in getattr(item, 'spell_conditions', ()):
                with self.subTest(seal=item.name):
                    (char_class,) = item.classes
                    spell = reference_by_spell_id('touch', char_class)[spell_id]
                    self.assertEqual(spell['levels'][rank - 1], min_level)
                    checked += 1
        self.assertEqual(30, checked)

    def test_four_seals_need_more_than_their_own_level(self):
        later = {item.name: level_to_wear(item) for item in self.seals
                 if level_to_wear(item) > item.level}
        self.assertEqual({'Osamodas Seal: Bestial Heal': 195,
                          'Sadida Seal: Insolent Bramble': 195,
                          'Sacrier Seal: Retribution': 200,
                          'Sram Seal: Paralysing Trap': 200}, later)

    def test_the_catalogue_offers_a_seal_from_the_level_that_wears_it(self):
        retribution = self.structure.get_item_by_name('Sacrier Seal: Retribution')
        martyr = self.structure.get_item_by_name('Sacrier Seal: Martyr Punishment')
        at_199 = self.structure.get_unique_items_by_type_and_level('Emblem', 199)
        at_200 = self.structure.get_unique_items_by_type_and_level('Emblem', 200)
        self.assertNotIn(retribution, at_199)
        self.assertIn(martyr, at_199)
        self.assertIn(retribution, at_200)
