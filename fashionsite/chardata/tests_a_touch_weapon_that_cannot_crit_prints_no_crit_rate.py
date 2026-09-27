# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""On Touch a weapon with base critical 0 gets no critical line in its header."""
from django.test import SimpleTestCase
from django.utils import translation

from chardata.encyclopedia_view import _get_weapon_detail_lines
from chardata.solution_result import evolve_result_item
from chardata.weapon_header import format_weapon_header
from fashionistapulp.modelresult import ModelResultItem
from fashionistapulp.structure import get_structure, set_current_game_version

LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
TOUCH_ARCHONS_BOW = 14164
TOUCH_SKY_WAND = 181
DOFUS3_ABATZ_SWORD = 7199
RETRO_KAISER = 233


class _Versioned(SimpleTestCase):

    def _structure(self, version):
        set_current_game_version(version)
        self.addCleanup(set_current_game_version, 'dofus3')
        return get_structure(version)

    def _header(self, structure, item_id, language):
        item = structure.get_item_by_id(item_id)
        self.assertIsNotNone(item, item_id)
        lines = _get_weapon_detail_lines(structure, [item], language)
        self.assertTrue(lines, item_id)
        return lines[0]


class TheTouchHeaderTests(_Versioned):

    def test_base_zero_prints_the_cost_alone(self):
        self.assertEqual('(Bow) AP: 4',
                         format_weapon_header('touch', 'Bow', 4, 0, 0))
        self.assertEqual('AP: 4', format_weapon_header('touch', None, 4, 0, 0))
        self.assertEqual('(Bow)',
                         format_weapon_header('touch', 'Bow', None, 0, 0))
        self.assertEqual('', format_weapon_header('touch', None, None, 0, 0))

    def test_a_real_base_zero_weapon_shows_no_rate_in_any_language(self):
        structure = self._structure('touch')
        weapon = structure.get_weapon_by_name(
            structure.get_item_by_id(TOUCH_ARCHONS_BOW).name)
        self.assertEqual((4, 0, 0), (weapon.ap, weapon.crit_chance,
                                     weapon.crit_bonus))
        self.assertEqual('(Bow) AP: 4',
                         self._header(structure, TOUCH_ARCHONS_BOW, 'en'))
        for language in LANGUAGES:
            with self.subTest(language=language):
                header = self._header(structure, TOUCH_ARCHONS_BOW, language)
                self.assertIn('4', header)
                self.assertNotIn('%', header)
                self.assertNotIn('/', header)

    def test_a_real_base_twenty_five_weapon_keeps_its_rate(self):
        structure = self._structure('touch')
        self.assertEqual('(Wand) AP: 4 / CH: 25% (+5)',
                         self._header(structure, TOUCH_SKY_WAND, 'en'))
        for language in LANGUAGES:
            with self.subTest(language=language):
                header = self._header(structure, TOUCH_SKY_WAND, language)
                self.assertIn('25%', header)
                self.assertIn('(+5)', header)

    def test_every_touch_weapon_shows_a_rate_exactly_when_its_base_is_set(self):
        structure = self._structure('touch')
        zero = 0
        for name, weapon in structure.weapons_dict_by_name.items():
            if weapon.ap is None or weapon.crit_chance is None:
                continue
            header = format_weapon_header('touch', 'Sword', weapon.ap,
                                          weapon.crit_chance,
                                          weapon.crit_bonus)
            with self.subTest(weapon=name):
                if weapon.crit_chance == 0:
                    zero += 1
                    self.assertEqual('(Sword) AP: %d' % weapon.ap, header)
                else:
                    self.assertIn('%d%%' % weapon.crit_chance, header)
        self.assertTrue(zero)


class ThePickerHeaderTests(_Versioned):

    def _picker_header(self, item_id, language):
        item = self._structure('touch').get_item_by_id(item_id)
        self.assertIsNotNone(item, item_id)
        with translation.override(language):
            result_item = ModelResultItem(item)
            evolve_result_item(result_item)
        return result_item.damage_text.split('<br>')[0]

    def test_a_base_zero_weapon_shows_no_rate_in_the_picker(self):
        self.assertEqual('(Bow) AP: 4',
                         self._picker_header(TOUCH_ARCHONS_BOW, 'en'))
        for language in LANGUAGES:
            with self.subTest(language=language):
                header = self._picker_header(TOUCH_ARCHONS_BOW, language)
                self.assertIn('4', header)
                self.assertNotIn('%', header)
                self.assertNotIn('/', header)

    def test_a_base_twenty_five_weapon_keeps_its_rate_in_the_picker(self):
        self.assertEqual('(Wand) AP: 4 / CH: 25% (+5)',
                         self._picker_header(TOUCH_SKY_WAND, 'en'))
        for language in LANGUAGES:
            with self.subTest(language=language):
                header = self._picker_header(TOUCH_SKY_WAND, language)
                self.assertIn('25%', header)
                self.assertIn('(+5)', header)


class TheOtherVersionsKeepTheirHeaderTests(_Versioned):

    def test_a_dofus3_weapon_at_twenty_five_percent(self):
        structure = self._structure('dofus3')
        self.assertEqual('(Sword) AP: 4 / CH: 25% (+10)',
                         self._header(structure, DOFUS3_ABATZ_SWORD, 'en'))

    def test_a_retro_weapon_keeps_its_fraction(self):
        structure = self._structure('retro')
        self.assertEqual('(Hammer) AP: 4 / CH: 1/200 (+20)',
                         self._header(structure, RETRO_KAISER, 'en'))
