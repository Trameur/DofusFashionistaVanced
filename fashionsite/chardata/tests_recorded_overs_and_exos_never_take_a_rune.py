# -*- coding: utf-8 -*-
"""The solver puts no rune on weapons, shields, overed pieces, exo carriers or TemporiX."""
from django.test import SimpleTestCase

from fashionistapulp.transcendence_terms import (copy_takes_rune,
                                                 solver_takes_rune)


class ACopyTakesARuneOnlyWhenNothingElseUsesItTests(SimpleTestCase):

    def test_a_ring_is_accepted(self):
        self.assertTrue(solver_takes_rune('Ring', None))
        self.assertTrue(copy_takes_rune('Ring', None))

    def test_the_six_worn_types_are_accepted(self):
        for item_type in ('Hat', 'Cloak', 'Amulet', 'Ring', 'Belt', 'Boots'):
            with self.subTest(item_type=item_type):
                self.assertTrue(copy_takes_rune(item_type, None))

    def test_weapons_are_refused_even_when_forgeable(self):
        for weapon_key in ('hammer', 'bow', 'lance', 'pickaxe', None):
            with self.subTest(weapon_key=weapon_key):
                self.assertFalse(solver_takes_rune('Weapon', weapon_key))
                self.assertFalse(copy_takes_rune('Weapon', weapon_key))

    def test_shields_and_the_rest_are_refused(self):
        for item_type in ('Shield', 'Pet', 'Dofus', 'Trophy', 'Mount'):
            with self.subTest(item_type=item_type):
                self.assertFalse(copy_takes_rune(item_type, None))

    def test_each_flag_refuses_a_ring(self):
        for flag in ('overed', 'exo_carrier', 'temporix'):
            with self.subTest(flag=flag):
                self.assertFalse(copy_takes_rune('Ring', None, **{flag: True}))

    def test_flags_left_false_change_nothing(self):
        self.assertTrue(copy_takes_rune('Ring', None, overed=False,
                                        exo_carrier=False, temporix=False))
