# -*- coding: utf-8 -*-
"""Each version note has to be true of the table it introduces.

The Touch note told every reader, in five languages, that Touch "kept the
pre-2.29 weights: Vi runes give +3/+10/+30, Crit weighs 30, Heal weighs 20".
Those are the Retro column's numbers. The Touch table serves +5/+15/+50, crit
10 and heal 10, and the module docstring describes Touch as forked from Dofus
2.14 with wisdom at 1 against the PC's 3 -- it never claimed the Retro
weights. The note had been written against the wrong column, and nothing
compared the two.

So the claims each note makes are written out here, next to the table they
are claims about. A note and a table that drift apart now fail rather than
mislead.
"""
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
    """"fixed resists weigh 5, % resists 4, Reflects 30, Trap damage 15"."""

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
        # Control: the three tests above check the table, not the sentence.
        # If the sentence changes, they would keep passing while the page
        # said something else.
        note = LOCALIZED_UI['en']['version_note_retro']
        for claim in ('fixed resists weigh 5', '% resists 4',
                      'Reflects 30', 'Trap damage 15'):
            with self.subTest(claim=claim):
                self.assertIn(claim, note)


class TheTouchNoteIsTrue(TestCase):
    """"forked from Dofus 2.14: wisdom weighs 1 against the 3 on PC, and no
    reflect, no trap and no per-attack-type percentage runes"."""

    def test_wisdom_weighs_one_against_the_three_on_pc(self):
        self.assertEqual(1, density('touch', 'wis'))
        self.assertEqual(3, density('dofus3', 'wis'))

    def test_the_client_has_no_reflect_no_trap_and_no_per_type_percentages(self):
        for key in ('ref', 'trapdam', 'trapdamper') + PER_ATTACK_TYPE:
            with self.subTest(stat=key):
                self.assertIsNone(density('touch', key))
        # Control: the PC does have them, so the absence above says something.
        self.assertIsNotNone(density('dofus3', 'ref'))
        self.assertIsNotNone(density('dofus3', 'perspedam'))

    def test_the_three_weights_read_in_game_on_touch(self):
        # Settled by looking, on 2026-09-03: the Cri, So and Vi runes in the
        # game's own smithmagic interface give 10, 10 and 0.2. Forking at 2.14
        # did not keep the pre-2.29 crit 30, heal 20 and Vi +3/+10/+30 -- those
        # are the Retro column's, and the note used to hand them to Touch.
        self.assertEqual(10, density('touch', 'ch'))
        self.assertEqual(10, density('touch', 'heals'))
        self.assertEqual(0.2, density('touch', 'vit'))
        self.assertEqual([('', 5), ('Pa', 15), ('Ra', 50)],
                         get_fm_stats('touch')['vit']['tiers'])
        # Control: Retro really does hold the other three, so the reading
        # above distinguishes the two columns instead of matching both.
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
    """"no Ra rune for the elemental resists or critical resist, and no Pa
    rune for reflect"."""

    def test_no_ra_tier_on_the_elemental_resists_or_the_critical_resist(self):
        for key in ELEMENTS + ('crires',):
            with self.subTest(stat=key):
                self.assertNotIn('Ra', tier_names('dofus2', key) or [])
        # Control: Dofus 3 does grant them, which is what the note contrasts.
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
