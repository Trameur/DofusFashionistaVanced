# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The weapon card and the spells page name each conversion with the client's item name, in the page language."""
from django.test import SimpleTestCase
from django.utils import translation
from django.utils.html import escape

from chardata.solution_result import evolve_result_item
from chardata.spells_view import _create_weapon_web_digest
from chardata.translation_util import LOCALIZED_ELEMENTS
from chardata.weapon_forge_text import conversion_line, conversion_lines
from chardata.weapon_header import format_weapon_hit
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import FIRE, NEUTRAL, WATER
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

_LANGUAGES = ('en', 'fr', 'es', 'pt', 'de')
_MALLEFISK_WAND = 15216
_HIDSAD_BOW = 1355
_LEVEL_ONE_WEAPONS = (('dofus3', 1934), ('beta', 1934), ('dofus2', 1934),
                      ('touch', 497), ('retro', 88))
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


def _worn(test, version, ankama_id, choice=None, level=200, **base):
    test.addCleanup(set_current_game_version, 'dofus3')
    set_current_game_version(version)
    structure = get_structure(version)
    result = ModelResult({'options': dict(_OPTIONS),
                          'base_stats_by_attr': dict(_BASE, **base),
                          'char_level': level})
    result.forge_choice = choice
    result.add_item_at_slot(structure.get_item_by_ankama_id(ankama_id), 'weapon')
    result.calculate_stats()
    return result.items['Weapon'][0]


def _card(weapon, language='en'):
    with translation.override(language):
        evolve_result_item(weapon)
        return weapon.damage_text.split('<br>')


def _rows(version, hits, language='en'):
    with translation.override(language):
        return [format_weapon_hit(version, hit, LOCALIZED_ELEMENTS) for hit in hits]


def _name(version, kind, element, tier, language):
    return weapon_forge.row(version, kind, element, tier)['names'][language]


class EachConversionHasItsLineThenTheRowsTests(SimpleTestCase):

    def test_the_lines_come_in_kind_order_before_the_converted_rows(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                weapon = _worn(self, version, _HIDSAD_BOW,
                               {'damage': (FIRE, 'strong'), 'heal': (WATER, 'weak')})
                lines = _card(weapon)
                damage = _name(version, 'damage', FIRE, 'strong', 'en')
                heal = _name(version, 'heal', WATER, 'weak', 'en')
                start = next(index for index, line in enumerate(lines)
                             if escape(damage) in line)
                self.assertEqual(escape('%s: Fire, 100%%' % damage), lines[start])
                self.assertEqual(escape('%s: Water, 10%%' % heal), lines[start + 1])
                self.assertEqual(_rows(version, weapon.non_crit_hits[FIRE]),
                                 lines[start + 2:])

    def test_a_steal_only_weapon_shows_its_neutral_tab_with_the_turned_steal(self):
        weapon = _worn(self, 'dofus3', _MALLEFISK_WAND,
                       {'steal': (WATER, 'strong'), 'heal': None})
        lines = _card(weapon)
        steal = escape('%s: Water, 100%%' % _name('dofus3', 'steal', WATER, 'strong', 'en'))
        self.assertEqual(1, lines.count(steal))
        self.assertFalse(weapon.is_mageable)
        rows = _rows('dofus3', weapon.non_crit_hits[NEUTRAL])
        self.assertEqual(rows, lines[lines.index(steal) + 1:])
        self.assertNotEqual(_rows('dofus3', weapon.forge_base), rows)

    def test_nothing_converted_shows_the_catalogue_rows_and_nothing_else(self):
        for version in ('dofus3', 'beta'):
            with self.subTest(version=version):
                weapon = _worn(self, version, _HIDSAD_BOW, {'damage': None, 'heal': None},
                               Intelligence=500)
                self.assertEqual([], conversion_lines(version, weapon.conversions))
                lines = _card(weapon)
                rows = _rows(version, weapon.forge_base)
                self.assertEqual(rows, lines[-len(rows):])
                self.assertLessEqual(len(lines) - len(rows), 1)
                for kind in weapon_forge.kinds(version):
                    for element, tier in weapon_forge.offer(version, kind):
                        self.assertNotIn(escape(_name(version, kind, element, tier, 'en')),
                                         weapon.damage_text)

    def test_an_auto_build_names_the_conversion_it_computes_with(self):
        weapon = _worn(self, 'beta', _MALLEFISK_WAND, Intelligence=500)
        lines = _card(weapon)
        for kind in ('steal', 'heal'):
            with self.subTest(kind=kind):
                self.assertIn(escape('%s: Fire, 100%%' % _name('beta', kind, FIRE, 'strong', 'en')),
                              lines)


class TheItemNameFollowsThePageLanguageTests(SimpleTestCase):

    def test_each_language_reads_the_client_name(self):
        for version in ('dofus3', 'beta', 'dofus2'):
            names = set()
            for language in _LANGUAGES:
                with self.subTest(version=version, language=language):
                    with translation.override(language):
                        line = conversion_line(version, 'damage', FIRE, 'strong')
                        element = str(LOCALIZED_ELEMENTS[FIRE])
                    name = _name(version, 'damage', FIRE, 'strong', language)
                    self.assertTrue(line.startswith(name))
                    self.assertIn(element, line)
                    names.add(name)
            self.assertEqual(len(_LANGUAGES), len(names))

    def test_the_card_line_is_written_in_the_page_language(self):
        weapon = _worn(self, 'dofus3', _HIDSAD_BOW, {'damage': (FIRE, 'strong'), 'heal': None})
        lines = _card(weapon, 'fr')
        expected = escape('%s : Feu, 100%%' % _name('dofus3', 'damage', FIRE, 'strong', 'fr'))
        self.assertIn(expected, lines)

    def test_touch_has_no_german_names_and_reads_the_english_one(self):
        row = weapon_forge.row('touch', 'damage', FIRE, 'strong')
        self.assertNotIn('de', row['names'])
        with translation.override('de'):
            line = conversion_line('touch', 'damage', FIRE, 'strong')
        self.assertTrue(line.startswith(row['names']['en']))

    def test_retro_says_its_rate_is_assumed(self):
        self.assertFalse(weapon_forge.rate_published('retro'))
        self.assertIsNone(weapon_forge.rate('retro', 'damage', 'strong'))
        assumed = weapon_forge.percent('retro', 'damage', 'strong')
        for language, word in (('en', 'assumed'), ('fr', 'supposé'),
                               ('es', 'supuesto'), ('pt', 'suposto'), ('de', 'angenommen')):
            with self.subTest(language=language):
                with translation.override(language):
                    line = conversion_line('retro', 'damage', FIRE, 'strong')
                self.assertIn('%d%%' % assumed, line)
                self.assertIn(word, line)
        with translation.override('en'):
            self.assertNotIn('assumed', conversion_line('dofus2', 'damage', FIRE, 'strong'))


class ALevelOneWeaponTurnsLikeAnyOtherTests(SimpleTestCase):

    def test_the_minimum_level_card_names_the_chosen_potion(self):
        for version, ankama_id in _LEVEL_ONE_WEAPONS:
            with self.subTest(version=version):
                tier = weapon_forge.offered_tiers(version, 'damage')[-1]
                weapon = _worn(self, version, ankama_id, {'damage': (WATER, tier)}, level=1)
                self.assertEqual(1, get_structure(version).get_item_by_ankama_id(ankama_id).level)
                self.assertEqual(WATER, weapon.element_maged)
                lines = _card(weapon)
                name = escape(_name(version, 'damage', WATER, tier, 'en'))
                self.assertEqual(1, sum(name in line for line in lines))
                self.assertEqual(_rows(version, weapon.non_crit_hits[WATER]),
                                 lines[-len(weapon.non_crit_hits[WATER]):])

    def test_the_minimum_level_card_without_a_conversion_is_unchanged(self):
        for version, ankama_id in _LEVEL_ONE_WEAPONS:
            with self.subTest(version=version):
                weapon = _worn(self, version, ankama_id, {'damage': None}, level=1)
                self.assertEqual({}, {kind: value for kind, value
                                      in weapon.conversions.items() if value[0] != NEUTRAL})
                lines = _card(weapon)
                self.assertEqual(_rows(version, weapon.forge_base),
                                 lines[-len(weapon.forge_base):])
                self.assertLessEqual(len(lines) - len(weapon.forge_base), 1)


class TheSpellsPageNamesTheStealAndHealTests(SimpleTestCase):

    def test_the_weapon_digest_lists_the_steal_and_heal_lines_only(self):
        weapon = _worn(self, 'dofus3', _HIDSAD_BOW,
                       {'damage': (FIRE, 'strong'), 'heal': (WATER, 'weak')})
        with translation.override('en'):
            digest = _create_weapon_web_digest(weapon)
        self.assertEqual(FIRE, digest['element_maged'])
        self.assertEqual(['%s: Water, 10%%' % _name('dofus3', 'heal', WATER, 'weak', 'en')],
                         digest['item_notes'])

    def test_a_staff_that_steals_and_heals_names_both(self):
        weapon = _worn(self, 'beta', _MALLEFISK_WAND, Intelligence=500)
        with translation.override('en'):
            digest = _create_weapon_web_digest(weapon)
        self.assertEqual(['%s: Fire, 100%%' % _name('beta', kind, FIRE, 'strong', 'en')
                          for kind in ('steal', 'heal')], digest['item_notes'])

    def test_a_neutral_choice_adds_no_note(self):
        weapon = _worn(self, 'dofus3', _HIDSAD_BOW, {'damage': (FIRE, 'strong'), 'heal': None})
        with translation.override('en'):
            self.assertEqual([], _create_weapon_web_digest(weapon)['item_notes'])
