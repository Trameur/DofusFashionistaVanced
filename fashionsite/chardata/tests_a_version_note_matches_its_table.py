# -*- coding: utf-8 -*-
"""Each version note has to be true of the table it introduces."""
import re

from django.test import TestCase

from chardata.forgemagie_data import get_fm_stats
from chardata.forgemagie_view import LOCALIZED_UI

ELEMENTS = ('neutres', 'earthres', 'fireres', 'waterres', 'airres')
PER_ELEMENTS = ('neutresper', 'earthresper', 'fireresper', 'waterresper',
                'airresper')
PER_ATTACK_TYPE = ('permedam', 'perrandam', 'perweadam', 'perspedam',
                   'respermee', 'resperran', 'resperwea')


def density(version, key):
    stat = get_fm_stats(version).get(key)
    return None if stat is None else stat['density']


def tier_names(version, key):
    stat = get_fm_stats(version).get(key)
    return None if stat is None else [tier for tier, _bonus in stat['tiers']]


class TheRetroNoteIsTrue(TestCase):

    def test_the_fixed_resists_weigh_five(self):
        for key in ELEMENTS:
            with self.subTest(stat=key):
                self.assertEqual(5, density('retro', key))

    def test_the_percentage_resists_weigh_four(self):
        for key in PER_ELEMENTS:
            with self.subTest(stat=key):
                self.assertEqual(4, density('retro', key))

    def test_reflect_weighs_thirty_and_trap_damage_fifteen(self):
        self.assertEqual(30, density('retro', 'ref'))
        self.assertEqual(15, density('retro', 'trapdam'))

    def test_the_note_still_says_so(self):
        note = LOCALIZED_UI['en']['version_note_retro']
        for claim in ('fixed resists weigh 5', '% resists 4',
                      'Reflects 30', 'Trap damage 15'):
            with self.subTest(claim=claim):
                self.assertIn(claim, note)


class TheTouchNoteIsTrue(TestCase):

    def test_wisdom_weighs_one_against_the_three_on_pc(self):
        self.assertEqual(1, density('touch', 'wis'))
        self.assertEqual(3, density('dofus3', 'wis'))

    def test_the_client_has_no_reflect_no_trap_and_no_per_type_percentages(self):
        for key in ('ref', 'trapdam', 'trapdamper') + PER_ATTACK_TYPE:
            with self.subTest(stat=key):
                self.assertIsNone(density('touch', key))
        self.assertIsNotNone(density('dofus3', 'ref'))
        self.assertIsNotNone(density('dofus3', 'perspedam'))

    def test_the_three_weights_read_in_game_on_touch(self):
        self.assertEqual(10, density('touch', 'ch'))
        self.assertEqual(10, density('touch', 'heals'))
        self.assertEqual(0.2, density('touch', 'vit'))
        self.assertEqual([('', 5), ('Pa', 15), ('Ra', 50)],
                         get_fm_stats('touch')['vit']['tiers'])
        self.assertEqual(30, density('retro', 'ch'))
        self.assertEqual(20, density('retro', 'heals'))
        self.assertEqual(0.25, density('retro', 'vit'))

    def test_the_note_no_longer_claims_the_retro_weights(self):
        note = LOCALIZED_UI['en']['version_note_touch']
        self.assertNotIn('30', note)
        self.assertNotIn('Heal weighs 20', note)

    def test_every_language_says_the_same_thing(self):
        for language in LOCALIZED_UI:
            with self.subTest(language=language):
                note = LOCALIZED_UI[language]['version_note_touch']
                self.assertIn('2.14', note)
                self.assertNotIn('2.29', note)


class TheDofus2NoteIsTrue(TestCase):

    def test_no_ra_tier_on_the_elemental_resists_or_the_critical_resist(self):
        for key in ELEMENTS + ('crires',):
            with self.subTest(stat=key):
                self.assertNotIn('Ra', tier_names('dofus2', key) or [])
        self.assertIn('Ra', tier_names('dofus3', 'crires') or [])

    def test_no_pa_tier_on_reflect(self):
        self.assertNotIn('Pa', tier_names('dofus2', 'ref') or [])
        self.assertIn('Pa', tier_names('dofus3', 'ref') or [])


class EveryRulesetHasANote(TestCase):

    def test_no_ruleset_is_left_without_one(self):
        from chardata.forgemagie_data import get_ruleset
        for version in ('dofus3', 'beta', 'dofus2', 'touch', 'retro'):
            with self.subTest(version=version):
                key = 'version_note_%s' % get_ruleset(version)
                for language in LOCALIZED_UI:
                    self.assertIn(key, LOCALIZED_UI[language])
                    self.assertTrue(LOCALIZED_UI[language][key].strip())


_ETIQUETTE_DU_RULESET = {
    'modern': 'Dofus 3',
    'dofus2': 'Dofus 2',
    'touch': 'Dofus Touch',
    'retro': 'Dofus Retro',
}

_NUMERO_DE_VERSION = re.compile(r'^\.\d+')


class ANoteNamesOnlyTheVersionsItIsShownTo(TestCase):

    def test_no_note_claims_a_version_served_by_another_table(self):
        coupables = []
        for ruleset, etiquette in sorted(_ETIQUETTE_DU_RULESET.items()):
            for langue in sorted(LOCALIZED_UI):
                note = LOCALIZED_UI[langue].get('version_note_%s' % ruleset)
                if not note:
                    continue
                for autre, nom in sorted(_ETIQUETTE_DU_RULESET.items()):
                    if autre == ruleset:
                        continue
                    depart = 0
                    while True:
                        i = note.find(nom, depart)
                        if i < 0:
                            break
                        depart = i + len(nom)
                        suite = note[i + len(nom):]
                        if _NUMERO_DE_VERSION.match(suite):
                            continue
                        if nom == 'Dofus 3' and suite.strip().startswith(
                                ('Beta', 'B\u00eata')):
                            continue
                        coupables.append((ruleset, langue, nom))
                        break
        self.assertFalse(
            coupables,
            'these notes name a version that a different table serves, so '
            'they promise numbers that do not apply: %s' % coupables)

    def test_the_sweep_reads_all_five_languages_and_all_four_rulesets(self):
        lues = 0
        for ruleset in _ETIQUETTE_DU_RULESET:
            for langue in LOCALIZED_UI:
                if LOCALIZED_UI[langue].get('version_note_%s' % ruleset):
                    lues += 1
        self.assertEqual(lues, 20, lues)
