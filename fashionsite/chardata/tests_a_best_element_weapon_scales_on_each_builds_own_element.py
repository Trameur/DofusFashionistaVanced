# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""A best element weapon hits in the best element of the build wearing it."""
import collections
import sqlite3
from unittest import mock

from django.test import SimpleTestCase

from chardata.item_exchange import _get_weapon_info
import fashionistapulp.dofus_constants as modern
import fashionistapulp.dofus_constants_beta as beta
import fashionistapulp.dofus_constants_dofus2 as dofus2
from fashionistapulp.dofus_constants import (EARTH, FIRE, NEUTRAL,
                                             NON_ELEMENTAL_HIT_TYPES,
                                             calculate_damage)
from fashionistapulp.fashionista_config import get_items_db_path
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

_MENALTS_LIGHTNING_SPEAR = 32116
_WARS_HALBAXE = 22368
_MOSKITO_SWATTER = 29024
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}
_BUILDS = (({'Strength': 500}, EARTH),
           ({'Intelligence': 500}, FIRE),
           ({'Strength': 500}, EARTH))


def _elements_in_the_data(version, item_id):
    connection = sqlite3.connect(
        'file:%s?mode=ro' % get_items_db_path(version), uri=True)
    try:
        return [row[0] for row in connection.execute(
            'SELECT element FROM weapon_hits WHERE item = ? ORDER BY hit',
            (item_id,))]
    finally:
        connection.close()


def _signed(hits, side):
    return sum(-getattr(hit, side) if hit.heals else getattr(hit, side)
               for hit in hits)


class _ABestElementWeapon(object):

    def setUp(self):
        self.addCleanup(set_current_game_version, 'dofus3')
        set_current_game_version(self.version)
        self.structure = get_structure(self.version)
        self.item = self.structure.get_item_by_ankama_id(self.ankama_id)
        self.assertIsNotNone(self.item, self.ankama_id)
        self.weapon = self.structure.get_weapon_by_name(self.item.name)
        self.elements = _elements_in_the_data(self.version, self.item.id)

    def _build(self, **base):
        result = ModelResult({'options': dict(_OPTIONS),
                              'base_stats_by_attr': dict(_BASE, **base),
                              'char_level': 200})
        result.add_item_at_slot(self.item, 'weapon')
        result.calculate_stats()
        return result

    def _rows(self, critical):
        return (self.weapon.crit_hits if critical
                else self.weapon.non_crit_hits)[NEUTRAL]

    def _faced(self, rows, element):
        return [row.copy_with_element(element if data == 'best' else data)
                for row, data in zip(rows, self.elements)]

    def test_the_data_gives_the_weapon_a_best_element_row(self):
        self.assertIn('best', self.elements)
        self.assertTrue(self.weapon.has_crits)

    def test_each_build_in_turn_hits_in_its_own_best_element(self):
        for base, element in _BUILDS:
            stats = self._build(**base).get_stats_total()
            expected = [element if data == 'best' else data
                        for data in self.elements
                        if data not in NON_ELEMENTAL_HIT_TYPES]
            for critical in (False, True):
                with self.subTest(build=base, critical=critical):
                    hits = calculate_damage(self._rows(critical), stats,
                                            critical_hit=critical,
                                            is_spell=False)
                    self.assertEqual(expected, [hit.element for hit in hits])

    def test_the_cached_rows_still_read_the_data_after_every_build(self):
        for base, _element in _BUILDS:
            stats = self._build(**base).get_stats_total()
            for critical in (False, True):
                calculate_damage(self._rows(critical), stats,
                                 critical_hit=critical, is_spell=False)
        for rows in (self.weapon.base_hit, self._rows(False),
                     self._rows(True)):
            self.assertEqual(self.elements, [row.element for row in rows])

    def test_the_weapon_card_of_each_build_scales_on_its_own_element(self):
        for base, element in _BUILDS:
            result = self._build(**base)
            with mock.patch('chardata.item_exchange.get_solution',
                            return_value=result):
                info = _get_weapon_info(self.item, None)
            stats = result.stats_total
            for critical, low, high in ((False, 'min_noncrit_dam',
                                         'max_noncrit_dam'),
                                        (True, 'min_crit_dam',
                                         'max_crit_dam')):
                hits = calculate_damage(
                    self._faced(self._rows(critical), element), stats,
                    critical_hit=critical, is_spell=False)
                with self.subTest(build=base, critical=critical):
                    self.assertEqual(
                        (_signed(hits, 'min_dam'), _signed(hits, 'max_dam')),
                        (info[low], info[high]))


class ALiveBestElementSpearTests(_ABestElementWeapon, SimpleTestCase):

    version = 'dofus3'
    ankama_id = _MENALTS_LIGHTNING_SPEAR


class ABetaBestElementHalbaxeTests(_ABestElementWeapon, SimpleTestCase):

    version = 'beta'
    ankama_id = _WARS_HALBAXE


class ADofus2BestElementSwatterTests(_ABestElementWeapon, SimpleTestCase):

    version = 'dofus2'
    ankama_id = _MOSKITO_SWATTER


class EveryCopyOfTheFormulaLeavesItsRowsAloneTests(SimpleTestCase):

    def test_one_row_scaled_for_two_builds_hits_each_ones_element(self):
        for constants in (modern, beta, dofus2):
            for token in ('best', 'damage', 'best-element'):
                with self.subTest(module=constants.__name__, token=token):
                    rows = [constants.BaseDamage(30, 40, token)]
                    strength = constants.calculate_damage(
                        rows, collections.defaultdict(int, str=100),
                        False, False)
                    intelligence = constants.calculate_damage(
                        rows, collections.defaultdict(int, int=100),
                        False, False)
                    self.assertEqual(
                        [(EARTH, 60, 80)],
                        [(hit.element, hit.min_dam, hit.max_dam)
                         for hit in strength])
                    self.assertEqual(
                        [(FIRE, 60, 80)],
                        [(hit.element, hit.min_dam, hit.max_dam)
                         for hit in intelligence])
                    self.assertEqual(token, rows[0].element)
