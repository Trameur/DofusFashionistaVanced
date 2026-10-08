# Copyright (C) 2026 The Dofus Fashionista, LGPL (see COPYING.LESSER)
"""The weapon element control offers the kinds, elements and tiers the version's data sells, nothing else."""
import json
import os

from django.test import SimpleTestCase
from django.utils import translation

from chardata.solution_result import evolve_result_item
from chardata.weapon_forge_text import AUTO, NONE, controls
from fashionistapulp import weapon_forge
from fashionistapulp.dofus_constants import FIRE, NEUTRAL, WATER
from fashionistapulp.modelresult import ModelResult
from fashionistapulp.structure import get_structure, set_current_game_version

_VERSIONS = ('dofus3', 'beta', 'dofus2', 'touch', 'retro')
_MALLEFISK_WAND = 15216
_HIDSAD_BOW = 1355
_KUKRI_KURA = 8932
_STRONG_WEAK = {'strong': 100, 'weak': 10}
_THREE_TIERS = {'strong': 85, 'medium': 68, 'weak': 50}
_SOLD = {
    'dofus3': {'damage': _STRONG_WEAK, 'steal': _STRONG_WEAK, 'heal': _STRONG_WEAK},
    'beta': {'damage': _STRONG_WEAK, 'steal': _STRONG_WEAK, 'heal': _STRONG_WEAK},
    'dofus2': {'damage': _THREE_TIERS, 'steal': _THREE_TIERS},
    'touch': {'damage': _THREE_TIERS},
    'retro': {'damage': {'strong': 85}},
}
_BASE = {'Vitality': 0, 'Wisdom': 0, 'Strength': 0, 'Intelligence': 0,
         'Chance': 0, 'Agility': 0}
_OPTIONS = {'ap_exo': False, 'mp_exo': False, 'range_exo': False,
            'dofus': True, 'trophies': True, 'dragoturkey': True,
            'seemyool': True, 'rhineetle': True, 'prysmaradite': False,
            'dofuses': {}, 'dofusnotforchar': set()}


def _file(version):
    path = os.path.join(os.path.dirname(weapon_forge.__file__), 'weapon_conversions',
                        '%s.json' % version)
    with open(path, encoding='utf-8') as handle:
        return json.load(handle)


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
    return result, result.items['Weapon'][0]


class TheOfferComesFromTheVersionFileTests(SimpleTestCase):

    def test_each_version_sells_these_kinds_tiers_and_rates(self):
        for version in _VERSIONS:
            with self.subTest(version=version):
                found = {kind: {tier: weapon_forge.percent(version, kind, tier)
                                for tier in weapon_forge.offered_tiers(version, kind)}
                         for kind in weapon_forge.kinds(version)}
                self.assertEqual(_SOLD[version], found)

    def test_every_offered_option_is_a_row_of_the_file_with_a_rate(self):
        for version in _VERSIONS:
            table = _file(version)
            published = table.get('rate_published', True)
            for kind in weapon_forge.kinds(version):
                with self.subTest(version=version, kind=kind):
                    rows = {(row['element'], row['tier']) for row in table['conversions']
                            if row['kind'] == kind
                            and (row['rate'] is not None
                                 or (not published and row['tier'] == weapon_forge.STRONG))}
                    offer = weapon_forge.offer(version, kind)
                    self.assertEqual(rows, set(offer))
                    self.assertEqual(len(rows), len(offer))
                    self.assertNotIn(NEUTRAL, {element for element, _tier in offer})

    def test_an_option_the_version_does_not_sell_reads_as_nothing(self):
        self.assertEqual((FIRE, 'weak'), weapon_forge.read_option('dofus3', 'damage', 'fire:weak'))
        self.assertEqual((FIRE, 'medium'), weapon_forge.read_option('dofus2', 'steal', 'fire:medium'))
        for version, kind, text in (('dofus3', 'damage', 'fire:medium'),
                                    ('retro', 'damage', 'fire:weak'),
                                    ('dofus2', 'heal', 'fire:strong'),
                                    ('touch', 'steal', 'fire:strong'),
                                    ('dofus3', 'damage', 'neut:strong'),
                                    ('dofus3', 'damage', 'fire'),
                                    ('dofus3', 'damage', ''),
                                    ('dofus3', 'damage', None)):
            with self.subTest(version=version, kind=kind, text=text):
                self.assertIsNone(weapon_forge.read_option(version, kind, text))


class TheControlListsAutoNeutralThenTheOfferTests(SimpleTestCase):

    def test_each_kind_lists_auto_none_then_what_the_version_sells(self):
        for version in _VERSIONS:
            chosen = {kind: (FIRE, weapon_forge.STRONG) for kind in weapon_forge.kinds(version)}
            with translation.override('en'):
                found = controls(version, chosen, {})
            with self.subTest(version=version):
                self.assertEqual(list(weapon_forge.kinds(version)),
                                 [control['kind'] for control in found])
                for control in found:
                    self.assertEqual(AUTO, control['current'])
                    self.assertEqual(
                        [AUTO, NONE] + ['%s:%s' % pair for pair
                                        in weapon_forge.offer(version, control['kind'])],
                        [option['value'] for option in control['options']])

    def test_a_stored_choice_is_the_selected_option(self):
        stored = {'damage': (WATER, 'weak'), 'heal': None}
        chosen = dict(stored, heal=(NEUTRAL, 'strong'), steal=(FIRE, 'strong'))
        with translation.override('en'):
            found = {control['kind']: control['current']
                     for control in controls('dofus3', chosen, stored)}
        self.assertEqual({'damage': 'water:weak', 'steal': AUTO, 'heal': NONE}, found)

    def test_only_retro_carries_the_unpublished_rate_note(self):
        for version in _VERSIONS:
            chosen = {kind: (FIRE, weapon_forge.STRONG) for kind in weapon_forge.kinds(version)}
            with translation.override('en'):
                notes = [control['note'] for control in controls(version, chosen, {})]
            with self.subTest(version=version):
                if version == 'retro':
                    self.assertEqual(['The game does not publish this rate: the site '
                                      'assumes 85%.'], notes)
                else:
                    self.assertEqual({''}, set(notes))

    def test_the_options_are_written_in_the_page_language(self):
        chosen = {'damage': (FIRE, 'strong')}
        with translation.override('fr'):
            options = controls('dofus3', chosen, {})[0]['options']
        name = weapon_forge.item_name('dofus3', 'damage', FIRE, 'strong', 'fr')
        self.assertTrue(options[0]['text'].startswith('Auto'))
        self.assertEqual('Neutre', options[1]['text'])
        self.assertIn('%s (Feu, 100%%)' % name, [option['text'] for option in options])


class TheCardOffersOnlyTheKindsTheWeaponTurnsTests(SimpleTestCase):

    def test_a_staff_without_a_damage_line_offers_the_steal_and_the_heal(self):
        result, weapon = _worn(self, 'dofus3', _MALLEFISK_WAND, Intelligence=500)
        evolve_result_item(weapon, result)
        self.assertEqual(['steal', 'heal'], [control['kind'] for control in weapon.forge_controls])

    def test_a_version_without_engravings_offers_the_potion_alone(self):
        for version in ('touch', 'retro'):
            with self.subTest(version=version):
                result, weapon = _worn(self, version, _KUKRI_KURA, Intelligence=500)
                evolve_result_item(weapon, result)
                self.assertEqual(['damage'],
                                 [control['kind'] for control in weapon.forge_controls])

    def test_a_card_drawn_without_the_build_offers_nothing(self):
        _result, weapon = _worn(self, 'beta', _HIDSAD_BOW, Intelligence=500)
        evolve_result_item(weapon)
        self.assertEqual([], weapon.forge_controls)

    def test_a_level_one_weapon_offers_its_kind(self):
        result, weapon = _worn(self, 'dofus3', 1934, level=1)
        evolve_result_item(weapon, result)
        self.assertEqual(['damage'], [control['kind'] for control in weapon.forge_controls])
