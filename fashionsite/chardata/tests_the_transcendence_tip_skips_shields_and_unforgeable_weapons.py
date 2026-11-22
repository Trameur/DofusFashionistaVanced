# -*- coding: utf-8 -*-
"""A transcendence rune is only advised on the pieces a smithmagic skill works on."""
from django.test import SimpleTestCase

from chardata.transcendence_advice import best_transcendence
from fashionistapulp.transcendence_terms import takes_transcendence_rune

WEIGHTS = {'str': 1}


class TheTipSkipsPiecesThatTakeNoRuneTests(SimpleTestCase):

    def _tip(self, item_type, weapon_key=None, version='dofus3'):
        return best_transcendence(version, {}, WEIGHTS, item_type, weapon_key)

    def test_the_tip_skips_shields_pets_dofus_trophies_and_mounts(self):
        for item_type in ('Shield', 'Pet', 'Dofus', 'Trophy', 'Mount'):
            with self.subTest(item_type=item_type):
                self.assertIsNone(self._tip(item_type))

    def test_the_tip_skips_the_weapons_no_smithmagic_skill_works_on(self):
        for weapon_key in ('pickaxe', 'scythe', None):
            with self.subTest(weapon_key=weapon_key):
                self.assertIsNone(self._tip('Weapon', weapon_key))

    def test_the_tip_keeps_the_forgeable_weapons(self):
        for weapon_key in ('hammer', 'axe', 'shovel', 'staff', 'sword',
                           'dagger', 'bow', 'wand'):
            with self.subTest(weapon_key=weapon_key):
                self.assertIsNotNone(self._tip('Weapon', weapon_key))

    def test_the_tip_keeps_the_six_worn_types(self):
        for item_type in ('Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots'):
            with self.subTest(item_type=item_type):
                self.assertIsNotNone(self._tip(item_type))

    def test_the_shared_predicate_agrees_with_the_tip(self):
        self.assertTrue(takes_transcendence_rune('Ring', None))
        self.assertTrue(takes_transcendence_rune('Weapon', 'bow'))
        self.assertFalse(takes_transcendence_rune('Weapon', 'pickaxe'))
        self.assertFalse(takes_transcendence_rune('Shield', None))

    def test_the_versions_are_the_three_that_have_the_runes(self):
        for version in ('touch', 'retro', 'wakfu'):
            with self.subTest(version=version):
                self.assertIsNone(self._tip('Ring', version=version))
